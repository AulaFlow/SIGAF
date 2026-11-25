# db

Scripts SQL (esquema, fragmentación, replicación, triggers), MongoDB y `docker-compose`.

## Orden de carga

`01_tablas` → `02_indices` → `03_funciones_triggers` → `05_seguridad` → `06_credenciales` → `07_margen_entrega`.
`pruebas.sql` (P1–P14) y luego `pruebas_seguridad.sql` (S1–S9) se corren sobre una base recién cargada.

## Regla: margen de entrega tardía (`07_margen_entrega.sql`)

Decisión de negocio de Ricardo, 23 nov 2026. Cada tarea tiene `margen_tardia` (48 h por defecto, 0 = sin tardías):

| Momento de la entrega | Resultado |
|---|---|
| `entregada_en <= fecha_limite` | `a_tiempo` |
| hasta `fecha_limite + margen_tardia` | `tardia` |
| después | rechazada con SQLSTATE `SG001` (la API responde 409) |

- Lo aplica el trigger `trg_estado_entrega` en INSERT y en UPDATE de `entregada_en`; las filas existentes no se revisan.
- `v_pendientes_alumno` trae `cierre_entrega`: una tarea sigue pendiente hasta límite + margen (consulta C2).
- `07` es re-ejecutable y no edita 01 ni 03.
