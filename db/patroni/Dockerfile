# SIGAF · imagen de nodo: PostgreSQL 16 + Patroni (issue #9)
# Python se copia de la imagen oficial de Python (misma Debian que postgres:16),
# así no hace falta apt-get.
FROM python:3.12-slim-trixie AS python
RUN python -m venv /opt/patroni \
 && /opt/patroni/bin/pip install --no-cache-dir "patroni[etcd3,psycopg3]==4.0.7"

FROM postgres:16
COPY --from=python /usr/local /usr/local
COPY --from=python /opt/patroni /opt/patroni
COPY entrypoint.sh post_bootstrap.sh /usr/local/bin/
# Quita los \r por si el repo se clonó en Windows
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh /usr/local/bin/post_bootstrap.sh \
 && chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/post_bootstrap.sh \
 && ln -s /opt/patroni/bin/patronictl /usr/local/bin/patronictl
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
