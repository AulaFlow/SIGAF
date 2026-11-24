"""Acceso a MongoDB (pymongo) detrás de una interfaz.

Las gráficas y el ETL dependen de ``RepositorioAnalitico`` y no de pymongo
directamente (inversión de dependencias): en las pruebas se usa la misma
clase con una base en memoria (mongomock).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from pymongo import ReplaceOne
from pymongo.database import Database

from .modelos import Documento


class RepositorioAnalitico(ABC):
    """Operaciones que necesitan el ETL y las gráficas."""

    @abstractmethod
    def guardar_lote(self, documentos: Iterable[Documento]) -> int:
        """Inserta o reemplaza documentos por su _id. Devuelve cuántos."""

    @abstractmethod
    def agregar(self, coleccion: str, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ejecuta un pipeline de agregación y devuelve los resultados."""

    @abstractmethod
    def contar(self, coleccion: str) -> int: ...


class RepositorioMongo(RepositorioAnalitico):
    """Implementación con pymongo."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def crear_indices(self) -> None:
        """Índices para las consultas de las gráficas y los reportes."""
        self._db["historico_calificaciones"].create_index([("periodo", 1), ("tipo", 1)])
        self._db["historico_calificaciones"].create_index("materia_clave")
        self._db["resumen_grupo"].create_index([("periodo", 1), ("materia_clave", 1)])
        self._db["actividad_alumno"].create_index([("periodo", 1), ("centro_academico_id", 1)])

    def guardar_lote(self, documentos: Iterable[Documento]) -> int:
        por_coleccion: dict[str, list[dict[str, Any]]] = {}
        for doc in documentos:
            por_coleccion.setdefault(doc.coleccion, []).append(doc.a_documento())
        return sum(self._escribir(c, docs) for c, docs in por_coleccion.items())

    def _escribir(self, coleccion: str, docs: list[dict[str, Any]]) -> int:
        """Un solo viaje a MongoDB por lote: reemplaza por _id o inserta si no existe."""
        operaciones = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs]
        resultado = self._db[coleccion].bulk_write(operaciones, ordered=False)
        return resultado.upserted_count + resultado.matched_count

    def agregar(self, coleccion: str, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return list(self._db[coleccion].aggregate(pipeline))

    def contar(self, coleccion: str) -> int:
        return self._db[coleccion].count_documents({})
