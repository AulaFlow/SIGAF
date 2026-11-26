#!/usr/bin/env bash
# =====================================================================
# SIGAF · crea el usuario sigaf_respaldo en una base que YA estaba creada
# (issue #26). En una base nueva no hace falta: post_bootstrap.sh lo crea.
#
#   cd db && bash respaldos/crear_usuario.sh
#
# Lo corre en el primario de A y de B; la réplica lo recibe sola.
# =====================================================================
set -euo pipefail
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
set -a; source .env; set +a
: "${SIGAF_PASS_RESPALDO:?falta SIGAF_PASS_RESPALDO en db/.env (ver .env.example)}"

for f in a b; do
    lider="$(docker compose exec -T "pg-${f}1" patronictl -c /etc/patroni.yml list -f tsv </dev/null \
             | awk -F'\t' '$4=="Leader" {print $2}')"
    [ -n "$lider" ] || { echo "Fragmento ${f^^}: no hay primario"; exit 1; }
    docker compose exec -T -u postgres "$lider" psql -d postgres -qX \
        -v pass_respaldo="$SIGAF_PASS_RESPALDO" -f /sigaf-sql/respaldos/crear_usuario.sql </dev/null
    echo "Fragmento ${f^^}: sigaf_respaldo listo en $lider"
done
