-- =====================================================================
-- SIGAF · db/02_indices.sql
-- Índices para las consultas más frecuentes (sección 1 del documento).
-- Las PK y UNIQUE ya crean su propio índice y no se repiten aquí.
-- =====================================================================
SET search_path TO sigaf;

-- Navegación por la estructura académica
CREATE INDEX idx_carrera_centro        ON carrera (centro_academico_id);
CREATE INDEX idx_alumno_carrera        ON alumno (carrera_id);
CREATE INDEX idx_grupo_profesor        ON grupo (profesor_id, periodo_id);
CREATE INDEX idx_grupo_centro_periodo  ON grupo (centro_academico_id, periodo_id);
CREATE INDEX idx_horario_grupo         ON horario (grupo_id);

-- Horario y grupos del alumno; lista de alumnos de un grupo
CREATE INDEX idx_inscripcion_alumno    ON inscripcion (alumno_id) WHERE estado = 'activa';
CREATE INDEX idx_inscripcion_grupo     ON inscripcion (grupo_id)  WHERE estado = 'activa';
CREATE INDEX idx_inscripcion_centro    ON inscripcion (centro_academico_id);

-- Tareas pendientes del alumno y entregas por revisar del profesor
CREATE INDEX idx_tarea_grupo_limite    ON tarea (grupo_id, fecha_limite);
CREATE INDEX idx_entrega_inscripcion   ON entrega (inscripcion_id);
CREATE INDEX idx_entrega_sin_calificar ON entrega (tarea_id) WHERE calificacion IS NULL;

-- Exámenes por grupo e intentos por alumno
CREATE INDEX idx_examen_grupo          ON examen (grupo_id, abre_en);
CREATE INDEX idx_intento_inscripcion   ON intento_examen (inscripcion_id);

-- Calificaciones: por centro (fragmento) y bitácora por calificación
CREATE INDEX idx_calificacion_centro   ON calificacion (centro_academico_id, tipo);
CREATE INDEX idx_bitacora_calificacion ON bitacora_calificacion (calificacion_id, cambiado_en);

-- Pase de lista por fecha
CREATE INDEX idx_asistencia_fecha      ON asistencia (fecha);

-- Avisos recientes por grupo y mensajes de una conversación
CREATE INDEX idx_aviso_grupo_fecha     ON aviso (grupo_id, publicado_en DESC);
CREATE INDEX idx_mensaje_conv_fecha    ON mensaje (conversacion_id, enviado_en DESC);
CREATE INDEX idx_participante_usuario  ON participante_conversacion (usuario_id);

-- Contador de notificaciones sin leer (índice parcial)
CREATE INDEX idx_notif_no_leidas       ON notificacion (usuario_id, creada_en DESC)
    WHERE leida = FALSE;
