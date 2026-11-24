#!/bin/bash
# Réplica: la primera vez copia todo del primario y luego lo sigue en vivo
set -e
DATA=/var/lib/postgresql/data
if [ ! -s "$DATA/PG_VERSION" ]; then
  until pg_isready -h "$PRIMARIO" -U sigaf_replicador; do
    echo "Esperando a $PRIMARIO..."; sleep 3
  done
  pg_basebackup -h "$PRIMARIO" -U sigaf_replicador -D "$DATA" -R -X stream
  chmod 700 "$DATA"
fi
exec postgres -D "$DATA"