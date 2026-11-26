"""Inicio de sesión (issue #11). Es la única ruta que no pide token."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..esquemas.auth import Login, Token
from .respuestas import CREDENCIALES
from .servicios import Autenticacion

router = APIRouter(prefix="/auth", tags=["auth"])

FORMATO_INVALIDO = {422: {"description": "Correo o contraseña con formato inválido"}}


@router.post("/login", response_model=Token, summary="Iniciar sesión",
             responses={**CREDENCIALES, **FORMATO_INVALIDO})
def login(datos: Login, request: Request, servicio: Autenticacion) -> Token:
    """Correo y contraseña -> token JWT para mandar en `Authorization: Bearer <token>`.

    Cualquier fallo (correo que no existe, contraseña mala, cuenta inactiva) responde
    el mismo 401. Cada intento, bueno o malo, queda en la bitácora de accesos.
    """
    # IP de quien se conecta directo a la API. Detrás de un proxy sería la del proxy:
    # en ese caso se arranca uvicorn con --proxy-headers y --forwarded-allow-ips.
    ip = request.client.host if request.client else None
    sesion = servicio.iniciar_sesion(datos.correo, datos.contrasena, ip)
    return Token(access_token=sesion.token, expira_en=sesion.expira_en, rol=sesion.persona.rol)
