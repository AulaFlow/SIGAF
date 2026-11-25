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
from pymongo import MongoClient

from .config import Configuracion
from .datos.enrutador import crear_base_distribuida
from .datos.mongo import crear_cliente_mongo
from .datos.postgres import crear_pool
from .rutas import ROUTERS

TIEMPO_ESPERA_POOL = 10   # segundos para conectar al arrancar


def crear_app(
    config: Configuracion | None = None,
    fabrica_pool: Callable[[Configuracion], ConnectionPool] = crear_pool,
    fabrica_mongo: Callable[[Configuracion], MongoClient] = crear_cliente_mongo,
) -> FastAPI:
    config = config or Configuracion.desde_entorno()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        def abrir(pool: ConnectionPool) -> None:
            pool.open(wait=True, timeout=TIEMPO_ESPERA_POOL)   # si la base no responde, no arranca

        pool = fabrica_pool(config)
        abrir(pool)
        abiertos = [pool]
        mongo = fabrica_mongo(config)                     # analítica (no conecta aún)
        app.state.mongo_db = mongo[config.mongo_db]
        abiertos.append(mongo)
        try:
            # Lee directorio_fragmento y abre un pool por fragmento (issue #6).
            app.state.bd, nuevos = crear_base_distribuida(config, pool, fabrica_pool, abrir)
            abiertos.extend(nuevos)
            yield
        finally:
            for abierto in abiertos:
                abierto.close()

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

    # Rutas de alumno, profesor y estadísticas (issue #23).
    for router in ROUTERS:
        app.include_router(router)

    return app
