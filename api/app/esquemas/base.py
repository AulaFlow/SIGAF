"""Bases de los esquemas.

Entrada: extra="forbid" rechaza cualquier campo que no esté declarado (por
ejemplo entregada_en o alumno_id que el cliente intente colar) y los tipos
estrictos impiden mandar objetos como {"$gt": ""} donde va un número o texto
(inyección NoSQL). Contra inyección SQL, además, todo va con parámetros %s.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

MAX_BIGINT = 9_223_372_036_854_775_807

# Identificador de la base: entero positivo que cabe en BIGINT.
Id = Annotated[int, Field(gt=0, le=MAX_BIGINT, strict=True)]


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Salida(BaseModel):
    model_config = ConfigDict(extra="ignore")
