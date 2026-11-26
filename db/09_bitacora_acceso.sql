-- =====================================================================
-- SIGAF · db/09_bitacora_acceso.sql  (issue #11, Salva)
-- Bitácora de accesos: un renglón por cada intento de inicio de sesión
-- en POST /auth/login, bueno o malo.
--
-- Qué NO se guarda, a propósito:
--   * la contraseña (ni en claro ni con hash)
--   * el correo tecleado: a veces la gente escribe la contraseña en el
--     campo del correo, y un correo que no existe tampoco es de nadie.
--     Si el correo sí existe, basta con usuario_id.
--
-- Integridad: la API (sigaf_api) SOLO puede insertar. No lee, no cambia
-- y no borra; así un atacante que entre por la API no puede ocultar sus
-- intentos. El administrador solo la lee.
--
-- Dónde vive: la tabla se crea en los dos fragmentos (este script corre en
-- cada uno), pero la API escribe en el primer fragmento del directorio,
-- porque en un intento fallido no hay centro para elegir otro.
--
-- Cambio trazable: no edita 01 ni 05. Re-ejecutable.
-- Orden de carga: 01 -> 02 -> 03 -> 05 -> 06 -> 07 -> (08) -> 09
-- El 08 está reservado para db/08_permisos_admin.sql (Ricardo, #7). Este
-- archivo no depende de él: funciona con o sin el 08 cargado.
-- =====================================================================
SET search_path TO sigaf;

-- Sin FK a usuario (como bitacora_calificacion): el rastro sobrevive aunque
-- se borre la cuenta.
CREATE TABLE IF NOT EXISTS bitacora_acceso (
    acceso_id    BIGSERIAL PRIMARY KEY,
    usuario_id   BIGINT,                  -- NULL: el correo no existe
    exito        BOOLEAN NOT NULL,
    motivo       VARCHAR(20) NOT NULL
                 CONSTRAINT chk_bitacora_acceso_motivo
                 CHECK (motivo IN ('ok', 'sin_usuario', 'contrasena', 'inactivo', 'hash_invalido')),
    ip           INET,                    -- NULL si no se conoce
    ocurrido_en  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- 'ok' si y solo si fue exitoso: no puede quedar un éxito con motivo de falla.
    CONSTRAINT chk_bitacora_acceso_exito CHECK (exito = (motivo = 'ok')),
    -- Si el correo no existe no hay usuario_id, y si hay usuario_id el motivo no es ese.
    CONSTRAINT chk_bitacora_acceso_usuario
        CHECK ((usuario_id IS NULL) = (motivo = 'sin_usuario'))
);

COMMENT ON TABLE bitacora_acceso IS
    'Intentos de inicio de sesión (issue #11). La API solo inserta; nunca guarda contraseña ni correo.';

-- Consulta típica: intentos recientes de una cuenta.
CREATE INDEX IF NOT EXISTS idx_bitacora_acceso_usuario
    ON bitacora_acceso (usuario_id, ocurrido_en DESC);

-- Permisos (05 ya corrió: GRANT ... ON ALL TABLES no alcanza a esta tabla nueva).
REVOKE ALL ON bitacora_acceso FROM PUBLIC;
REVOKE ALL ON SEQUENCE bitacora_acceso_acceso_id_seq FROM PUBLIC;
GRANT INSERT ON bitacora_acceso TO sigaf_api;      -- sin SELECT: no usar INSERT ... RETURNING
GRANT USAGE ON SEQUENCE bitacora_acceso_acceso_id_seq TO sigaf_api;
GRANT SELECT ON bitacora_acceso TO sigaf_admin;    -- solo leer: la bitácora no se edita
-- sigaf_etl no recibe nada: los accesos no van a MongoDB.
