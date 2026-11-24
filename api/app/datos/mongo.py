"""Lectura de la base analítica (MongoDB) con pymongo.

La llena el ETL (datos/analitica) con consistencia EVENTUAL: los datos pueden
ir un poco atrás de PostgreSQL. Por eso cada respuesta trae actualizado_en.

Contra inyección NoSQL: las consultas y pipelines son FIJOS en este archivo;
lo que manda el usuario (periodo, ids) solo entra como VALOR, ya validado por
los esquemas, nunca como llave ni como operador ($...).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from ..config import Configuracion
from ..dominio.excepciones import ServicioNoDisponibleError

T = TypeVar("T")

TIEMPO_ESPERA_MS = 3000
# Rangos de calificación [0,1), [1,2) ... [9,10) y el 10 en su propio rango.
LIMITES_RANGOS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10.01]
SIN_ID = {"_id": 0}


def crear_cliente_mongo(config: Configuracion) -> MongoClient:
    """El cliente no conecta al crearse: si MongoDB está caído, la API arranca igual
    y solo las estadísticas responden 503."""
    return MongoClient(
        config.mongo_uri,
        serverSelectionTimeoutMS=TIEMPO_ESPERA_MS,
        connectTimeoutMS=TIEMPO_ESPERA_MS,
        tz_aware=True,
        appname="sigaf_api",
    )


class RepositorioEstadisticas:
    def __init__(self, db: Database) -> None:
        self._db = db

    def _consultar(self, operacion: Callable[[], T]) -> T:
        try:
            return operacion()
        except PyMongoError as error:
            raise ServicioNoDisponibleError("La base de analítica no responde") from error

    def actividad_de_alumno(self, alumno_id: int) -> list[dict[str, Any]]:
        return self._consultar(lambda: list(
            self._db["actividad_alumno"].find({"alumno_id": alumno_id}, SIN_ID).sort("periodo", -1)
        ))

    def resumen_de_grupo(self, grupo_id: int) -> list[dict[str, Any]]:
        return self._consultar(lambda: list(
            self._db["resumen_grupo"].find({"grupo_id": grupo_id}, SIN_ID).sort("periodo", -1)
        ))

    def distribucion(self, periodo: str, tipo: str | None) -> list[dict[str, Any]]:
        filtro: dict[str, Any] = {"periodo": periodo}
        if tipo is not None:
            filtro["tipo"] = tipo
        pipeline = [
            {"$match": filtro},
            {"$bucket": {"groupBy": "$valor", "boundaries": LIMITES_RANGOS,
                         "default": "fuera_de_rango", "output": {"total": {"$sum": 1}}}},
        ]
        return self._consultar(lambda: list(
            self._db["historico_calificaciones"].aggregate(pipeline)
        ))

    def promedio_por_materia(self, periodo: str, cuantas: int) -> list[dict[str, Any]]:
        pipeline = [
            {"$match": {"periodo": periodo, "promedio": {"$ne": None}}},
            {"$group": {"_id": "$materia_clave", "materia": {"$first": "$materia"},
                        "promedio": {"$avg": "$promedio"}, "alumnos": {"$sum": "$alumnos"}}},
            {"$sort": {"promedio": 1, "_id": 1}},
            {"$limit": cuantas},
        ]
        return self._consultar(lambda: list(self._db["resumen_grupo"].aggregate(pipeline)))

    def entregas_por_centro(self, periodo: str) -> list[dict[str, Any]]:
        pipeline = [
            {"$match": {"periodo": periodo}},
            {"$group": {"_id": "$centro",
                        "a_tiempo": {"$sum": "$entregas_a_tiempo"},
                        "tardias": {"$sum": "$entregas_tardias"},
                        "no_entregadas": {"$sum": "$no_entregadas"}}},
            {"$sort": {"_id": 1}},
        ]
        return self._consultar(lambda: list(self._db["actividad_alumno"].aggregate(pipeline)))
