-- =====================================================================
-- SIGAF · db/01_tablas.sql
-- Tablas con PK, FK, CHECK y UNIQUE (PostgreSQL 16), más las vistas.
-- Forma normal objetivo: 3FN. Redundancias intencionales:
--   * centro_academico_id copiado en grupo, inscripcion y calificacion:
--     es la shard key; así cada fila sabe a qué fragmento pertenece sin
--     hacer JOIN (se llena sola por trigger, ver 03).
--   * inscripcion.promedio_parciales: lo mantiene trg_recalcular_promedio.
-- Orden de ejecución: 01_tablas -> 02_indices -> 03_funciones_triggers
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS sigaf;
SET search_path TO sigaf;

-- ---------------------------------------------------------------------
-- Usuarios y roles
-- ---------------------------------------------------------------------
CREATE TABLE rol (
    rol_id      SMALLSERIAL PRIMARY KEY,
    nombre      VARCHAR(20) NOT NULL UNIQUE
                CHECK (nombre IN ('alumno', 'profesor', 'administrador'))
);

CREATE TABLE usuario (
    usuario_id       BIGSERIAL PRIMARY KEY,
    correo           VARCHAR(120) NOT NULL UNIQUE
                     CHECK (correo ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    hash_contrasena  VARCHAR(255) NOT NULL,
    rol_id           SMALLINT NOT NULL REFERENCES rol (rol_id),
    activo           BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Estructura académica
-- ---------------------------------------------------------------------
CREATE TABLE centro_academico (
    centro_academico_id  SMALLSERIAL PRIMARY KEY,
    clave                VARCHAR(10) NOT NULL UNIQUE,
    nombre               VARCHAR(120) NOT NULL
);

-- Directorio de fragmentos: a qué fragmento (y a qué nodos) va cada
-- centro. Lo consulta el enrutador de la API para saber a dónde conectar.
CREATE TABLE directorio_fragmento (
    centro_academico_id  SMALLINT PRIMARY KEY
                         REFERENCES centro_academico (centro_academico_id),
    fragmento            CHAR(1) NOT NULL CHECK (fragmento IN ('A', 'B')),
    host_primario        TEXT NOT NULL,          -- endpoint de Patroni del primario
    host_replica         TEXT NOT NULL,          -- endpoint de la réplica
    actualizado_en       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE carrera (
    carrera_id           SERIAL PRIMARY KEY,
    centro_academico_id  SMALLINT NOT NULL REFERENCES centro_academico (centro_academico_id),
    clave                VARCHAR(10) NOT NULL UNIQUE,
    nombre               VARCHAR(120) NOT NULL
);

CREATE TABLE periodo (
    periodo_id    SMALLSERIAL PRIMARY KEY,
    clave         VARCHAR(20) NOT NULL UNIQUE,          -- p. ej. 2026-AGO-DIC
    fecha_inicio  DATE NOT NULL,
    fecha_fin     DATE NOT NULL,
    CHECK (fecha_fin > fecha_inicio)
);

CREATE TABLE materia (
    materia_id         SERIAL PRIMARY KEY,
    carrera_id         INT NOT NULL REFERENCES carrera (carrera_id),
    clave              VARCHAR(15) NOT NULL UNIQUE,
    nombre             VARCHAR(120) NOT NULL,
    creditos           SMALLINT NOT NULL CHECK (creditos > 0),
    semestre_sugerido  SMALLINT CHECK (semestre_sugerido BETWEEN 1 AND 12)
);

CREATE TABLE alumno (
    alumno_id    BIGSERIAL PRIMARY KEY,
    usuario_id   BIGINT NOT NULL UNIQUE REFERENCES usuario (usuario_id),
    carrera_id   INT NOT NULL REFERENCES carrera (carrera_id),
    matricula    VARCHAR(12) NOT NULL UNIQUE,            -- sintética / seudonimizada
    nombre       VARCHAR(80) NOT NULL,
    apellidos    VARCHAR(120) NOT NULL,
    semestre     SMALLINT NOT NULL CHECK (semestre BETWEEN 1 AND 12)
);

CREATE TABLE profesor (
    profesor_id          BIGSERIAL PRIMARY KEY,
    usuario_id           BIGINT NOT NULL UNIQUE REFERENCES usuario (usuario_id),
    centro_academico_id  SMALLINT NOT NULL REFERENCES centro_academico (centro_academico_id),
    num_empleado         VARCHAR(12) NOT NULL UNIQUE,
    nombre               VARCHAR(80) NOT NULL,
    apellidos            VARCHAR(120) NOT NULL
);

CREATE TABLE grupo (
    grupo_id             BIGSERIAL PRIMARY KEY,
    materia_id           INT NOT NULL REFERENCES materia (materia_id),
    profesor_id          BIGINT NOT NULL REFERENCES profesor (profesor_id),
    periodo_id           SMALLINT NOT NULL REFERENCES periodo (periodo_id),
    centro_academico_id  SMALLINT NOT NULL REFERENCES centro_academico (centro_academico_id),
    clave                VARCHAR(5) NOT NULL,            -- p. ej. 7A
    cupo                 SMALLINT NOT NULL CHECK (cupo > 0),
    UNIQUE (materia_id, periodo_id, clave)
);

CREATE TABLE horario (
    horario_id   BIGSERIAL PRIMARY KEY,
    grupo_id     BIGINT NOT NULL REFERENCES grupo (grupo_id) ON DELETE CASCADE,
    dia_semana   SMALLINT NOT NULL CHECK (dia_semana BETWEEN 1 AND 7),
    hora_inicio  TIME NOT NULL,
    hora_fin     TIME NOT NULL,
    aula         VARCHAR(20),
    CHECK (hora_fin > hora_inicio)
);

CREATE TABLE inscripcion (
    inscripcion_id       BIGSERIAL PRIMARY KEY,
    alumno_id            BIGINT NOT NULL REFERENCES alumno (alumno_id),
    grupo_id             BIGINT NOT NULL REFERENCES grupo (grupo_id),
    centro_academico_id  SMALLINT NOT NULL REFERENCES centro_academico (centro_academico_id),
    inscrito_en          TIMESTAMPTZ NOT NULL DEFAULT now(),
    estado               VARCHAR(10) NOT NULL DEFAULT 'activa'
                         CHECK (estado IN ('activa', 'baja')),
    promedio_parciales   NUMERIC(4, 2) CHECK (promedio_parciales BETWEEN 0 AND 10),
    UNIQUE (alumno_id, grupo_id)
);

-- ---------------------------------------------------------------------
-- Tareas y entregas
-- ---------------------------------------------------------------------
CREATE TABLE tarea (
    tarea_id      BIGSERIAL PRIMARY KEY,
    grupo_id      BIGINT NOT NULL REFERENCES grupo (grupo_id),
    titulo        VARCHAR(150) NOT NULL,
    descripcion   TEXT,
    publicada_en  TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_limite  TIMESTAMPTZ NOT NULL,
    CHECK (fecha_limite > publicada_en)
);

-- El archivo NO se guarda en la base: solo sus metadatos. El archivo vive
-- en el almacenamiento de la API (carpeta o bucket) en archivo_ruta.
CREATE TABLE entrega (
    entrega_id            BIGSERIAL PRIMARY KEY,
    tarea_id              BIGINT NOT NULL REFERENCES tarea (tarea_id),
    inscripcion_id        BIGINT NOT NULL REFERENCES inscripcion (inscripcion_id),
    entregada_en          TIMESTAMPTZ NOT NULL DEFAULT now(),
    archivo_ruta          VARCHAR(255),
    archivo_tamano_bytes  BIGINT CHECK (archivo_tamano_bytes BETWEEN 1 AND 52428800), -- máx. 50 MB
    archivo_tipo          VARCHAR(100),          -- MIME, p. ej. application/pdf
    estado                VARCHAR(10) NOT NULL DEFAULT 'a_tiempo'
                          CHECK (estado IN ('a_tiempo', 'tardia')),
    calificacion          NUMERIC(4, 2) CHECK (calificacion BETWEEN 0 AND 10),
    retroalimentacion     TEXT,
    UNIQUE (tarea_id, inscripcion_id),
    CHECK ((archivo_ruta IS NULL) = (archivo_tamano_bytes IS NULL))
);

-- ---------------------------------------------------------------------
-- Exámenes (pregunta/opción en tablas propias: así el examen se califica
-- con SQL, ver fn_calificar_intento)
-- ---------------------------------------------------------------------
CREATE TABLE examen (
    examen_id     BIGSERIAL PRIMARY KEY,
    grupo_id      BIGINT NOT NULL REFERENCES grupo (grupo_id),
    titulo        VARCHAR(150) NOT NULL,
    abre_en       TIMESTAMPTZ NOT NULL,
    cierra_en     TIMESTAMPTZ NOT NULL,
    intentos_max  SMALLINT NOT NULL DEFAULT 1 CHECK (intentos_max >= 1),
    CHECK (cierra_en > abre_en)
);

CREATE TABLE pregunta (
    pregunta_id  BIGSERIAL PRIMARY KEY,
    examen_id    BIGINT NOT NULL REFERENCES examen (examen_id) ON DELETE CASCADE,
    enunciado    TEXT NOT NULL,
    puntos       NUMERIC(5, 2) NOT NULL DEFAULT 1 CHECK (puntos > 0)
);

CREATE TABLE opcion (
    opcion_id    BIGSERIAL PRIMARY KEY,
    pregunta_id  BIGINT NOT NULL REFERENCES pregunta (pregunta_id) ON DELETE CASCADE,
    texto        TEXT NOT NULL,
    es_correcta  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE intento_examen (
    intento_id      BIGSERIAL PRIMARY KEY,
    examen_id       BIGINT NOT NULL REFERENCES examen (examen_id),
    inscripcion_id  BIGINT NOT NULL REFERENCES inscripcion (inscripcion_id),
    numero          SMALLINT NOT NULL CHECK (numero >= 1),
    iniciado_en     TIMESTAMPTZ NOT NULL DEFAULT now(),
    enviado_en      TIMESTAMPTZ,
    puntaje         NUMERIC(5, 2),
    UNIQUE (examen_id, inscripcion_id, numero)
);

CREATE TABLE respuesta (
    respuesta_id  BIGSERIAL PRIMARY KEY,
    intento_id    BIGINT NOT NULL REFERENCES intento_examen (intento_id) ON DELETE CASCADE,
    pregunta_id   BIGINT NOT NULL REFERENCES pregunta (pregunta_id),
    opcion_id     BIGINT NOT NULL REFERENCES opcion (opcion_id),
    UNIQUE (intento_id, pregunta_id)
);

-- ---------------------------------------------------------------------
-- Calificaciones y asistencias
-- calificacion es la tabla que se fragmenta horizontalmente por
-- centro_academico_id (fragmento A / B).
-- ---------------------------------------------------------------------
CREATE TABLE calificacion (
    calificacion_id      BIGSERIAL PRIMARY KEY,
    inscripcion_id       BIGINT NOT NULL REFERENCES inscripcion (inscripcion_id),
    centro_academico_id  SMALLINT NOT NULL REFERENCES centro_academico (centro_academico_id),
    tipo                 VARCHAR(10) NOT NULL
                         CHECK (tipo IN ('parcial1', 'parcial2', 'parcial3', 'final')),
    valor                NUMERIC(4, 2) NOT NULL CHECK (valor BETWEEN 0 AND 10),
    validada             BOOLEAN NOT NULL DEFAULT FALSE,  -- la final la valida el profesor
    registrada_en        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (inscripcion_id, tipo)
);

-- Bitácora de cambios de calificación (integridad). Sin FK a calificacion
-- para que el rastro sobreviva aunque se borre la calificación.
CREATE TABLE bitacora_calificacion (
    bitacora_id      BIGSERIAL PRIMARY KEY,
    calificacion_id  BIGINT NOT NULL,
    inscripcion_id   BIGINT NOT NULL,
    operacion        CHAR(1) NOT NULL CHECK (operacion IN ('I', 'U', 'D')),
    valor_anterior   NUMERIC(4, 2),
    valor_nuevo      NUMERIC(4, 2),
    usuario_bd       TEXT NOT NULL DEFAULT current_user,
    cambiado_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE asistencia (
    asistencia_id   BIGSERIAL PRIMARY KEY,
    inscripcion_id  BIGINT NOT NULL REFERENCES inscripcion (inscripcion_id),
    fecha           DATE NOT NULL,
    estado          VARCHAR(12) NOT NULL
                    CHECK (estado IN ('presente', 'falta', 'retardo', 'justificada')),
    UNIQUE (inscripcion_id, fecha)
);

-- ---------------------------------------------------------------------
-- Comunicación: avisos, mensajería y notificaciones (consistencia eventual)
-- ---------------------------------------------------------------------
CREATE TABLE aviso (
    aviso_id          BIGSERIAL PRIMARY KEY,
    autor_usuario_id  BIGINT NOT NULL REFERENCES usuario (usuario_id),
    grupo_id          BIGINT REFERENCES grupo (grupo_id),   -- NULL = aviso general
    titulo            VARCHAR(150) NOT NULL,
    cuerpo            TEXT NOT NULL,
    publicado_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE conversacion (
    conversacion_id  BIGSERIAL PRIMARY KEY,
    tipo             VARCHAR(10) NOT NULL CHECK (tipo IN ('directa', 'grupo')),
    grupo_id         BIGINT REFERENCES grupo (grupo_id),
    creada_en        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((tipo = 'grupo') = (grupo_id IS NOT NULL))
);

CREATE TABLE participante_conversacion (
    conversacion_id  BIGINT NOT NULL REFERENCES conversacion (conversacion_id) ON DELETE CASCADE,
    usuario_id       BIGINT NOT NULL REFERENCES usuario (usuario_id),
    ultimo_leido_en  TIMESTAMPTZ,                 -- estado de lectura
    PRIMARY KEY (conversacion_id, usuario_id)
);

CREATE TABLE mensaje (
    mensaje_id       BIGSERIAL PRIMARY KEY,
    conversacion_id  BIGINT NOT NULL REFERENCES conversacion (conversacion_id) ON DELETE CASCADE,
    remitente_id     BIGINT NOT NULL REFERENCES usuario (usuario_id),
    cuerpo           TEXT NOT NULL CHECK (length(cuerpo) BETWEEN 1 AND 4000),
    enviado_en       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE notificacion (
    notificacion_id  BIGSERIAL PRIMARY KEY,
    usuario_id       BIGINT NOT NULL REFERENCES usuario (usuario_id),
    tipo             VARCHAR(20) NOT NULL
                     CHECK (tipo IN ('tarea', 'examen', 'aviso', 'calificacion', 'mensaje', 'inscripcion')),
    texto            VARCHAR(255) NOT NULL,
    referencia_id    BIGINT,
    leida            BOOLEAN NOT NULL DEFAULT FALSE,
    creada_en        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- Vistas
-- =====================================================================

-- Situación académica por alumno (la entidad que pide el profe). Es vista
-- y no tabla: se calcula de las calificaciones finales validadas, así
-- nunca queda desactualizada. Aprobatoria: 6.0 o más.
CREATE VIEW v_situacion_academica AS
SELECT a.alumno_id,
       a.matricula,
       a.carrera_id,
       count(c.calificacion_id) FILTER (WHERE c.valor >= 6)            AS materias_aprobadas,
       count(c.calificacion_id) FILTER (WHERE c.valor < 6)             AS materias_reprobadas,
       coalesce(sum(m.creditos) FILTER (WHERE c.valor >= 6), 0)        AS creditos_aprobados,
       round(avg(c.valor), 2)                                          AS promedio_general
FROM alumno a
LEFT JOIN inscripcion i  ON i.alumno_id = a.alumno_id
LEFT JOIN grupo g        ON g.grupo_id = i.grupo_id
LEFT JOIN materia m      ON m.materia_id = g.materia_id
LEFT JOIN calificacion c ON c.inscripcion_id = i.inscripcion_id
                        AND c.tipo = 'final' AND c.validada
GROUP BY a.alumno_id, a.matricula, a.carrera_id;

-- Pendientes del alumno: tareas de sus grupos que aún no entrega.
CREATE VIEW v_pendientes_alumno AS
SELECT i.alumno_id, t.tarea_id, t.titulo, m.nombre AS materia, t.fecha_limite
FROM inscripcion i
JOIN tarea t   ON t.grupo_id = i.grupo_id
JOIN grupo g   ON g.grupo_id = i.grupo_id
JOIN materia m ON m.materia_id = g.materia_id
LEFT JOIN entrega e ON e.tarea_id = t.tarea_id AND e.inscripcion_id = i.inscripcion_id
WHERE i.estado = 'activa' AND e.entrega_id IS NULL;

-- Boleta (kardex del periodo): parciales, promedio y final por inscripción.
CREATE VIEW v_boleta AS
SELECT i.inscripcion_id, i.alumno_id, m.clave AS materia_clave, m.nombre AS materia,
       max(c.valor) FILTER (WHERE c.tipo = 'parcial1')               AS parcial1,
       max(c.valor) FILTER (WHERE c.tipo = 'parcial2')               AS parcial2,
       max(c.valor) FILTER (WHERE c.tipo = 'parcial3')               AS parcial3,
       i.promedio_parciales,
       max(c.valor) FILTER (WHERE c.tipo = 'final' AND c.validada)   AS final
FROM inscripcion i
JOIN grupo g   ON g.grupo_id = i.grupo_id
JOIN materia m ON m.materia_id = g.materia_id
LEFT JOIN calificacion c ON c.inscripcion_id = i.inscripcion_id
GROUP BY i.inscripcion_id, i.alumno_id, m.clave, m.nombre, i.promedio_parciales;
