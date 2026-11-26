"""Respuestas de error que se documentan en OpenAPI (para la app de Kevin).

Los códigos 404/409/422/503 los produce el manejador de errores de Ricardo (#7),
que traduce las excepciones de negocio con el formato {"error": ..., "mensaje": ...}.
"""

from __future__ import annotations

from typing import Any

SIN_SESION = {401: {"description": "Sin token o token inválido (inicia sesión en /auth/login)"}}
ROL = {403: {"description": "Tu rol no tiene permiso para esta operación"}}
NO_ENCONTRADO = {404: {"description": "No existe o no es tuyo (no se revela cuál de los dos)"}}
CONFLICTO = {409: {"description": "Regla de negocio: duplicado o entrega fuera de tiempo"}}
CREDENCIALES = {401: {"description": "Correo o contraseña incorrectos (siempre el mismo mensaje)"}}
SIN_ANALITICA = {503: {"description": "La base de análisis (MongoDB) no responde"}}


def errores(*grupos: dict[int, dict[str, Any]]) -> dict[int | str, dict[str, Any]]:
    juntos: dict[int | str, dict[str, Any]] = {**SIN_SESION, **ROL}
    for grupo in grupos:
        juntos.update(grupo)
    return juntos
