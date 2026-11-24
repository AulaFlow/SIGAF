from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import StringConstraints

from .base import Salida

# p. ej. 2026-AGO-DIC. El patrón no deja pasar '$', llaves ni espacios.
Periodo = Annotated[str, StringConstraints(pattern=r"^\d{4}-[A-Z]{3}-[A-Z]{3}$")]
TipoCalificacion = Literal["parcial1", "parcial2", "parcial3", "final"]


class ActividadDelAlumno(Salida):
    periodo: str
    centro: str
    entregas_a_tiempo: int
    entregas_tardias: int
    no_entregadas: int
    faltas: int
    actualizado_en: datetime | None = None     # consistencia eventual: de cuándo es el dato


class ResumenDeGrupo(Salida):
    periodo: str
    materia_clave: str
    materia: str
    alumnos: int
    promedio: float | None
    pct_aprobados: float | None
    pct_asistencia: float | None
    actualizado_en: datetime | None = None


class RangoCalificaciones(Salida):
    desde: int            # [desde, desde+1); el rango 10 es exactamente 10
    total: int


class Distribucion(Salida):
    periodo: str
    tipo: TipoCalificacion | None
    total: int
    rangos: list[RangoCalificaciones]


class PromedioMateria(Salida):
    materia_clave: str
    materia: str
    promedio: float
    alumnos: int


class EntregasCentro(Salida):
    centro: str
    a_tiempo: int
    tardias: int
    no_entregadas: int
