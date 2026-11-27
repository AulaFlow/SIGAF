-- =====================================================================
-- SIGAF · usuario de respaldos (issue #26)
-- Mínimo privilegio (decisión del equipo): solo puede LEER, no escribir,
-- no crear nada y no replicar. pg_read_all_data (PostgreSQL 14+) le da
-- SELECT en todas las tablas y secuencias, que es justo lo que pg_dump usa.
-- Uso: psql -v pass_respaldo='...' -f crear_usuario.sql   (se puede repetir)
-- =====================================================================
\set ON_ERROR_STOP on

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sigaf_respaldo') THEN
        CREATE ROLE sigaf_respaldo LOGIN;
    END IF;
END
$$;

ALTER ROLE sigaf_respaldo WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    PASSWORD :'pass_respaldo';
-- Por si acaso: toda transacción de este usuario es de solo lectura
ALTER ROLE sigaf_respaldo SET default_transaction_read_only = on;
GRANT pg_read_all_data TO sigaf_respaldo;
