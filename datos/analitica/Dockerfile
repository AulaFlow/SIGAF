# ETL de PostgreSQL (fragmentos A y B) a MongoDB y gráficas (issue #8).
#   docker build -t sigaf-analitica datos/analitica
#   docker run --rm --network sigaf_default -v sigaf_certs:/certs:ro --env-file db/.env sigaf-analitica etl
FROM python:3.12-slim-trixie
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY analitica analitica

# Los dos fragmentos por HAProxy, con TLS que revisa la CA de Ricardo.
ENV SIGAF_FRAGMENTOS="A=postgresql://sigaf_etl_svc@haproxy:5432/postgres?sslmode=verify-ca&sslrootcert=/certs/ca.crt;B=postgresql://sigaf_etl_svc@haproxy:5434/postgres?sslmode=verify-ca&sslrootcert=/certs/ca.crt" \
    SIGAF_MONGO_DB=sigaf_analitica \
    MPLCONFIGDIR=/tmp/matplotlib

# Las contraseñas llegan del db/.env (--env-file) y aquí se pasan con el nombre
# que espera el ETL. Corre como root SOLO para leer /certs/ca.crt (carpeta 700);
# el volumen es de solo lectura y el contenedor se borra al terminar.
ENTRYPOINT ["sh", "-c", "export PGPASSWORD=\"$SIGAF_PASS_ETL\" SIGAF_MONGO_URI=\"mongodb://sigaf:$SIGAF_PASS_MONGO@mongo:27017/?authSource=admin\"; exec python -m analitica \"$@\"", "--"]
CMD ["etl"]
