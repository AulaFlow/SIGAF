-- =====================================================================
-- SIGAF · db/07_margen_entrega.sql
-- Regla de negocio (decidida por Ricardo, 23 nov 2026):
--   entregas fuera de tiempo se aceptan como 'tardia' dentro de un margen
--   por tarea y se rechazan después.
--
--     entregada_en <= fecha_limite                        -> 'a_tiempo'
--     fecha_limite < entregada_en <= limite + margen      -> 'tardia'
--     entregada_en > fecha_limite + margen_tardia         -> RECHAZO (SG001)
--
-- Cambio trazable sobre 01 y 03 (que ya están en main): no los edita.
-- Re-ejecutable: se puede correr varias veces sin error ni pérdida de datos.
-- Orden de carga: 01 -> 02 -> 03 -> 05 -> 06 -> 07
-- =====================================================================
SET search_path TO sigaf;

-- ---------------------------------------------------------------------
-- 1. Margen por tarea (48 h por defecto)
-- En PostgreSQL 16, agregar una columna con DEFAULT constante NO reescribe
-- la tabla: las tareas existentes toman 48 h al instante.
-- El CHECK va dentro del ADD COLUMN, así que si la columna ya existe
-- se omite todo junto (por eso es re-ejecutable).
-- ---------------------------------------------------------------------
ALTER TABLE tarea
    ADD COLUMN IF NOT EXISTS margen_tardia INTERVAL NOT NULL DEFAULT interval '48 hours'
        CONSTRAINT chk_tarea_margen_tardia CHECK (margen_tardia >= interval '0');

COMMENT ON COLUMN tarea.margen_tardia IS
    'Tiempo después de fecha_limite en que una entrega aún se acepta como tardía. 0 = no se aceptan tardías.';

-- ---------------------------------------------------------------------
-- 2. Trigger de entrega: valida inscripción y ahora también el margen
-- fn_estado_entrega(entregada, limite) NO cambia: sigue decidiendo
-- a_tiempo / tardia. El rechazo ocurre antes de llamarla.
-- El trigger trg_estado_entrega (BEFORE INSERT OR UPDATE OF entregada_en)
-- tampoco cambia: solo se reemplaza la función que ejecuta.
--
-- SQLSTATE 'SG001': los códigos son 5 caracteres; las clases que empiezan
-- con 5-9 o I-Z quedan libres para cada implementación, así que 'SG'
-- no choca con ningún código del estándar ni de PostgreSQL (P0001 es el
-- genérico de RAISE). La API lo distingue con e.sqlstate == 'SG001'.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_trg_estado_entrega()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_limite TIMESTAMPTZ;
    v_margen INTERVAL;
BEGIN
    SELECT t.fecha_limite, t.margen_tardia INTO v_limite, v_margen
    FROM tarea t
    JOIN inscripcion i ON i.grupo_id = t.grupo_id
    WHERE t.tarea_id = NEW.tarea_id
      AND i.inscripcion_id = NEW.inscripcion_id
      AND i.estado = 'activa';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'La inscripción % no pertenece al grupo de la tarea %',
            NEW.inscripcion_id, NEW.tarea_id USING ERRCODE = 'P0001';
    END IF;

    IF NEW.entregada_en > v_limite + v_margen THEN
        RAISE EXCEPTION 'Entrega fuera de tiempo para la tarea %: se aceptaba hasta % (límite % + margen %)',
            NEW.tarea_id, v_limite + v_margen, v_limite, v_margen
            USING ERRCODE = 'SG001',
                  HINT = 'El margen de entrega tardía se configura por tarea en tarea.margen_tardia';
    END IF;

    NEW.estado := fn_estado_entrega(NEW.entregada_en, v_limite);
    RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------
-- 3. Pendientes del alumno: una tarea sigue "pendiente" mientras se pueda
-- entregar, o sea hasta fecha_limite + margen. Se agregan dos columnas al
-- final de la vista (CREATE OR REPLACE VIEW solo permite agregar al final;
-- los GRANT existentes se conservan).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_pendientes_alumno AS
SELECT i.alumno_id, t.tarea_id, t.titulo, m.nombre AS materia, t.fecha_limite,
       t.margen_tardia,
       t.fecha_limite + t.margen_tardia AS cierre_entrega
FROM inscripcion i
JOIN tarea t   ON t.grupo_id = i.grupo_id
JOIN grupo g   ON g.grupo_id = i.grupo_id
JOIN materia m ON m.materia_id = g.materia_id
LEFT JOIN entrega e ON e.tarea_id = t.tarea_id AND e.inscripcion_id = i.inscripcion_id
WHERE i.estado = 'activa' AND e.entrega_id IS NULL;
