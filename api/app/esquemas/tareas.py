from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, Field, StringConstraints

from .base import Entrada, Salida

# Límite técnico (1 año) para que un número absurdo no llegue a la base.
# La regla de negocio solo pide que no sea negativo; si no se manda, la base
# pone su DEFAULT de 48 horas (decisión 13).
MARGEN_MAXIMO_HORAS = 8760


class TareaNueva(Entrada):
    titulo: Annotated[str, StringConstraints(min_length=1, max_length=150)]
    descripcion: Annotated[str, StringConstraints(max_length=5000)] | None = None
    fecha_limite: AwareDatetime                 # con zona horaria, para no adivinarla
    margen_tardia_horas: int | None = Field(default=None, ge=0, le=MARGEN_MAXIMO_HORAS)


class Tarea(Salida):
    tarea_id: int
    grupo_id: int
    titulo: str
    descripcion: str | None
    fecha_limite: datetime
    margen_tardia_horas: float
    cierre_entrega: datetime
