from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import field_validator

from ..dominio.reglas import validar_calificacion
from .base import Entrada, Id, Salida

TipoCalificacion = Literal["parcial1", "parcial2", "parcial3", "final"]


class CalificacionNueva(Entrada):
    inscripcion_id: Id
    tipo: TipoCalificacion
    valor: Decimal

    @field_validator("valor")
    @classmethod
    def _escala_0_a_10(cls, valor: Decimal) -> Decimal:
        return validar_calificacion(valor)   # lanza CalificacionInvalidaError -> 422


class CalificacionRegistrada(Salida):
    calificacion_id: int
    inscripcion_id: int
    tipo: TipoCalificacion
    valor: float
    validada: bool
