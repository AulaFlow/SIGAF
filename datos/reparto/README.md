# Reparto de datos en los fragmentos A y B (issue #8)

Llena la base distribuida con los datos sintéticos y deja **cada centro en su
fragmento**, como lo decidió el equipo:

| Fragmento | Centros | Puerta (HAProxy) |
|---|---|---|
| A | CCB (1), CCA (3), CCSH (5) | `haproxy:5432` primario, `haproxy:5433` réplica |
| B | CCEA (2), CCS (4), CCDC (6) | `haproxy:5434` primario, `haproxy:5435` réplica |

```
generador de Ricardo ──► fragmento A (6 centros) ──COPY──► fragmento B (centros 2, 4, 6)
                                   │
                                   └── DELETE de lo que ya está en B
```

## Qué hace

1. **Vacía** A y B y corre el generador (`datos/generador`) contra A: ~150 mil registros de los 6 centros.
2. **Copia** a B los catálogos y todo lo de CCEA, CCS y CCDC con `COPY ... (FORMAT BINARY)`, por bloques.
3. **Borra** de A lo que ya vive en B (hijos primero, por las llaves foráneas).
4. Llena **`directorio_fragmento`** en los dos fragmentos; de ahí lee el enrutador de la API (issue #6).
5. Ajusta los **contadores de id**: A sigue desde su máximo y B arranca en 1,000,000,000. Así un registro
   nuevo nunca tiene el mismo id en A y en B, y el ETL a MongoDB no los mezcla.
6. **Verifica**: lo que había en A = lo que quedó en A + lo que pasó a B. Si algo no cuadra, se detiene.

| Tipo de tabla | Tablas | Dónde queda |
|---|---|---|
| Replicadas (catálogos) | rol, usuario, centro_academico, carrera, periodo, materia, avisos generales, directorio_fragmento | En los dos |
| Fragmentadas por centro | profesor, alumno, alumno_datos_personales, grupo, horario, tarea, examen, pregunta, opcion, inscripcion, intento_examen, respuesta, calificacion, bitacora_calificacion, entrega, asistencia, avisos de grupo, notificacion | Solo en el fragmento de su centro |
| Fuera de alcance (Mensajería) | conversacion, participante_conversacion, mensaje | Solo en A |

Las reglas están en `reparto/plan.py`. Los triggers de la base siguen activos al copiar; por eso
`tarea` se copia antes que `inscripcion` (si no, se repetirían notificaciones) y la bitácora de
calificaciones se borra y se vuelve a copiar.

## Cómo correrlo

Necesita la base con Patroni arriba (`db/docker-compose.yml`, issue #9). En `db/.env` agrega las dos
llaves del generador (64 caracteres hexadecimales cada una, **guárdalas**: sin ellas no se pueden
leer los nombres ni iniciar sesión):

```bash
echo "SIGAF_LLAVE_DATOS=$(openssl rand -hex 32)" >> db/.env
echo "SIGAF_LLAVE_SEUDONIMO=$(openssl rand -hex 32)" >> db/.env
```

Desde la raíz del repo (en Git Bash):

```bash
docker build -t sigaf-reparto -f datos/reparto/Dockerfile datos
MSYS_NO_PATHCONV=1 docker run --rm --network sigaf_default -v sigaf_certs:/certs:ro \
    --env-file db/.env sigaf-reparto todo
```

Otros comandos: `generar`, `repartir`, `verificar` (muestra los alumnos, inscripciones y calificaciones
de cada centro en cada fragmento). Se conecta como `sigaf_dba` por TLS; la contraseña sale de
`SIGAF_PASS_ADMIN` en `db/.env`. Para las 4 laptops se cambian `SIGAF_DSN_A`, `SIGAF_DSN_B`,
`SIGAF_NODOS_A` y `SIGAF_NODOS_B`.

## Pruebas

```bash
cd datos/reparto
pip install -r requirements-dev.txt
pytest          # plan y reparto con conexiones falsas
```

Con los fragmentos reales (vacía A y B y los vuelve a llenar con 60 alumnos):

```bash
MSYS_NO_PATHCONV=1 docker run --rm --network sigaf_default -v sigaf_certs:/certs:ro --env-file db/.env \
    -e SIGAF_REPARTO_PRUEBAS=1 -v "$PWD":/app -w /app/datos/reparto --entrypoint sh sigaf-reparto \
    -c "pip install -q pytest pytest-cov && python -m pytest -q -p no:cacheprovider"
```

## Resultado (24 nov 2026, 1000 alumnos)

| Centro | Fragmento | Alumnos | Inscripciones | Calificaciones |
|---|---|---|---|---|
| CCB | A | 260 | 2,600 | 7,800 |
| CCA | A | 80 | 800 | 2,400 |
| CCSH | A | 150 | 1,500 | 4,500 |
| CCEA | B | 220 | 2,200 | 6,600 |
| CCS | B | 180 | 1,800 | 5,400 |
| CCDC | B | 110 | 1,100 | 3,300 |

A quedó con 490 alumnos y B con 510. Generar tardó ~10 s y repartir ~4 s. Los 25 conteos cuadraron.
