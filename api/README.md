# api

API de SIGAF con FastAPI (issue #7).

## Estructura

```
app/
  main.py              crear_app(): CORS, lifespan (abre/cierra el pool), rutas
  config.py            variables de entorno (nada de secretos en el código)
  dependencias.py      BD = conexión para las rutas (Depends)
  dominio/personas.py  Persona (abstracta) -> Alumno, Profesor, Administrador
  dominio/excepciones.py  errores de negocio (sin HTTP)
  datos/postgres.py    DB-API 2.0 (psycopg 3) + pool: una transacción por operación
  datos/errores.py     SQLSTATE de PostgreSQL -> excepción de negocio
  dominio/reglas.py    reglas puras (calificación 0-10, máx. 2 decimales)
  esquemas/            Pydantic: entrada con extra="forbid" y tipos estrictos; salida para OpenAPI
  repositorios/        el ÚNICO lugar con SQL (siempre con parámetros %s)
  servicios/           casos de uso por rol: alumno, profesor, inscripciones, estadísticas
  datos/mongo.py       lectura de MongoDB (pymongo): consultas y pipelines fijos
  rutas/               capa HTTP (#23): alumno, profesor, estadísticas; solo llaman servicios
  seguridad.py         usuario_actual() y requiere_rol() (login JWT del #11; hoy provisional)
scripts/exportar_openapi.py  genera openapi.json para la app de Flutter
```

### Estadísticas (MongoDB)

Lee lo que dejó el ETL de `datos/analitica` en `sigaf_analitica`
(consistencia **eventual**: cada respuesta trae `actualizado_en`).

| Servicio | Quién | Colección |
|---|---|---|
| `mi_actividad` | el alumno (solo la suya) | `actividad_alumno` |
| `resumen_de_grupo` | el profesor (solo sus grupos; se verifica en PostgreSQL) | `resumen_grupo` |
| `distribucion` (rangos 0–10) | profesor y administrador | `historico_calificaciones` |
| `promedio_por_materia` | profesor y administrador | `resumen_grupo` |
| `entregas_por_centro` | profesor y administrador | `actividad_alumno` |

Si MongoDB no responde, la API sigue funcionando y solo estas operaciones dan
`ServicioNoDisponibleError` (503).

Reglas que aplican los servicios:

- `alumno_id`, `profesor_id` y `centro_academico_id` salen del usuario autenticado (objeto `Alumno`/`Profesor`), nunca de la petición. El centro decide el fragmento (A o B) con el enrutador del #6; sin centro se usa el primer fragmento.
- El profesor solo ve y modifica SUS grupos; si no es suyo responde "no existe" (no revela datos ajenos).
- La entrega no recibe `entregada_en`: la pone la base y el trigger decide `a_tiempo`, `tardia` o `SG001`.
- Pendientes = tareas que todavía se pueden entregar (`cierre_entrega > now()`); `solo_tardia` avisa si ya pasó la fecha límite.
- Tarea sin `margen_tardia_horas` usa el DEFAULT de la base (48 h); con margen, 0 a 8760 h.

## Variables de entorno

Copia `.env.example` como `.env` (git lo ignora) y llénalo. La API entra
**siempre** como `sigaf_api_svc` y **siempre con TLS**, también en desarrollo
(decisión del equipo).

| Variable | Obligatoria | Uso |
|---|---|---|
| `SIGAF_PASS_API` | sí | Contraseña de `sigaf_api_svc` (12+ caracteres) |
| `SIGAF_LLAVE_DATOS` | sí | Llave AES-256 de datos personales (32+) |
| `SIGAF_LLAVE_SEUDONIMO` | sí | Llave HMAC de la matrícula (32+) |
| `SIGAF_DB_HOST` / `SIGAF_DB_PORT` / `SIGAF_DB_NOMBRE` | no | `localhost` / `5432` / `postgres` |
| `SIGAF_DB_SSLMODE` | no | `require` (default), `verify-ca` o `verify-full`. Nunca sin TLS |
| `SIGAF_DB_SSLROOTCERT` | con `verify-*` | Ruta a `ca.crt` de `infra/postgres/certs` |
| `SIGAF_DB_POOL_MAX` | no | Conexiones máximas del pool (default 10) |
| `SIGAF_MONGO_URI` / `SIGAF_MONGO_DB` | no | `mongodb://localhost:27017` / `sigaf_analitica` |
| `SIGAF_CORS_ORIGENES` | no | Orígenes del cliente web separados por coma (no se permite `*`) |

## Errores de la base y cómo se traducen

| SQLSTATE | Origen | Excepción |
|---|---|---|
| `SG001` | `trg_estado_entrega` (db/07): entrega después de `fecha_limite + margen_tardia` (48 h por defecto) | `EntregaFueraDeTiempoError` |
| `P0002` | registro inexistente en procedimientos | `NoEncontradoError` |
| `P0001` | reglas (`RAISE`); "ya está inscrito" | `InscripcionDuplicadaError` / `ReglaDeNegocioError` |
| `23505` | UNIQUE (en `inscripcion`) | `InscripcionDuplicadaError` / `RegistroDuplicadoError` |
| `23514` | CHECK de calificación / otros | `CalificacionInvalidaError` / `DatoInvalidoError` |
| otro | conexión, permisos, llaves | no se traduce: se deja pasar |

## Rutas HTTP (issue #23)

Cada ruta une la persona (`seguridad.py`), un servicio y sus esquemas. No hay SQL ni
consultas a MongoDB en `app/rutas/`. Documentación interactiva en `/docs`.

| Método y ruta | Servicio | Rol |
|---|---|---|
| `GET /alumno/datos` | `ServicioAlumno.mis_datos` | alumno |
| `GET /alumno/boleta` | `ServicioAlumno.boleta` | alumno |
| `GET /alumno/pendientes` | `ServicioAlumno.pendientes` | alumno |
| `GET /alumno/situacion` | `ServicioAlumno.situacion` | alumno |
| `POST /alumno/tareas/{tarea_id}/entregas` (201) | `ServicioAlumno.entregar` | alumno |
| `POST /alumno/inscripciones` (201) | `ServicioInscripciones.inscribir` | alumno |
| `GET /alumno/actividad` | `ServicioEstadisticas.mi_actividad` | alumno |
| `GET /profesor/grupos` | `ServicioProfesor.grupos` | profesor |
| `GET /profesor/grupos/{grupo_id}/alumnos` | `ServicioProfesor.alumnos_de_grupo` | profesor |
| `POST /profesor/grupos/{grupo_id}/tareas` (201) | `ServicioProfesor.crear_tarea` | profesor |
| `PUT /profesor/entregas/{entrega_id}/calificacion` | `ServicioProfesor.calificar_entrega` | profesor |
| `POST /profesor/calificaciones` (201) | `ServicioProfesor.registrar_calificacion` | profesor |
| `GET /profesor/grupos/{grupo_id}/resumen` | `ServicioEstadisticas.resumen_de_grupo` | profesor |
| `GET /estadisticas/distribucion?periodo=&tipo=` | `ServicioEstadisticas.distribucion` | profesor, admin |
| `GET /estadisticas/promedio-por-materia?periodo=&cuantas=` | `ServicioEstadisticas.promedio_por_materia` | profesor, admin |
| `GET /estadisticas/entregas-por-centro?periodo=` | `ServicioEstadisticas.entregas_por_centro` | profesor, admin |

- Sin token: **401**. Rol equivocado: **403** (se revisa antes de llamar al servicio).
- Ids en la URL: enteros positivos que caben en BIGINT; si no, **422**.
- Hasta que llegue el login del #11, `usuario_actual()` responde siempre 401: no hay usuario falso en la app.
- Contrato para la app: `python scripts/exportar_openapi.py` genera `api/openapi.json`.

## Correr

```bash
cd api
pip install -r requirements-dev.txt
uvicorn app.main:crear_app --factory --env-file .env --reload   # http://localhost:8000/docs
ruff check . && bandit -r app -c pyproject.toml && pip-audit -r requirements.txt && pytest
```

Las pruebas de `tests/test_integracion_postgres.py` usan la base real y se
omiten si no está definida `SIGAF_PASS_API` (por eso el CI no las corre).
Requieren `db/07_margen_entrega.sql` aplicado y TLS activo en `sigaf-db`:

```bash
set -a; source .env; set +a
pytest tests/test_integracion_postgres.py -v --no-cov
```
