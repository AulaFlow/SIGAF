-- =====================================================================
-- SIGAF · db/04_consultas.sql
-- Consultas frecuentes del sistema (sección 1 del documento: análisis de
-- consultas y patrones de acceso). De aquí sale la justificación de la
-- shard key: casi todas filtran, directa o indirectamente, por un solo
-- centro_academico_id.
--
-- Cada consulta indica:
--   Quién      rol que la ejecuta
--   Frecuencia estimación en temporada normal de clases
--   Centro     "1 centro" si todos los datos que toca viven en un solo
--              fragmento; "global" si cruza fragmentos
--
-- Los valores fijos (alumno 1, grupo 1, ...) son de ejemplo; en la API
-- llegan como parámetros (%s) para evitar inyección SQL.
-- Para probar: correr después de pruebas.sql o del generador.
-- =====================================================================
SET search_path TO sigaf, public;
-- Llave SOLO DE PRUEBA para descifrar nombres en C9 (la API usa la real)
SELECT set_config('sigaf.llave_datos', 'llave-de-prueba-datos-0123456789abcdef', false) \gset

-- C1. Horario del alumno
-- Quién: alumno · Frecuencia: muy alta (varias veces al día) · Centro: 1 centro
SELECT m.nombre AS materia, g.clave AS grupo, h.dia_semana, h.hora_inicio, h.hora_fin, h.aula
FROM inscripcion i
JOIN grupo g   ON g.grupo_id = i.grupo_id
JOIN materia m ON m.materia_id = g.materia_id
JOIN horario h ON h.grupo_id = g.grupo_id
JOIN periodo p ON p.periodo_id = g.periodo_id
WHERE i.alumno_id = 1 AND i.estado = 'activa'
  AND current_date BETWEEN p.fecha_inicio AND p.fecha_fin
ORDER BY h.dia_semana, h.hora_inicio;

-- C2. Tareas pendientes del alumno (más próximas primero)
-- Quién: alumno · Frecuencia: muy alta · Centro: 1 centro
-- Sigue pendiente mientras se pueda entregar: hasta fecha_limite + margen_tardia
-- (07_margen_entrega.sql). solo_tardia = ya pasó el límite, entra como tardía.
SELECT tarea_id, titulo, materia, fecha_limite, cierre_entrega,
       fecha_limite < now() AS solo_tardia
FROM v_pendientes_alumno
WHERE alumno_id = 1 AND cierre_entrega > now()
ORDER BY fecha_limite;

-- C3. Entregas por revisar del profesor
-- Quién: profesor · Frecuencia: alta (diaria) · Centro: 1 centro
SELECT t.titulo, a.matricula, e.entregada_en, e.estado, e.archivo_ruta
FROM entrega e
JOIN tarea t       ON t.tarea_id = e.tarea_id
JOIN grupo g       ON g.grupo_id = t.grupo_id
JOIN inscripcion i ON i.inscripcion_id = e.inscripcion_id
JOIN alumno a      ON a.alumno_id = i.alumno_id
WHERE g.profesor_id = 1 AND e.calificacion IS NULL
ORDER BY e.entregada_en;

-- C4. Registrar (o corregir) una calificación parcial
-- Quién: profesor · Frecuencia: media (al cierre de cada parcial, picos)
-- Centro: 1 centro · Escritura con consistencia fuerte. Los triggers
-- recalculan el promedio y dejan rastro en la bitácora.
INSERT INTO calificacion (inscripcion_id, tipo, valor)
VALUES (1, 'parcial3', 9.5)
ON CONFLICT (inscripcion_id, tipo) DO UPDATE SET valor = EXCLUDED.valor;

-- C5. Pasar lista de un grupo
-- Quién: profesor · Frecuencia: alta (cada clase) · Centro: 1 centro
INSERT INTO asistencia (inscripcion_id, fecha, estado)
SELECT i.inscripcion_id, current_date, 'presente'
FROM inscripcion i
WHERE i.grupo_id = 1 AND i.estado = 'activa'
ON CONFLICT (inscripcion_id, fecha) DO NOTHING;

-- C6. Avisos de los grupos del alumno + avisos generales
-- Quién: alumno · Frecuencia: muy alta · Centro: 1 centro (los generales
-- se replican a ambos fragmentos) · Consistencia eventual
SELECT av.titulo, av.publicado_en, coalesce(m.nombre, 'General') AS origen
FROM aviso av
LEFT JOIN grupo g   ON g.grupo_id = av.grupo_id
LEFT JOIN materia m ON m.materia_id = g.materia_id
WHERE av.grupo_id IS NULL
   OR av.grupo_id IN (SELECT grupo_id FROM inscripcion WHERE alumno_id = 1 AND estado = 'activa')
ORDER BY av.publicado_en DESC
LIMIT 20;

-- C7. Kardex / boleta del alumno
-- Quién: alumno, administrador · Frecuencia: media · Centro: 1 centro
SELECT materia_clave, materia, parcial1, parcial2, parcial3, promedio_parciales, final
FROM v_boleta
WHERE alumno_id = 1
ORDER BY materia_clave;

-- C8. Promedio y % de aprobados por grupo del profesor
-- Quién: profesor, coordinador · Frecuencia: baja (fin de parcial) · Centro: 1 centro
SELECT g.grupo_id, m.nombre AS materia, g.clave,
       count(i.inscripcion_id)                                        AS alumnos,
       round(avg(i.promedio_parciales), 2)                            AS promedio_grupo,
       round(100.0 * count(*) FILTER (WHERE i.promedio_parciales >= 6)
             / nullif(count(i.promedio_parciales), 0), 1)             AS pct_aprobados
FROM grupo g
JOIN materia m          ON m.materia_id = g.materia_id
LEFT JOIN inscripcion i ON i.grupo_id = g.grupo_id AND i.estado = 'activa'
WHERE g.profesor_id = 1
GROUP BY g.grupo_id, m.nombre, g.clave
ORDER BY g.grupo_id;

-- C9. Lista de alumnos de un grupo con nombre, promedio y asistencia
-- Quién: profesor · Frecuencia: alta · Centro: 1 centro
-- Los nombres están cifrados: solo se leen con fn_alumnos_de_profesor, que
-- devuelve únicamente alumnos de los grupos de ESE profesor (requiere la
-- llave de datos en la sesión).
SELECT p.apellidos, p.nombre, i.promedio_parciales,
       fn_porcentaje_asistencia(i.inscripcion_id) AS asistencia_pct
FROM fn_alumnos_de_profesor(1) p
JOIN inscripcion i ON i.alumno_id = p.alumno_id AND i.grupo_id = p.grupo_id
WHERE p.grupo_id = 1
ORDER BY p.apellidos, p.nombre;

-- C10. Promedio por centro académico (indicador institucional)
-- Quién: administrador · Frecuencia: baja (reportes) · Centro: GLOBAL
-- Cruza los dos fragmentos. Por eso esta consulta NO se hace sobre la
-- base relacional en producción: se responde desde MongoDB
-- (colección resumen_grupo), que se llena por lotes (consistencia eventual).
SELECT c.clave AS centro, d.fragmento,
       count(DISTINCT i.alumno_id)          AS alumnos,
       round(avg(i.promedio_parciales), 2)  AS promedio
FROM centro_academico c
LEFT JOIN directorio_fragmento d USING (centro_academico_id)   -- vacío = aún sin asignar
LEFT JOIN inscripcion i ON i.centro_academico_id = c.centro_academico_id
GROUP BY c.clave, d.fragmento
ORDER BY d.fragmento, c.clave;
