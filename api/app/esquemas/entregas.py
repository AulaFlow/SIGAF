from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from ..dominio.reglas import validar_calificacion
from .base import Entrada, Salida

TAMANO_MAXIMO_BYTES = 52_428_800    # 50 MB, igual que el CHECK de entrega

RutaArchivo = Annotated[
    str, StringConstraints(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9_.\-/]+$")
]
TipoMime = Annotated[
    str, StringConstraints(max_length=100, pattern=r"^[a-z]+/[a-z0-9.+\-]+$")
]


class EntregaNueva(Entrada):
    """Lo que manda el alumno. NO incluye entregada_en: la pone la base con
    DEFAULT now(), así nadie puede fingir que entregó a tiempo."""

    archivo_ruta: RutaArchivo | None = None
    archivo_tamano_bytes: int | None = Field(default=None, ge=1, le=TAMANO_MAXIMO_BYTES)
    archivo_tipo: TipoMime | None = None

    @field_validator("archivo_ruta")
    @classmethod
    def _ruta_segura(cls, ruta: str | None) -> str | None:
        if ruta is not None and (ruta.startswith("/") or ".." in ruta.split("/")):
            raise ValueError("La ruta del archivo debe ser relativa y sin '..'")
        return ruta

    @model_validator(mode="after")
    def _ruta_y_tamano_juntos(self) -> EntregaNueva:
        # Mismo CHECK que la base: (archivo_ruta IS NULL) = (archivo_tamano_bytes IS NULL)
        if (self.archivo_ruta is None) != (self.archivo_tamano_bytes is None):
            raise ValueError("archivo_ruta y archivo_tamano_bytes van juntos")
        return self


class EntregaRegistrada(Salida):
    entrega_id: int
    tarea_id: int
    entregada_en: datetime
    estado: Literal["a_tiempo", "tardia"]


class CalificacionDeEntrega(Entrada):
    calificacion: Decimal
    retroalimentacion: Annotated[str, StringConstraints(max_length=2000)] | None = None

    @field_validator("calificacion")
    @classmethod
    def _escala_0_a_10(cls, valor: Decimal) -> Decimal:
        return validar_calificacion(valor)   # lanza CalificacionInvalidaError -> 422


class EntregaCalificada(Salida):
    entrega_id: int
    calificacion: float
    retroalimentacion: str | None
