"""Dependencias de FastAPI compartidas por las rutas.

usuario_actual() y requiere_rol() las agrega Salva en el issue #11 (JWT y roles).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from .datos.mongo import RepositorioEstadisticas
from .datos.postgres import BaseDeDatos
from .servicios.estadisticas import ServicioEstadisticas


def obtener_bd(request: Request) -> BaseDeDatos:
    """La BaseDeDatos que creó el lifespan. En pruebas se reemplaza con dependency_overrides."""
    return request.app.state.bd


# Uso en una ruta:  def mi_ruta(bd: BD) -> ...
BD = Annotated[BaseDeDatos, Depends(obtener_bd)]


def obtener_estadisticas(request: Request) -> ServicioEstadisticas:
    """Estadísticas: MongoDB para los indicadores y PostgreSQL para los permisos."""
    return ServicioEstadisticas(RepositorioEstadisticas(request.app.state.mongo_db),
                                request.app.state.bd)


Estadisticas = Annotated[ServicioEstadisticas, Depends(obtener_estadisticas)]
