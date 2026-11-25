# Análisis con MongoDB y gráficas (issues #14 y #15)

Copia indicadores de los fragmentos de PostgreSQL a MongoDB (ETL por lotes,
consistencia eventual) y genera las 3 gráficas que eligió el equipo con Matplotlib.

```
PostgreSQL fragmento A ─┐                       ┌─ 1_distribucion_calificaciones.png
                        ├─ ETL (sigaf_etl_svc) ─► MongoDB ─┼─ 2_promedio_por_materia.png
PostgreSQL fragmento B ─┘     solo lectura       └─ 3_entregas_a_tiempo_vs_tardias.png
```

## Colecciones

| Colección | `_id` | Qué guarda |
|---|---|---|
| `resumen_grupo` | `periodo:grupo_id` | alumnos, promedio, % aprobados y % asistencia por grupo |
| `actividad_alumno` | `periodo:alumno_id` | entregas a tiempo, tardías, no entregadas y faltas (sin datos personales) |
| `historico_calificaciones` | `calificacion_id` | cada calificación con materia, periodo, tipo y centro |

El `_id` es estable: volver a correr el ETL **reemplaza** los documentos, no los duplica.
El ETL usa la cuenta `sigaf_etl_svc`, que no puede leer nombres, usuarios ni mensajes.

## Diseño (POO)

- `modelos.py`: `Documento` (clase base abstracta) y sus subclases `ResumenGrupo`, `ActividadAlumno`, `RegistroCalificacion`.
- `fuentes.py`: `FuentePostgres`, un administrador de contexto (`with`) de solo lectura que lee por lotes con DB-API.
- `repositorio.py`: `RepositorioAnalitico` (interfaz) y `RepositorioMongo` (pymongo). El ETL y las gráficas dependen de la interfaz, no de pymongo.
- `etl.py`: `ProcesoETL` recorre los fragmentos y escribe en lotes; si un fragmento falla, lanza `ETLError` indicando cuál.
- `graficas.py`: `Grafica` (plantilla) y una subclase por gráfica (polimorfismo). Cada una define su consulta de agregación en MongoDB y cómo dibujarla.

## Uso

```bash
cd datos/analitica
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
docker run --name sigaf-mongo -p 27017:27017 -d mongo:7      # MongoDB local

export SIGAF_DSN="postgresql://sigaf_etl_svc@localhost:5432/postgres"
export PGPASSWORD=<contraseña de sigaf_etl_svc>
python -m analitica etl
python -m analitica graficas --periodo 2026-AGO-DIC          # PNG en graficas/
```

Con los dos fragmentos:
`export SIGAF_FRAGMENTOS="A=postgresql://sigaf_etl_svc@laptop1/postgres;B=postgresql://sigaf_etl_svc@laptop2/postgres"`

## Con Docker y los fragmentos reales A y B (issue #8)

MongoDB ya viene en `db/docker-compose.yml` (servicio `mongo`, con usuario `sigaf` y la
contraseña `SIGAF_PASS_MONGO` del `db/.env`; solo escucha en `127.0.0.1:27017`).
El contenedor del ETL lee A por `haproxy:5432` y B por `haproxy:5434`, con TLS (`verify-ca`).

```bash
cd db && docker compose up -d && cd ..                                   # Patroni + HAProxy + MongoDB
docker run --rm --network sigaf_default -v sigaf_certs:/certs:ro --env-file db/.env sigaf-reparto todo
docker build -t sigaf-analitica datos/analitica
docker run --rm --network sigaf_default -v sigaf_certs:/certs:ro --env-file db/.env sigaf-analitica etl
docker run --rm --network sigaf_default --env-file db/.env -v "$PWD/graficas:/app/graficas" \
    sigaf-analitica graficas --periodo 2026-AGO-DIC
```

En Git Bash (Windows) antepón `MSYS_NO_PATHCONV=1` a los `docker run`.

Resultado esperado con los datos del generador: `historico_calificaciones` = 30,000
(14,700 de A + 15,300 de B), los 6 centros presentes y el mismo promedio por centro que en
PostgreSQL. Volver a correr el ETL no duplica (reemplaza por `_id`).

Para la API: `SIGAF_MONGO_URI=mongodb://sigaf:<SIGAF_PASS_MONGO>@mongo:27017/?authSource=admin`.

## Pruebas

```bash
pytest     # ETL y gráficas con MongoDB en memoria (mongomock)

# además, ETL real desde PostgreSQL (tarda ~1 min por mongomock)
SIGAF_DSN_ETL_PRUEBAS="postgresql://sigaf_etl_svc@localhost:5432/postgres" PGPASSWORD=... pytest
```
