#!/usr/bin/env bash
# =====================================================================
# SIGAF · infra/postgres/probar_tls.sh  (issue #6)
# Evidencia de que pg_hba.conf y TLS funcionan como decidió el equipo.
# Uso:  HOST=laptop1 ./probar_tls.sh
# Requiere las contraseñas en SIGAF_PASS_API, SIGAF_PASS_ETL, SIGAF_PASS_ADMIN.
# =====================================================================
set -u
HOST="${HOST:-localhost}"
CA="$(dirname "$0")/certs/ca.crt"
: "${SIGAF_PASS_API:?falta SIGAF_PASS_API}" "${SIGAF_PASS_ETL:?falta SIGAF_PASS_ETL}" "${SIGAF_PASS_ADMIN:?falta SIGAF_PASS_ADMIN}"

esperar() {  # $1 = descripción, $2 = "ok" o "falla", resto = comando
    local desc="$1" esperado="$2"; shift 2
    if salida=$("$@" 2>&1); then real="ok"; else real="falla"; fi
    if [ "$real" = "$esperado" ]; then echo "[OK]    $desc"; else echo "[ERROR] $desc"; echo "        $salida"; fi
}

esperar "API sin TLS es rechazada" falla \
    env PGPASSWORD="$SIGAF_PASS_API" psql "host=$HOST user=sigaf_api_svc dbname=postgres sslmode=disable" -c "select 1"
esperar "API con TLS (verify-full) entra" ok \
    env PGPASSWORD="$SIGAF_PASS_API" psql "host=$HOST user=sigaf_api_svc dbname=postgres sslmode=verify-full sslrootcert=$CA" -c "select 1"
esperar "API no lee datos personales" falla \
    env PGPASSWORD="$SIGAF_PASS_API" psql "host=$HOST user=sigaf_api_svc dbname=postgres sslmode=verify-full sslrootcert=$CA" -v ON_ERROR_STOP=1 -c "select * from sigaf.alumno_datos_personales"
esperar "ETL sin TLS es rechazado" falla \
    env PGPASSWORD="$SIGAF_PASS_ETL" psql "host=$HOST user=sigaf_etl_svc dbname=postgres sslmode=disable" -c "select 1"
esperar "ETL con TLS lee calificaciones" ok \
    env PGPASSWORD="$SIGAF_PASS_ETL" psql "host=$HOST user=sigaf_etl_svc dbname=postgres sslmode=verify-full sslrootcert=$CA" -v ON_ERROR_STOP=1 -c "select count(*) from sigaf.calificacion"
esperar "ETL no lee usuarios" falla \
    env PGPASSWORD="$SIGAF_PASS_ETL" psql "host=$HOST user=sigaf_etl_svc dbname=postgres sslmode=verify-full sslrootcert=$CA" -v ON_ERROR_STOP=1 -c "select * from sigaf.usuario"
esperar "Admin local sin TLS entra" ok \
    env PGPASSWORD="$SIGAF_PASS_ADMIN" psql "host=127.0.0.1 user=sigaf_dba dbname=postgres sslmode=disable" -c "select 1"
echo "Cifrado de la sesión de la API:"
PGPASSWORD="$SIGAF_PASS_API" psql "host=$HOST user=sigaf_api_svc dbname=postgres sslmode=verify-full sslrootcert=$CA" \
    -Atc "select 'ssl=' || ssl || ' ' || version || ' ' || cipher from pg_stat_ssl where pid = pg_backend_pid()"
