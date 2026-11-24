-- =====================================================================
-- SIGAF · db/06_credenciales.sql  (issue #6)
-- Crea los USUARIOS con login y les asigna su rol. Las contraseñas NO
-- están aquí: llegan como variables de psql desde variables de entorno.
--
--   psql -v ON_ERROR_STOP=1 \
--        -v pass_admin="$SIGAF_PASS_ADMIN" -v pass_api="$SIGAF_PASS_API" \
--        -v pass_etl="$SIGAF_PASS_ETL" -v pass_repl="$SIGAF_PASS_REPL" \
--        -f db/06_credenciales.sql
--
-- Cuentas administrativas separadas de las de servicio (Lineamientos a.7).
-- =====================================================================
SELECT set_config('sigaf.pass_admin', :'pass_admin', false),
       set_config('sigaf.pass_api',   :'pass_api',   false),
       set_config('sigaf.pass_etl',   :'pass_etl',   false),
       set_config('sigaf.pass_repl',  :'pass_repl',  false) \gset

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT * FROM (VALUES
            ('sigaf_dba',        'sigaf_admin', 'pass_admin'),   -- persona: administrador
            ('sigaf_api_svc',    'sigaf_api',   'pass_api'),     -- servicio: API FastAPI
            ('sigaf_etl_svc',    'sigaf_etl',   'pass_etl')      -- servicio: ETL a MongoDB
        ) AS t(usuario, rol, var)
    LOOP
        IF length(current_setting('sigaf.' || r.var)) < 12 THEN
            RAISE EXCEPTION 'La contraseña de % debe tener al menos 12 caracteres', r.usuario;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.usuario) THEN
            EXECUTE format('CREATE ROLE %I LOGIN', r.usuario);
        END IF;
        EXECUTE format('ALTER ROLE %I LOGIN PASSWORD %L CONNECTION LIMIT 50',
                       r.usuario, current_setting('sigaf.' || r.var));
        EXECUTE format('GRANT %I TO %I', r.rol, r.usuario);
    END LOOP;

    -- Replicación (Patroni): solo puede replicar, no leer tablas
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigaf_replicador') THEN
        CREATE ROLE sigaf_replicador LOGIN REPLICATION;
    END IF;
    EXECUTE format('ALTER ROLE sigaf_replicador PASSWORD %L', current_setting('sigaf.pass_repl'));
END $$;

-- Borra las contraseñas de la sesión
SELECT set_config('sigaf.pass_admin', '', false), set_config('sigaf.pass_api', '', false),
       set_config('sigaf.pass_etl', '', false),   set_config('sigaf.pass_repl', '', false) \gset
