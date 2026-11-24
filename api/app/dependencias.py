"""Dependencias de FastAPI compartidas por las rutas.

usuario_actual() y requiere_rol() las agrega Salva en el issue #11 (JWT y roles).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from .datos.postgres import BaseDeDatos


def obtener_bd(request: Request) -> BaseDeDatos:
    """La BaseDeDatos que creó el lifespan. En pruebas se reemplaza con dependency_overrides."""
    return request.app.state.bd


# Uso en una ruta:  def mi_ruta(bd: BD) -> ...
BD = Annotated[BaseDeDatos, Depends(obtener_bd)]
