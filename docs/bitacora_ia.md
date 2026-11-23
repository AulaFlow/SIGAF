# Bitácora de uso de IA — SIGAF

Lineamientos, apartado 5.3. Solo se registran los usos que produjeron algo que se
integró al proyecto o que influyeron en una decisión.

| Fecha | Integrante | Herramienta | Propósito | Resultado (aceptado / modificado / descartado) | Verificación | Commit |
|---|---|---|---|---|---|---|
| 2026-11-22 | Angel Ricardo Figueroa Flores | Claude (chat) | Escribir el esquema relacional: tablas con PK, FK y CHECK, índices, vistas, funciones, triggers (`trg_recalcular_promedio`, `trg_estado_entrega`, `trg_bitacora_calificacion`) y el procedimiento `sp_inscribir_alumno` (issues #4 y #5). Nivel: con verificación. | **Aceptado:** el esquema y los triggers que pidió el profesor. **Modificado:** la situación académica pasó de tabla a vista (`v_situacion_academica`); se agregó `centro_academico_id` en grupo, inscripción y calificación. **Pendiente de decisión del equipo:** el reparto de centros en los fragmentos A y B que viene en `pruebas.sql` es solo una propuesta. | `db/pruebas.sql`: 11 pruebas con ASSERT en PostgreSQL 16 (Docker), todas pasan. Por ejemplo, parciales 8, 9 y 10 dan 9.00 y se recalcula al cambiar o borrar uno. Revisión de alex en el PR #2. | 462b6da, 626385f, e5c1706, 5b2635c |
| 2026-11-22 | Angel Ricardo Figueroa Flores | Claude (chat) | Escribir las consultas frecuentes con quién las hace, su frecuencia y si se quedan en un centro (sección 1, análisis de consultas). Nivel: con verificación. | **Aceptado:** 10 consultas en `db/04_consultas.sql`. 9 de 10 se resuelven en un solo centro; la consulta global (C10) se responde desde MongoDB. | Se corrieron contra los datos de `pruebas.sql` y contra los ~150 mil registros del generador; todas devuelven resultados. | ver PR #2 |
