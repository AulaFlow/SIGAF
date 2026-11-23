# Generador de datos sintéticos (issue #10)

Llena el esquema `sigaf` con ~150 mil registros **ficticios** (nombres de Faker y
matrículas aleatorias que funcionan como seudónimos). Sirve para observar la
fragmentación, la replicación y el monitoreo con carga real.

## Uso

```bash
cd datos/generador
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PGPASSWORD=dev                       # la contraseña nunca va en el código
export SIGAF_LLAVE_DATOS="$(openssl rand -hex 32)"       # cifra nombre y apellidos
export SIGAF_LLAVE_SEUDONIMO="$(openssl rand -hex 32)"   # seudonimiza matrículas
python generar_datos.py --limpiar
```

Antes hay que crear el esquema (`db/01_tablas.sql`, `02_indices.sql`,
`03_funciones_triggers.sql` y `05_seguridad.sql`).

Las matrículas se guardan seudonimizadas (HMAC) y los nombres cifrados (AES-256).
**Guarda las dos llaves**: sin la misma `SIGAF_LLAVE_DATOS` no se pueden volver a leer
los nombres, y sin la misma `SIGAF_LLAVE_SEUDONIMO` un alumno no podría iniciar sesión.

| Opción | Default | Para qué |
|---|---|---|
| `--alumnos` | 1000 | Tamaño de la carga (1000 alumnos ≈ 150 mil registros) |
| `--semilla` | 2026 | Misma semilla = mismos datos |
| `--pesos` | 0.26 0.22 0.08 0.18 0.15 0.11 | Proporción de alumnos de cada centro |
| `--limpiar` | no | Vacía las tablas antes de generar |
| `--dsn` | `SIGAF_DSN` o `postgresql://postgres@localhost:5432/postgres` | Conexión |

Al final imprime los registros por tabla y el **conteo por centro** para decidir
el reparto de los fragmentos A y B. El script no llena `directorio_fragmento`:
esa decisión es del equipo.

Si algo falla, toda la carga se revierte (rollback) y la base queda como estaba.
