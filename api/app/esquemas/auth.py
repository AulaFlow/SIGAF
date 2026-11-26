"""Entrada y salida de POST /auth/login (issue #11)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from ..dominio.personas import Rol
from .base import Entrada, Salida

# Mismo patrón que el CHECK de usuario.correo (db/01) y mismo largo que la columna.
# A minúsculas: el generador, pruebas.sql y la limpieza guardan siempre minúsculas
# (verificado en el #11), y la búsqueda es por igualdad exacta (usa el índice UNIQUE).
Correo = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=120,
                      pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", strict=True),
]

# La contraseña NO se recorta: Entrada quita espacios a todos los textos, pero
# "  clave  " y "clave" son contraseñas distintas.
#
# Sin límite de 72 aquí, a propósito: el 422 de FastAPI devuelve el valor recibido
# ("input") y regresaría la contraseña en la respuesta. El límite real de bcrypt
# (72 bytes) lo aplica el servicio con el mismo 401 de siempre. 1024 solo frena
# cuerpos enormes; nadie tiene una contraseña así.
LARGO_MAXIMO_CONTRASENA = 1024
Contrasena = Annotated[
    str, StringConstraints(strip_whitespace=False, min_length=1,
                           max_length=LARGO_MAXIMO_CONTRASENA, strict=True),
]


class Login(Entrada):
    """Solo correo y contraseña. El rol NO se manda: sale de la base."""

    correo: Correo
    contrasena: Contrasena = Field(repr=False)    # nunca en logs ni en mensajes de error


class Token(Salida):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expira_en: int = Field(description="Segundos de vida del token")
    rol: Rol = Field(description="Para que la app abra la pantalla de su rol")
