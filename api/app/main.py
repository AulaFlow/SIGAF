"""Punto de entrada de la API.

Se arranca con la fábrica (lee la configuración del entorno al crear la app):
    uvicorn app.main:crear_app --factory --env-file .env
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg_pool import ConnectionPool

from .config import Configuracion
from .datos.postgres import BaseDeDatos, crear_pool

TIEMPO_ESPERA_POOL = 10   # segundos para conectar al arrancar


def crear_app(
    config: Configuracion | None = None,
    fabrica_pool: Callable[[Configuracion], ConnectionPool] = crear_pool,
) -> FastAPI:
    config = config or Configuracion.desde_entorno()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = fabrica_pool(config)
        pool.open(wait=True, timeout=TIEMPO_ESPERA_POOL)   # si la base no responde, no arranca
        app.state.bd = BaseDeDatos(config, pool)
        try:
            yield
        finally:
            pool.close()

    app = FastAPI(title="SIGAF API", version="0.1.0", lifespan=lifespan)

    # CORS para el cliente web de Flutter: solo los orígenes listados (nunca "*").
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.origenes_cors),
        allow_credentials=False,                # el token va en el encabezado Authorization
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
