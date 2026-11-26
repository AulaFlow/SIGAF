-- =====================================================================
-- SIGAF · db/pruebas.sql
-- Datos FICTICIOS mínimos + pruebas de funciones, procedimiento y triggers.
-- Cada prueba usa ASSERT: si una regla no se cumple, el script se detiene.
--
-- Cómo correrlo (PostgreSQL 16 en Docker):
--   docker run --name sigaf-db -e POSTGRES_PASSWORD=dev -p 5432:5432 -d postgres:16
--   psql -h localhost -U postgres -v ON_ERROR_STOP=1 -f db/01_tablas.sql
--   psql -h localhost -U postgres -v ON_ERROR_STOP=1 -f db/02_indices.sql
--   psql -h localhost -U postgres -v ON_ERROR_STOP=1 -f db/03_funciones_triggers.sql
--   psql -h localhost -U postgres -v ON_ERROR_STOP=1 -f db/05_seguridad.sql
--   psql -h localhost -U postgres -v ON_ERROR_STOP=1 -f db/07_margen_entrega.sql
--   psql -h localhost -U postgres -v ON_ERROR_STOP=1 -f db/pruebas.sql
-- Para repetir desde cero:  DROP SCHEMA sigaf CASCADE;
-- =====================================================================
SET search_path TO sigaf, public;
-- Llaves SOLO DE PRUEBA (en el sistema real vienen de variables de entorno)
SELECT set_config('sigaf.llave_datos',     'llave-de-prueba-datos-0123456789abcdef', false),
       set_config('sigaf.llave_seudonimo', 'llave-de-prueba-seudonimo-0123456789ab', false) \gset
\echo '== Datos de prueba =='

INSERT INTO rol (nombre) VALUES ('alumno'), ('profesor'), ('administrador');

-- 6 centros académicos y su fragmento (reparto PROVISIONAL decidido por el
-- equipo: A = CCB, CCSH, CCA · B = CCEA, CCS, CCDC)
INSERT INTO centro_academico (clave, nombre) VALUES
    ('CCB',  'Centro de Ciencias Básicas'),
    ('CCEA', 'Centro de Ciencias Económicas y Administrativas'),
    ('CCA',  'Centro de Ciencias Agropecuarias'),
    ('CCS',  'Centro de Ciencias de la Salud'),
    ('CCSH', 'Centro de Ciencias Sociales y Humanidades'),
    ('CCDC', 'Centro de Ciencias del Diseño y de la Construcción');

INSERT INTO directorio_fragmento (centro_academico_id, fragmento, host_primario, host_replica) VALUES
    (1, 'A', 'laptop1:5432', 'laptop3:5432'),   -- CCB
    (2, 'B', 'laptop2:5432', 'laptop4:5432'),   -- CCEA
    (3, 'A', 'laptop1:5432', 'laptop3:5432'),   -- CCA
    (4, 'B', 'laptop2:5432', 'laptop4:5432'),   -- CCS
    (5, 'A', 'laptop1:5432', 'laptop3:5432'),   -- CCSH
    (6, 'B', 'laptop2:5432', 'laptop4:5432');   -- CCDC

INSERT INTO carrera (centro_academico_id, clave, nombre) VALUES
    (1, 'ISC', 'Ingeniería en Sistemas Computacionales'),
    (2, 'LAE', 'Licenciatura en Administración de Empresas');

INSERT INTO periodo (clave, fecha_inicio, fecha_fin) VALUES
    ('2026-AGO-DIC', '2026-08-10', '2026-12-18');

INSERT INTO materia (carrera_id, clave, nombre, creditos, semestre_sugerido) VALUES
    (1, 'ISC-701', 'Ingeniería de Datos I', 8, 7),
    (1, 'ISC-702', 'Programación Python', 8, 7),
    (2, 'LAE-301', 'Contabilidad de Costos', 6, 3);

-- Hashes bcrypt (costo 12, una sal por cuenta) de la contraseña de DESARROLLO
-- documentada en db/README.md, para probar POST /auth/login (#11).
-- Solo para bases de prueba: nunca cargar este archivo en producción.
INSERT INTO usuario (correo, hash_contrasena, rol_id) VALUES
    ('admin@sigaf.test',   '$2b$12$4EesZiPXjoJ/bULWxoNq/u2.FXEom6ur0j6MDguoCwCVJGyDehrEa', 3),
    ('profe1@sigaf.test',  '$2b$12$LPD4MTs307FxuizXC/MaA.xxehhmttT49OuETtQ4Cdjz1DaZhh.3m', 2),
    ('alumno1@sigaf.test', '$2b$12$AtjM.on52jo.J73Bmq9Oq.6BVXo0kLUrSqVCbQHLnlzJHOfqLAJOC', 1),
    ('alumno2@sigaf.test', '$2b$12$d07di.e/Q4OqTsAdu7SauupVp4I6agj//Co5g17smrrc5BJWVPYQa', 1),
    ('alumno3@sigaf.test', '$2b$12$o8is2POSUAbAJfc.BpUaQumDYTq2CukeYNH7DHFKpuanSe1MKoGoS', 1),
    ('alumno4@sigaf.test', '$2b$12$nrB1.vFIbVAEKvaBgKLihOl8/uvj.FylrNQP0X6rxxRljD0lwroS.', 1);

INSERT INTO profesor (usuario_id, centro_academico_id, num_empleado, nombre, apellidos) VALUES
    (2, 1, 'E-0001', 'Laura', 'Méndez Ruiz');

-- La matrícula se guarda seudonimizada (HMAC); la real no queda en la base
INSERT INTO alumno (usuario_id, carrera_id, matricula, semestre) VALUES
    (3, 1, fn_seudonimizar('A000001'), 7),
    (4, 1, fn_seudonimizar('A000002'), 7),
    (5, 2, fn_seudonimizar('A000003'), 3),
    (6, 1, fn_seudonimizar('A000004'), 7);

-- Fragmento vertical: datos personales aparte y cifrados
CALL sp_guardar_datos_personales(1, 'Diego',   'Pérez Luna');
CALL sp_guardar_datos_personales(2, 'Mariana', 'Soto Vega');
CALL sp_guardar_datos_personales(3, 'Iván',    'Ríos Campos');
CALL sp_guardar_datos_personales(4, 'Ana',     'Gil Mora');

-- centro_academico_id NO se manda: lo llena trg_grupo_centro
INSERT INTO grupo (materia_id, profesor_id, periodo_id, clave, cupo) VALUES
    (1, 1, 1, '7A', 2),     -- cupo chico para probar sobrecupo
    (1, 1, 1, '7B', 30),
    (2, 1, 1, '7A', 30);

INSERT INTO horario (grupo_id, dia_semana, hora_inicio, hora_fin, aula) VALUES
    (1, 1, '07:00', '09:00', 'B-101'),
    (1, 3, '07:00', '09:00', 'B-101');

\echo '== Pruebas =='

-- P1. sp_inscribir_alumno inscribe y notifica
DO $$
DECLARE v_ins BIGINT;
BEGIN
    CALL sp_inscribir_alumno(1, 1, v_ins);
    ASSERT v_ins IS NOT NULL, 'No devolvió inscripción';
    ASSERT (SELECT count(*) FROM notificacion WHERE usuario_id = 3 AND tipo = 'inscripcion') = 1,
        'No generó notificación';
    RAISE NOTICE 'P1 OK: inscripción % creada y notificada', v_ins;
END $$;

-- P2. Falla si ya está inscrito en la materia (aunque sea otro grupo)
DO $$
DECLARE v_ins BIGINT;
BEGIN
    CALL sp_inscribir_alumno(1, 2, v_ins);
    RAISE EXCEPTION 'P2 FALLÓ: permitió doble inscripción';
EXCEPTION WHEN raise_exception THEN
    IF SQLERRM LIKE 'P2 FALLÓ%' THEN RAISE; END IF;
    RAISE NOTICE 'P2 OK: rechazada -> %', SQLERRM;
END $$;

-- P3. Falla si no hay cupo (grupo 1 tiene cupo 2)
DO $$
DECLARE v_ins BIGINT;
BEGIN
    CALL sp_inscribir_alumno(2, 1, v_ins);   -- 2/2, grupo lleno
    BEGIN
        CALL sp_inscribir_alumno(4, 1, v_ins);  -- tercer alumno
        RAISE EXCEPTION 'P3 FALLÓ: permitió sobrecupo';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'P3 FALLÓ%' THEN RAISE; END IF;
        RAISE NOTICE 'P3 OK: rechazada -> %', SQLERRM;
    END;
END $$;

-- P4. Falla si la materia es de otra carrera
DO $$
DECLARE v_ins BIGINT;
BEGIN
    CALL sp_inscribir_alumno(3, 1, v_ins);
    RAISE EXCEPTION 'P4 FALLÓ: inscribió a alumno de otra carrera';
EXCEPTION WHEN raise_exception THEN
    IF SQLERRM LIKE 'P4 FALLÓ%' THEN RAISE; END IF;
    RAISE NOTICE 'P4 OK: rechazada -> %', SQLERRM;
END $$;

-- P5. Shard key heredada sola: grupo, inscripción y calificación quedan en el centro 1
DO $$
BEGIN
    ASSERT (SELECT centro_academico_id FROM grupo WHERE grupo_id = 1) = 1, 'grupo sin centro';
    ASSERT (SELECT centro_academico_id FROM inscripcion WHERE inscripcion_id = 1) = 1, 'inscripción sin centro';
    RAISE NOTICE 'P5 OK: centro_academico_id heredado en grupo e inscripción';
END $$;

-- P6. trg_recalcular_promedio: 8, 9, 10 -> 9.00; al cambiar uno se actualiza
DO $$
DECLARE v NUMERIC;
BEGIN
    INSERT INTO calificacion (inscripcion_id, tipo, valor) VALUES
        (1, 'parcial1', 8), (1, 'parcial2', 9), (1, 'parcial3', 10);
    SELECT promedio_parciales INTO v FROM inscripcion WHERE inscripcion_id = 1;
    ASSERT v = 9.00, 'Esperaba 9.00 y quedó ' || coalesce(v::text, 'NULL');
    RAISE NOTICE 'P6a OK: parciales 8, 9, 10 -> promedio %', v;

    UPDATE calificacion SET valor = 7 WHERE inscripcion_id = 1 AND tipo = 'parcial3';
    SELECT promedio_parciales INTO v FROM inscripcion WHERE inscripcion_id = 1;
    ASSERT v = 8.00, 'Esperaba 8.00 y quedó ' || coalesce(v::text, 'NULL');
    RAISE NOTICE 'P6b OK: parcial3 de 10 a 7 -> promedio %', v;

    DELETE FROM calificacion WHERE inscripcion_id = 1 AND tipo = 'parcial3';
    SELECT promedio_parciales INTO v FROM inscripcion WHERE inscripcion_id = 1;
    ASSERT v = 8.50, 'Esperaba 8.50 y quedó ' || coalesce(v::text, 'NULL');
    RAISE NOTICE 'P6c OK: se borra parcial3 -> promedio %', v;

    ASSERT (SELECT centro_academico_id FROM calificacion WHERE inscripcion_id = 1 LIMIT 1) = 1,
        'calificación sin centro';
    RAISE NOTICE 'P6d OK: la calificación heredó centro_academico_id';
END $$;

-- P7. trg_bitacora_calificacion: 3 altas, 1 cambio (10 -> 7) y 1 baja
DO $$
BEGIN
    ASSERT (SELECT count(*) FROM bitacora_calificacion WHERE inscripcion_id = 1 AND operacion = 'I') = 3, 'altas';
    ASSERT (SELECT count(*) FROM bitacora_calificacion
            WHERE operacion = 'U' AND valor_anterior = 10 AND valor_nuevo = 7) = 1, 'cambio';
    ASSERT (SELECT count(*) FROM bitacora_calificacion WHERE operacion = 'D') = 1, 'baja';
    RAISE NOTICE 'P7 OK: bitácora con 3 altas, 1 cambio y 1 baja';
END $$;

-- P8. trg_tarea_notificar + trg_estado_entrega (tardía y a tiempo)
DO $$
DECLARE v_estado VARCHAR;
BEGIN
    INSERT INTO tarea (grupo_id, titulo, publicada_en, fecha_limite) VALUES
        (1, 'Práctica 1: esquema ER', now() - interval '3 days', now() - interval '1 day'),
        (1, 'Práctica 2: triggers',   now() - interval '1 day',  now() + interval '2 days');
    ASSERT (SELECT count(*) FROM notificacion WHERE tipo = 'tarea') = 4,
        'Debió notificar 2 tareas a 2 alumnos';
    RAISE NOTICE 'P8a OK: 2 tareas notificadas a los 2 inscritos';

    INSERT INTO entrega (tarea_id, inscripcion_id) VALUES (1, 1) RETURNING estado INTO v_estado;
    ASSERT v_estado = 'tardia', 'Debió ser tardía, quedó ' || v_estado;
    INSERT INTO entrega (tarea_id, inscripcion_id, archivo_ruta, archivo_tamano_bytes, archivo_tipo)
    VALUES (2, 1, 'entregas/2/1/practica2.pdf', 204800, 'application/pdf')
    RETURNING estado INTO v_estado;
    ASSERT v_estado = 'a_tiempo', 'Debió ser a tiempo, quedó ' || v_estado;
    RAISE NOTICE 'P8b OK: una entrega tardía y una a tiempo, marcadas solas';
END $$;

-- P9. Alguien que no está en el grupo no puede entregar
DO $$
DECLARE v_ins BIGINT;
BEGIN
    CALL sp_inscribir_alumno(4, 2, v_ins);             -- Ana en el grupo 7B
    INSERT INTO entrega (tarea_id, inscripcion_id) VALUES (1, v_ins);
    RAISE EXCEPTION 'P9 FALLÓ: aceptó entrega de otro grupo';
EXCEPTION WHEN raise_exception THEN
    IF SQLERRM LIKE 'P9 FALLÓ%' THEN RAISE; END IF;
    RAISE NOTICE 'P9 OK: rechazada -> %', SQLERRM;
END $$;

-- P10. Examen: se califica solo y respeta el límite de intentos
DO $$
DECLARE v_intento BIGINT; v_puntaje NUMERIC;
BEGIN
    INSERT INTO examen (grupo_id, titulo, abre_en, cierra_en, intentos_max)
    VALUES (1, 'Examen U1', now() - interval '1 hour', now() + interval '1 hour', 1);
    INSERT INTO pregunta (examen_id, enunciado, puntos) VALUES (1, '¿Qué es una PK?', 1), (1, '¿Qué es 3FN?', 1);
    INSERT INTO opcion (pregunta_id, texto, es_correcta) VALUES
        (1, 'Identificador único', TRUE), (1, 'Un índice cualquiera', FALSE),
        (2, 'Sin dependencias transitivas', TRUE), (2, 'Sin llaves', FALSE);

    INSERT INTO intento_examen (examen_id, inscripcion_id, numero) VALUES (1, 1, 1)
    RETURNING intento_id INTO v_intento;
    INSERT INTO respuesta (intento_id, pregunta_id, opcion_id) VALUES (v_intento, 1, 1), (v_intento, 2, 4);
    CALL sp_enviar_intento(v_intento, v_puntaje);
    ASSERT v_puntaje = 5.00, 'Esperaba 5.00 y quedó ' || v_puntaje;
    RAISE NOTICE 'P10a OK: 1 de 2 correctas -> %', v_puntaje;

    BEGIN
        INSERT INTO intento_examen (examen_id, inscripcion_id, numero) VALUES (1, 1, 1);
        RAISE EXCEPTION 'P10 FALLÓ: permitió un segundo intento';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'P10 FALLÓ%' THEN RAISE; END IF;
        RAISE NOTICE 'P10b OK: rechazado -> %', SQLERRM;
    END;
END $$;

-- P11. v_situacion_academica cuenta solo finales validadas
DO $$
BEGIN
    INSERT INTO calificacion (inscripcion_id, tipo, valor, validada) VALUES (1, 'final', 9, TRUE);
    INSERT INTO calificacion (inscripcion_id, tipo, valor, validada) VALUES (2, 'final', 5, FALSE);
    ASSERT (SELECT materias_aprobadas FROM v_situacion_academica WHERE alumno_id = 1) = 1, 'aprobadas';
    ASSERT (SELECT creditos_aprobados FROM v_situacion_academica WHERE alumno_id = 1) = 8, 'créditos';
    ASSERT (SELECT materias_reprobadas FROM v_situacion_academica WHERE alumno_id = 2) = 0,
        'contó una final no validada';
    RAISE NOTICE 'P11 OK: situación académica correcta (no cuenta finales sin validar)';
END $$;

-- P12. Fragmentación derivada: entrega y asistencia heredan el centro de su inscripción
DO $$
BEGIN
    INSERT INTO asistencia (inscripcion_id, fecha, estado) VALUES (1, current_date, 'presente');
    ASSERT NOT EXISTS (
        SELECT 1 FROM entrega e JOIN inscripcion i USING (inscripcion_id)
        WHERE e.centro_academico_id IS DISTINCT FROM i.centro_academico_id), 'entrega con otro centro';
    ASSERT NOT EXISTS (
        SELECT 1 FROM asistencia s JOIN inscripcion i USING (inscripcion_id)
        WHERE s.centro_academico_id IS DISTINCT FROM i.centro_academico_id), 'asistencia con otro centro';
    ASSERT (SELECT count(*) FROM entrega WHERE centro_academico_id = 1) = 2, 'faltan entregas en el centro 1';
    RAISE NOTICE 'P12 OK: entrega y asistencia quedan en el mismo fragmento que su inscripción';
END $$;

-- P13. Fragmentación vertical: alumno ya no guarda nombre; los datos personales van aparte (1 a 1)
DO $$
BEGIN
    ASSERT NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_schema = 'sigaf' AND table_name = 'alumno'
                         AND column_name IN ('nombre', 'apellidos')), 'alumno todavía tiene nombre';
    ASSERT (SELECT count(*) FROM alumno) = (SELECT count(*) FROM alumno_datos_personales),
        'no todos los alumnos tienen datos personales';
    ASSERT (SELECT apellidos FROM fn_datos_alumno(1)) = 'Pérez Luna', 'no se pudo descifrar';
    RAISE NOTICE 'P13 OK: datos personales separados de los académicos (y cifrados)';
END $$;

-- P14. Margen de entrega tardía (db/07_margen_entrega.sql, regla del 23 nov 2026)
--      a tiempo / tardía dentro del margen / rechazo SG001 / margen 0 / filas viejas
DO $$
DECLARE
    v_estado VARCHAR;
    t_ok BIGINT; t_tarde BIGINT; t_fuera BIGINT; t_cero BIGINT; t_vieja BIGINT;
BEGIN
    INSERT INTO tarea (grupo_id, titulo, publicada_en, fecha_limite)
    VALUES (1, 'P14 a tiempo', now() - interval '5 days', now() + interval '1 day')
    RETURNING tarea_id INTO t_ok;
    INSERT INTO tarea (grupo_id, titulo, publicada_en, fecha_limite)
    VALUES (1, 'P14 tardía', now() - interval '5 days', now() - interval '47 hours')
    RETURNING tarea_id INTO t_tarde;
    INSERT INTO tarea (grupo_id, titulo, publicada_en, fecha_limite)
    VALUES (1, 'P14 fuera', now() - interval '5 days', now() - interval '49 hours')
    RETURNING tarea_id INTO t_fuera;
    INSERT INTO tarea (grupo_id, titulo, publicada_en, fecha_limite, margen_tardia)
    VALUES (1, 'P14 margen 0', now() - interval '5 days', now() - interval '1 minute', interval '0')
    RETURNING tarea_id INTO t_cero;
    INSERT INTO tarea (grupo_id, titulo, publicada_en, fecha_limite)
    VALUES (1, 'P14 fila vieja', now() - interval '5 days', now() - interval '3 days')
    RETURNING tarea_id INTO t_vieja;

    ASSERT (SELECT margen_tardia FROM tarea WHERE tarea_id = t_ok) = interval '48 hours',
        'El margen por defecto debió ser 48 h';

    -- a) antes del límite
    INSERT INTO entrega (tarea_id, inscripcion_id) VALUES (t_ok, 1) RETURNING estado INTO v_estado;
    ASSERT v_estado = 'a_tiempo', 'a) debió ser a_tiempo, quedó ' || v_estado;

    -- b) 47 h tarde, dentro de las 48 h
    INSERT INTO entrega (tarea_id, inscripcion_id) VALUES (t_tarde, 1) RETURNING estado INTO v_estado;
    ASSERT v_estado = 'tardia', 'b) debió ser tardia, quedó ' || v_estado;

    -- c) 49 h tarde: la base la rechaza con SG001
    BEGIN
        INSERT INTO entrega (tarea_id, inscripcion_id) VALUES (t_fuera, 1);
        RAISE EXCEPTION 'P14c FALLÓ: aceptó una entrega fuera del margen';
    EXCEPTION WHEN SQLSTATE 'SG001' THEN
        RAISE NOTICE 'P14c rechazo -> %', SQLERRM;
    END;

    -- d) margen 0: un minuto tarde ya se rechaza
    BEGIN
        INSERT INTO entrega (tarea_id, inscripcion_id) VALUES (t_cero, 1);
        RAISE EXCEPTION 'P14d FALLÓ: con margen 0 aceptó una entrega tarde';
    EXCEPTION WHEN SQLSTATE 'SG001' THEN NULL;
    END;
    -- ...pero justo en el límite sí entra, como a tiempo
    INSERT INTO entrega (tarea_id, inscripcion_id, entregada_en)
    VALUES (t_cero, 1, (SELECT fecha_limite FROM tarea WHERE tarea_id = t_cero))
    RETURNING estado INTO v_estado;
    ASSERT v_estado = 'a_tiempo', 'd) en el límite exacto debió ser a_tiempo';

    -- e) el margen no acepta valores negativos
    BEGIN
        UPDATE tarea SET margen_tardia = interval '-1 hour' WHERE tarea_id = t_ok;
        RAISE EXCEPTION 'P14e FALLÓ: aceptó un margen negativo';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    -- f) filas ya existentes: el trigger solo revisa INSERT y UPDATE de entregada_en.
    --    Simulamos una entrega vieja (72 h tarde, aceptada con un margen mayor)
    UPDATE tarea SET margen_tardia = interval '5 days' WHERE tarea_id = t_vieja;
    INSERT INTO entrega (tarea_id, inscripcion_id) VALUES (t_vieja, 1);
    UPDATE tarea SET margen_tardia = interval '48 hours' WHERE tarea_id = t_vieja;
    UPDATE entrega SET calificacion = 8.5, retroalimentacion = 'Bien'      -- no toca entregada_en
    WHERE tarea_id = t_vieja AND inscripcion_id = 1;
    BEGIN
        UPDATE entrega SET entregada_en = now() WHERE tarea_id = t_vieja AND inscripcion_id = 1;
        RAISE EXCEPTION 'P14f FALLÓ: un UPDATE de entregada_en fuera del margen pasó';
    EXCEPTION WHEN SQLSTATE 'SG001' THEN NULL;
    END;

    -- g) pendientes: la tarea sigue visible hasta límite + margen
    ASSERT EXISTS (SELECT 1 FROM v_pendientes_alumno
                   WHERE tarea_id = t_fuera AND cierre_entrega = fecha_limite + margen_tardia),
        'g) la vista de pendientes no trae cierre_entrega';

    RAISE NOTICE 'P14 OK: a tiempo, tardía en 48 h, rechazo SG001, margen 0, CHECK y filas viejas intactas';
END $$;

\echo '== Todas las pruebas pasaron =='

-- Resultados para la captura del documento
\echo '-- Boleta (promedio_parciales lo mantiene el trigger)'
SELECT inscripcion_id, materia, parcial1, parcial2, parcial3, promedio_parciales, final FROM v_boleta ORDER BY 1;
\echo '-- Bitácora de calificaciones'
SELECT bitacora_id, calificacion_id, operacion, valor_anterior, valor_nuevo, cambiado_en::time(0)
FROM bitacora_calificacion ORDER BY 1;
\echo '-- Situación académica'
SELECT * FROM v_situacion_academica ORDER BY alumno_id;
\echo '-- Directorio de fragmentos (reparto provisional del equipo)'
SELECT d.centro_academico_id, c.clave, d.fragmento, d.host_primario, d.host_replica
FROM directorio_fragmento d JOIN centro_academico c USING (centro_academico_id) ORDER BY 1;
