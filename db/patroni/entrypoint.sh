#!/bin/bash
# Arranca un nodo: prepara certificados y datos, escribe la config de Patroni
# y lanza Patroni como usuario postgres. Variables: NODO, FRAGMENTO, contraseñas.
set -euo pipefail

# 1. Certificados TLS (los genera el servicio "certificados"). PostgreSQL
#    exige que la llave sea del usuario postgres y no la lean otros.
install -d -o postgres -m 700 /run/certs
install -o postgres -m 644 /certs/ca.crt /run/certs/ca.crt
install -o postgres -m 644 "/certs/$NODO.crt" /run/certs/nodo.crt
install -o postgres -m 600 "/certs/$NODO.key" /run/certs/nodo.key

# 2. Carpeta de datos
install -d -o postgres -m 700 /var/lib/postgresql/data

# 3. Configuración de Patroni. TLS y pg_hba = infra/postgres de Ricardo.
cat > /etc/patroni.yml <<YAML
scope: sigaf-${FRAGMENTO}
name: ${NODO}
restapi:
  listen: 0.0.0.0:8008
  connect_address: ${NODO}:8008
etcd3:
  hosts: etcd:2379
bootstrap:
  dcs:
    ttl: 20
    loop_wait: 5
    retry_timeout: 5
    maximum_lag_on_failover: 1048576
    # Decisión del equipo (CP en lo académico, CP estricto):
    # cada escritura espera a la réplica; sin réplica, no se escribe.
    synchronous_mode: true
    synchronous_mode_strict: true
    postgresql:
      use_pg_rewind: false
      parameters:
        wal_level: replica
        hot_standby: "on"
        max_wal_senders: 5
        max_replication_slots: 5
  initdb:
    - encoding: UTF8
    - data-checksums
  post_bootstrap: /usr/local/bin/post_bootstrap.sh
postgresql:
  listen: 0.0.0.0:5432
  connect_address: ${NODO}:5432
  data_dir: /var/lib/postgresql/data/pgdata
  pgpass: /tmp/pgpass
  use_unix_socket: true          # Patroni entra por socket local: regla "local all postgres peer"
  use_unix_socket_repl: false
  remove_data_directory_on_diverged_timelines: true
  remove_data_directory_on_rewind_failure: true
  authentication:
    superuser:
      username: postgres
      password: "${SIGAF_PASS_SUPER}"
    replication:
      username: sigaf_replicador
      password: "${SIGAF_PASS_REPL}"
      sslmode: verify-full
      sslrootcert: /run/certs/ca.crt
  parameters:
    unix_socket_directories: /var/run/postgresql
    ssl: "on"
    ssl_cert_file: /run/certs/nodo.crt
    ssl_key_file: /run/certs/nodo.key
    ssl_ca_file: /run/certs/ca.crt
    ssl_min_protocol_version: TLSv1.2
    password_encryption: scram-sha-256
    log_connections: "on"
    log_disconnections: "on"
    log_statement: ddl
  pg_hba:
    - local all postgres peer
    - host all sigaf_dba 127.0.0.1/32 scram-sha-256
    # Patroni revisa su propia réplica por 127.0.0.1 (también con TLS)
    - hostssl replication sigaf_replicador 127.0.0.1/32 scram-sha-256
    - hostssl replication sigaf_replicador 192.168.0.0/16 scram-sha-256
    - hostssl replication sigaf_replicador 10.8.0.0/24 scram-sha-256
    - hostssl all sigaf_api_svc 0.0.0.0/0 scram-sha-256
    - hostssl all sigaf_etl_svc 0.0.0.0/0 scram-sha-256
    - hostssl all sigaf_dba 0.0.0.0/0 scram-sha-256
    # Respaldos (issue #26): solo desde la red de Docker/LAN y solo con TLS
    - hostssl all sigaf_respaldo 192.168.0.0/16 scram-sha-256
    - hostnossl all all 0.0.0.0/0 reject
    - host all all 0.0.0.0/0 reject
YAML
chown postgres /etc/patroni.yml
chmod 600 /etc/patroni.yml

exec gosu postgres /opt/patroni/bin/patroni /etc/patroni.yml
