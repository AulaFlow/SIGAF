# Limpieza con pandas (issue #11)

Lee CSV "sucios" de alumnos y calificaciones, los limpia con pandas, deja un
reporte JSON de lo que se corrigió y lo que se descartó y, si se pide, los carga
a PostgreSQL en **una sola transacción** (commit si todo sale bien, rollback si no).

## Qué corrige y qué descarta

| Dato | Se corrige | Se descarta |
|---|---|---|
| Matrícula | espacios, guiones, minúsculas (`" a-000102 "` → `A000102`) | formato inválido, duplicada (se conserva la última) |
| Nombre y apellidos | espacios repetidos y mayúsculas (`GARCÍA  de la cruz` → `García de la Cruz`) | vacíos |
| Carrera, materia, periodo | mayúsculas y espacios | vacíos; carrera que no existe en la base (al cargar) |
| Semestre | — | fuera de 1 a 12 o no numérico |
| Tipo de calificación | `Parcial 1`, `P1`, `1er parcial` → `parcial1`; `Ordinario` → `final` | tipo desconocido |
| Calificación | coma decimal (`8,5`); entero de 11 a 100 como escala 0-100 (`95` → 9.5) | no numérica (`NP`), negativa, decimal mayor a 10 (`11.5`), mayor a 100 |

El reporte guarda solo el número de fila y el motivo: **no contiene datos personales**.
Al cargar, la matrícula se guarda seudonimizada (HMAC) y el nombre cifrado, con las
funciones de `db/05_seguridad.sql`; los triggers recalculan promedios y registran la bitácora.

## Uso

```bash
cd datos/limpieza
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Solo limpiar (no toca la base)
python -m limpieza --alumnos ejemplos/alumnos_sucio.csv \
                   --calificaciones ejemplos/calificaciones_sucio.csv

# Limpiar y cargar
export PGPASSWORD=dev SIGAF_DSN="postgresql://postgres@localhost:5432/postgres"
export SIGAF_LLAVE_DATOS=... SIGAF_LLAVE_SEUDONIMO=...   # las mismas que usa la base
python -m limpieza --alumnos ejemplos/alumnos_sucio.csv --cargar
```

## Pruebas

```bash
pytest          # limpieza y línea de comandos (cobertura mínima 60 %)

# además, carga real y rollback (base con db/01, 02, 03, 05 y pruebas.sql)
SIGAF_DSN_PRUEBAS="postgresql://postgres@localhost:5432/postgres" PGPASSWORD=dev pytest
```
