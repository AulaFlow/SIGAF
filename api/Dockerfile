# SIGAF · imagen de la API (issue #28)
#   La levanta db/docker-compose.yml (servicio "api"). Sin secretos aquí:
#   contraseñas y llaves llegan por variables de entorno desde db/.env.
FROM python:3.12-slim-trixie

# Sin .pyc en disco y logs al instante (sin búfer) para "docker compose logs"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Primero solo las dependencias: si cambias código y no requirements.txt,
# Docker reutiliza esta capa y el build tarda segundos.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app app

# Usuario sin privilegios: si alguien rompe la API, no es root en el contenedor.
RUN useradd --system --no-create-home --uid 10001 sigaf
USER sigaf

EXPOSE 8000

# El healthcheck usa Python (la imagen slim no trae curl).
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

# --factory: crear_app() lee la configuración del entorno al arrancar.
# --proxy-headers no: la API no está detrás de un proxy HTTP todavía.
CMD ["uvicorn", "app.main:crear_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
