"""Indicadores agregados (sin datos personales) para profesores y administradores.

Salen de MongoDB, que llena el ETL por lotes: consistencia eventual.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..dominio.personas import Persona, Rol
from ..esquemas.estadisticas import Distribucion, EntregasCentro, PromedioMateria
from ..esquemas.estadisticas import TipoCalificacion as Tipo
from ..seguridad import requiere_rol
from ..servicios.estadisticas import MAXIMO_MATERIAS
from .respuestas import SIN_ANALITICA, errores
from .servicios import Estadisticas

router = APIRouter(prefix="/estadisticas", tags=["estadísticas"],
                   responses=errores(SIN_ANALITICA))

Lector = Annotated[Persona, Depends(requiere_rol(Rol.PROFESOR, Rol.ADMINISTRADOR))]
PeriodoQ = Annotated[str, Query(pattern=r"^\d{4}-[A-Z]{3}-[A-Z]{3}$",
                                examples=["2026-AGO-DIC"], description="Periodo escolar")]


@router.get("/distribucion", response_model=Distribucion,
            summary="Distribución de calificaciones")
def distribucion(periodo: PeriodoQ, persona: Lector, servicio: Estadisticas,
                 tipo: Tipo | None = None) -> Distribucion:
    """Cuántas calificaciones caen en cada rango [0,1), [1,2) … 10. Filtro opcional por tipo."""
    return servicio.distribucion(persona, periodo, tipo)


@router.get("/promedio-por-materia", response_model=list[PromedioMateria],
            summary="Materias con menor promedio")
def promedio_por_materia(
    periodo: PeriodoQ, persona: Lector, servicio: Estadisticas,
    cuantas: Annotated[int, Query(ge=1, le=MAXIMO_MATERIAS)] = 12,
) -> list[PromedioMateria]:
    """Las materias con el promedio más bajo del periodo, de menor a mayor."""
    return servicio.promedio_por_materia(persona, periodo, cuantas)


@router.get("/entregas-por-centro", response_model=list[EntregasCentro],
            summary="Entregas a tiempo vs tardías por centro")
def entregas_por_centro(periodo: PeriodoQ, persona: Lector,
                        servicio: Estadisticas) -> list[EntregasCentro]:
    """Junta los dos fragmentos (A y B) a través de MongoDB, como dice la consulta C10."""
    return servicio.entregas_por_centro(persona, periodo)
