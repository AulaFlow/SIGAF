-- =====================================================================
-- SIGAF · db/03_funciones_triggers.sql
-- Funciones, procedimientos almacenados y triggers.
--   Funciones:      fn_estado_entrega, fn_porcentaje_asistencia,
--                   fn_calificar_intento
--   Procedimientos: sp_inscribir_alumno, sp_enviar_intento
--   Triggers:       trg_recalcular_promedio, trg_estado_entrega,
--                   trg_bitacora_calificacion, trg_tarea_notificar,
--                   trg_intento_validar y los de shard key (trg_*_centro)
-- Nota: fn_trg_estado_entrega se reemplaza en 07_margen_entrega.sql
--       (margen de entrega tardía por tarea; rechazo con SQLSTATE SG001).
-- =====================================================================
SET search_path TO sigaf;

-- =====================================================================
-- 1. Funciones
-- =====================================================================

-- Estado de una entrega según su fecha y la fecha límite de la tarea.
CREATE OR REPLACE FUNCTION fn_estado_entrega(p_entregada TIMESTAMPTZ, p_limite TIMESTAMPTZ)
RETURNS VARCHAR
LANGUAGE sql IMMUTABLE
AS $$
    SELECT CASE WHEN p_entregada <= p_limite THEN 'a_tiempo' ELSE 'tardia' END;
$$;

-- Porcentaje de asistencia (presente, retardo y justificada cuentan).
CREATE OR REPLACE FUNCTION fn_porcentaje_asistencia(p_inscripcion BIGINT)
RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
    SELECT CASE WHEN count(*) = 0 THEN NULL
                ELSE round(100.0 * count(*) FILTER (WHERE estado <> 'falta') / count(*), 1)
           END
    FROM asistencia
    WHERE inscripcion_id = p_inscripcion;
$$;

-- Califica un intento de examen de opción múltiple en escala 0-10.
CREATE OR REPLACE FUNCTION fn_calificar_intento(p_intento BIGINT)
RETURNS NUMERIC
LANGUAGE plpgsql
AS $$
DECLARE
    v_total     NUMERIC;
    v_obtenido  NUMERIC;
    v_examen    BIGINT;
BEGIN
    SELECT examen_id INTO v_examen FROM intento_examen WHERE intento_id = p_intento;
    IF v_examen IS NULL THEN
        RAISE EXCEPTION 'El intento % no existe', p_intento USING ERRCODE = 'P0002';
    END IF;

    SELECT coalesce(sum(puntos), 0) INTO v_total FROM pregunta WHERE examen_id = v_examen;

    SELECT coalesce(sum(p.puntos), 0) INTO v_obtenido
    FROM respuesta r
    JOIN opcion o   ON o.opcion_id = r.opcion_id
    JOIN pregunta p ON p.pregunta_id = r.pregunta_id
    WHERE r.intento_id = p_intento AND o.es_correcta;

    RETURN CASE WHEN v_total = 0 THEN 0 ELSE round(10 * v_obtenido / v_total, 2) END;
END;
$$;

-- =====================================================================
-- 2. Triggers
-- =====================================================================

-- 2.1 trg_recalcular_promedio (lo pidió el profe)
-- Cada vez que se inserta, cambia o borra una calificación, recalcula
-- inscripcion.promedio_parciales con los parciales 1, 2 y 3.
CREATE OR REPLACE FUNCTION fn_recalcular_promedio()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_inscripcion BIGINT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_inscripcion := OLD.inscripcion_id;
    ELSE
        v_inscripcion := NEW.inscripcion_id;
    END IF;

    UPDATE inscripcion
       SET promedio_parciales = (
               SELECT round(avg(valor), 2)
               FROM calificacion
               WHERE inscripcion_id = v_inscripcion
                 AND tipo IN ('parcial1', 'parcial2', 'parcial3'))
     WHERE inscripcion_id = v_inscripcion;

    RETURN NULL;   -- AFTER trigger: el valor de retorno se ignora
END;
$$;

CREATE TRIGGER trg_recalcular_promedio
AFTER INSERT OR UPDATE OF valor, tipo OR DELETE ON calificacion
FOR EACH ROW EXECUTE FUNCTION fn_recalcular_promedio();

-- 2.2 trg_estado_entrega
-- Valida que quien entrega esté inscrito (activo) en el grupo de la tarea
-- y marca sola si la entrega fue a tiempo o tardía.
CREATE OR REPLACE FUNCTION fn_trg_estado_entrega()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_limite TIMESTAMPTZ;
BEGIN
    SELECT t.fecha_limite INTO v_limite
    FROM tarea t
    JOIN inscripcion i ON i.grupo_id = t.grupo_id
    WHERE t.tarea_id = NEW.tarea_id
      AND i.inscripcion_id = NEW.inscripcion_id
      AND i.estado = 'activa';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'La inscripción % no pertenece al grupo de la tarea %',
            NEW.inscripcion_id, NEW.tarea_id USING ERRCODE = 'P0001';
    END IF;

    NEW.estado := fn_estado_entrega(NEW.entregada_en, v_limite);
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_estado_entrega
BEFORE INSERT OR UPDATE OF entregada_en ON entrega
FOR EACH ROW EXECUTE FUNCTION fn_trg_estado_entrega();

-- 2.3 trg_bitacora_calificacion
-- Deja rastro de cada alta, cambio de valor o baja de una calificación:
-- quién (usuario de la BD), cuándo, valor anterior y nuevo.
CREATE OR REPLACE FUNCTION fn_bitacora_calificacion()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO bitacora_calificacion (calificacion_id, inscripcion_id, operacion, valor_nuevo)
        VALUES (NEW.calificacion_id, NEW.inscripcion_id, 'I', NEW.valor);
    ELSIF TG_OP = 'UPDATE' THEN
        IF NEW.valor IS DISTINCT FROM OLD.valor THEN
            INSERT INTO bitacora_calificacion
                (calificacion_id, inscripcion_id, operacion, valor_anterior, valor_nuevo)
            VALUES (NEW.calificacion_id, NEW.inscripcion_id, 'U', OLD.valor, NEW.valor);
        END IF;
    ELSE
        INSERT INTO bitacora_calificacion (calificacion_id, inscripcion_id, operacion, valor_anterior)
        VALUES (OLD.calificacion_id, OLD.inscripcion_id, 'D', OLD.valor);
    END IF;
    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_bitacora_calificacion
AFTER INSERT OR UPDATE OR DELETE ON calificacion
FOR EACH ROW EXECUTE FUNCTION fn_bitacora_calificacion();

-- 2.4 trg_tarea_notificar: una tarea nueva notifica a los inscritos.
CREATE OR REPLACE FUNCTION fn_tarea_notificar()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO notificacion (usuario_id, tipo, texto, referencia_id)
    SELECT a.usuario_id, 'tarea', left('Nueva tarea: ' || NEW.titulo, 255), NEW.tarea_id
    FROM inscripcion i JOIN alumno a ON a.alumno_id = i.alumno_id
    WHERE i.grupo_id = NEW.grupo_id AND i.estado = 'activa';
    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_tarea_notificar
AFTER INSERT ON tarea
FOR EACH ROW EXECUTE FUNCTION fn_tarea_notificar();

-- 2.5 trg_intento_validar: respeta la ventana del examen y el límite de
-- intentos; numera el intento solo.
CREATE OR REPLACE FUNCTION fn_intento_validar()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_examen  examen%ROWTYPE;
    v_previos INT;
BEGIN
    SELECT * INTO v_examen FROM examen WHERE examen_id = NEW.examen_id;

    IF NEW.iniciado_en NOT BETWEEN v_examen.abre_en AND v_examen.cierra_en THEN
        RAISE EXCEPTION 'El examen % no está abierto', NEW.examen_id USING ERRCODE = 'P0001';
    END IF;

    SELECT count(*) INTO v_previos FROM intento_examen
    WHERE examen_id = NEW.examen_id AND inscripcion_id = NEW.inscripcion_id;

    IF v_previos >= v_examen.intentos_max THEN
        RAISE EXCEPTION 'Se alcanzó el máximo de % intento(s)', v_examen.intentos_max
            USING ERRCODE = 'P0001';
    END IF;

    NEW.numero := v_previos + 1;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_intento_validar
BEFORE INSERT ON intento_examen
FOR EACH ROW EXECUTE FUNCTION fn_intento_validar();

-- 2.6 Shard key (fragmentación derivada, decisión 2 del equipo):
-- centro_academico_id se hereda solo del padre para que nunca quede
-- inconsistente: grupo <- materia/carrera, inscripcion <- grupo, y
-- calificacion, entrega y asistencia <- inscripcion. La API no lo manda.
CREATE OR REPLACE FUNCTION fn_heredar_centro()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_TABLE_NAME = 'grupo' THEN
        SELECT c.centro_academico_id INTO NEW.centro_academico_id
        FROM materia m JOIN carrera c ON c.carrera_id = m.carrera_id
        WHERE m.materia_id = NEW.materia_id;
    ELSIF TG_TABLE_NAME = 'inscripcion' THEN
        SELECT centro_academico_id INTO NEW.centro_academico_id
        FROM grupo WHERE grupo_id = NEW.grupo_id;
    ELSIF TG_TABLE_NAME IN ('calificacion', 'entrega', 'asistencia') THEN
        SELECT centro_academico_id INTO NEW.centro_academico_id
        FROM inscripcion WHERE inscripcion_id = NEW.inscripcion_id;
    END IF;
    RETURN NEW;   -- si el padre no existe, el NOT NULL / FK lo rechaza
END;
$$;

CREATE TRIGGER trg_grupo_centro
BEFORE INSERT OR UPDATE OF materia_id ON grupo
FOR EACH ROW EXECUTE FUNCTION fn_heredar_centro();

CREATE TRIGGER trg_inscripcion_centro
BEFORE INSERT OR UPDATE OF grupo_id ON inscripcion
FOR EACH ROW EXECUTE FUNCTION fn_heredar_centro();

CREATE TRIGGER trg_calificacion_centro
BEFORE INSERT OR UPDATE OF inscripcion_id ON calificacion
FOR EACH ROW EXECUTE FUNCTION fn_heredar_centro();

CREATE TRIGGER trg_entrega_centro
BEFORE INSERT OR UPDATE OF inscripcion_id ON entrega
FOR EACH ROW EXECUTE FUNCTION fn_heredar_centro();

CREATE TRIGGER trg_asistencia_centro
BEFORE INSERT OR UPDATE OF inscripcion_id ON asistencia
FOR EACH ROW EXECUTE FUNCTION fn_heredar_centro();

-- =====================================================================
-- 3. Procedimientos almacenados
-- =====================================================================

-- sp_inscribir_alumno: inscribe validando que
--   1) el grupo exista y tenga cupo (bloquea la fila del grupo para que
--      dos inscripciones simultáneas no rebasen el cupo),
--   2) el alumno no esté ya inscrito en esa materia en el periodo,
--   3) la materia sea de la carrera del alumno.
-- Además genera la notificación para el alumno.
CREATE OR REPLACE PROCEDURE sp_inscribir_alumno(
    p_alumno BIGINT,
    p_grupo  BIGINT,
    INOUT p_inscripcion BIGINT DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_cupo            SMALLINT;
    v_ocupados        INT;
    v_materia         INT;
    v_periodo         SMALLINT;
    v_carrera_materia INT;
    v_carrera_alumno  INT;
    v_usuario         BIGINT;
BEGIN
    SELECT g.cupo, g.materia_id, g.periodo_id, m.carrera_id
      INTO v_cupo, v_materia, v_periodo, v_carrera_materia
    FROM grupo g JOIN materia m ON m.materia_id = g.materia_id
    WHERE g.grupo_id = p_grupo
    FOR UPDATE OF g;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El grupo % no existe', p_grupo USING ERRCODE = 'P0002';
    END IF;

    SELECT carrera_id, usuario_id INTO v_carrera_alumno, v_usuario
    FROM alumno WHERE alumno_id = p_alumno;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El alumno % no existe', p_alumno USING ERRCODE = 'P0002';
    END IF;

    IF v_carrera_alumno <> v_carrera_materia THEN
        RAISE EXCEPTION 'La materia no pertenece a la carrera del alumno'
            USING ERRCODE = 'P0001';
    END IF;

    IF EXISTS (
        SELECT 1 FROM inscripcion i JOIN grupo g ON g.grupo_id = i.grupo_id
        WHERE i.alumno_id = p_alumno AND i.estado = 'activa'
          AND g.materia_id = v_materia AND g.periodo_id = v_periodo
    ) THEN
        RAISE EXCEPTION 'El alumno ya está inscrito en esta materia en el periodo'
            USING ERRCODE = 'P0001';
    END IF;

    SELECT count(*) INTO v_ocupados
    FROM inscripcion WHERE grupo_id = p_grupo AND estado = 'activa';

    IF v_ocupados >= v_cupo THEN
        RAISE EXCEPTION 'El grupo % no tiene cupo (%/%)', p_grupo, v_ocupados, v_cupo
            USING ERRCODE = 'P0001';
    END IF;

    INSERT INTO inscripcion (alumno_id, grupo_id)
    VALUES (p_alumno, p_grupo)
    RETURNING inscripcion_id INTO p_inscripcion;

    INSERT INTO notificacion (usuario_id, tipo, texto, referencia_id)
    VALUES (v_usuario, 'inscripcion', 'Quedaste inscrito en un nuevo grupo', p_grupo);
END;
$$;

-- sp_enviar_intento: cierra un intento de examen, lo califica y guarda el puntaje.
CREATE OR REPLACE PROCEDURE sp_enviar_intento(p_intento BIGINT, INOUT p_puntaje NUMERIC DEFAULT NULL)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE intento_examen
       SET enviado_en = now(),
           puntaje    = fn_calificar_intento(p_intento)
     WHERE intento_id = p_intento AND enviado_en IS NULL
    RETURNING puntaje INTO p_puntaje;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El intento % no existe o ya fue enviado', p_intento
            USING ERRCODE = 'P0001';
    END IF;
END;
$$;
