# Contenedor para generar y repartir los datos (issue #8).
# Se construye desde la carpeta datos/ para incluir el generador de Ricardo:
#   docker build -t sigaf-reparto -f datos/reparto/Dockerfile datos
FROM python:3.12-slim-trixie
WORKDIR /app/datos
COPY reparto/requirements.txt reparto/requirements.txt
RUN pip install --no-cache-dir -r reparto/requirements.txt
COPY generador/generar_datos.py generador/generar_datos.py
COPY reparto/reparto reparto/reparto
WORKDIR /app/datos/reparto
# Corre como root SOLO para poder leer /certs/ca.crt (la carpeta de certificados
# es 700). El volumen se monta de solo lectura y el contenedor se borra al terminar.
ENTRYPOINT ["python", "-m", "reparto"]
CMD ["todo"]
