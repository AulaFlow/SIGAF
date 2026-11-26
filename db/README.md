# db

Scripts SQL (esquema, fragmentación, replicación, triggers), MongoDB y `docker-compose`.

## Orden de carga

`01_tablas` → `02_indices` → `03_funciones_triggers` → `05_seguridad` → `06_credenciales` → `07_margen_entrega` → `08_bitacora_acceso`.
`pruebas.sql` (P1–P14) y luego `pruebas_seguridad.sql` (S1–S10) se corren sobre una base recién cargada.

## Cuentas para probar el inicio de sesión (`pruebas.sql`, #11)

**Solo para bases de desarrollo y pruebas. Nunca cargues `pruebas.sql` en producción.**

Las 6 cuentas de `pruebas.sql` comparten esta contraseña de desarrollo:

```
sigaf-dev-NO-PRODUCCION
```

| Correo | Rol |
|---|---|
| `admin@sigaf.test` | administrador |
| `profe1@sigaf.test` | profesor |
| `alumno1@sigaf.test` … `alumno4@sigaf.test` | alumno |

```bash
curl -s -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" \
     -d '{"correo": "alumno1@sigaf.test", "contrasena": "sigaf-dev-NO-PRODUCCION"}'
```

- En la base van solo los hashes bcrypt (costo 12, una sal distinta por cuenta), no la contraseña.
- **No entran a propósito:** las cuentas del generador (`datos/generador`, hash `sintetico$...`), las que
  crea la limpieza (contraseña aleatoria que nadie conoce) y `profe2@sigaf.test` de `pruebas_seguridad.sql`.
  El login las rechaza con el mismo 401 y anota `hash_invalido` o `contrasena` en `bitacora_acceso`.
- Para crear el hash de otra cuenta de prueba (desde `api/`, con el `.venv` activo):
  `python -c "import bcrypt; print(bcrypt.hashpw(b'otra-de-prueba', bcrypt.gensalt(12)).decode())"`

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
