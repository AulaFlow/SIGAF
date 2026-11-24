#!/bin/bash
# Corre una sola vez en cada primario: crea el usuario de replicación
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "CREATE ROLE sigaf_replicador WITH REPLICATION LOGIN PASSWORD '$REPL_PASSWORD';"
echo "host replication sigaf_replicador all scram-sha-256" >> "$PGDATA/pg_hba.conf"
# Consistencia fuerte: cada escritura espera a que la réplica la confirme
echo "synchronous_standby_names = '*'" >> "$PGDATA/postgresql.conf"