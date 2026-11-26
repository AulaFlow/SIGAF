#!/bin/bash
# Patroni lo corre UNA vez, en el primer nodo que crea el fragmento.
# Carga el esquema y la seguridad de Ricardo (orden: 01 02 03 05 06 07)
# y el usuario de respaldos (issue #26).
# synchronous_commit=local: al crear el fragmento todavía no hay réplica y,
# con CP estricto, cualquier escritura se quedaría esperando.
set -euo pipefail
export PGOPTIONS="-c synchronous_commit=local"
CONEXION="$1"
correr() { psql "$CONEXION" -q -v ON_ERROR_STOP=1 "$@"; }

for f in 01_tablas 02_indices 03_funciones_triggers 05_seguridad; do
    correr -f "/sigaf-sql/$f.sql"
done
correr -v pass_admin="$SIGAF_PASS_ADMIN" -v pass_api="$SIGAF_PASS_API" \
       -v pass_etl="$SIGAF_PASS_ETL" -v pass_repl="$SIGAF_PASS_REPL" \
       -f /sigaf-sql/06_credenciales.sql
correr -f /sigaf-sql/07_margen_entrega.sql
# Usuario de solo lectura para respaldos (issue #26)
correr -v pass_respaldo="$SIGAF_PASS_RESPALDO" -f /sigaf-sql/respaldos/crear_usuario.sql
echo "[sigaf] esquema y seguridad cargados en $(hostname)"
