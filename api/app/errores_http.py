"""Traduce las excepciones de negocio (app/dominio/excepciones.py) a respuestas HTTP.

El dominio no sabe nada de HTTP; aquí se decide el código. Todas las respuestas de
error tienen la misma forma, para que la app las muestre igual:

    {"error": "<código corto y estable>", "mensaje": "<texto para el usuario>"}

- "error" es para el programa de la app (no cambia aunque cambie el texto).
- "mensaje" es para la persona. Nunca lleva SQL, nombres de tablas ni trazas.

Se registra UN solo manejador para SigafError y se busca la traducción recorriendo
la jerarquía de la excepción (su MRO), de la clase más específica a la más general.
Ejemplo: InscripcionDuplicadaError -> RegistroDuplicadoError -> ReglaDeNegocioError:
se usa la primera que esté en la tabla. Si mañana alguien crea una subclase nueva,
hereda el código de su padre sin tocar este archivo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from .dominio.excepciones import (
    CalificacionInvalidaError,
    DatoInvalidoError,
    EntregaFueraDeTiempoError,
    InscripcionDuplicadaError,
    NoEncontradoError,
    PermisoDenegadoError,
    RegistroDuplicadoError,
    ReglaDeNegocioError,
    ServicioNoDisponibleError,
    SigafError,
)

log = logging.getLogger("sigaf.api")

MENSAJE_INTERNO = "Ocurrió un error inesperado; intenta de nuevo más tarde"
MENSAJE_NO_DISPONIBLE = "El servicio no está disponible por el momento; intenta más tarde"


@dataclass(frozen=True)
class Traduccion:
    estado: int
    error: str
    mensaje_fijo: str | None = None   # None: se usa el mensaje de la excepción


TRADUCCIONES: dict[type[SigafError], Traduccion] = {
    NoEncontradoError: Traduccion(status.HTTP_404_NOT_FOUND, "no_encontrado"),
    PermisoDenegadoError: Traduccion(status.HTTP_403_FORBIDDEN, "permiso_denegado"),
    EntregaFueraDeTiempoError: Traduccion(status.HTTP_409_CONFLICT, "entrega_fuera_de_tiempo"),
    InscripcionDuplicadaError: Traduccion(status.HTTP_409_CONFLICT, "inscripcion_duplicada"),
    RegistroDuplicadoError: Traduccion(status.HTTP_409_CONFLICT, "registro_duplicado"),
    ReglaDeNegocioError: Traduccion(status.HTTP_409_CONFLICT, "regla_de_negocio"),
    CalificacionInvalidaError: Traduccion(422, "calificacion_invalida"),
    DatoInvalidoError: Traduccion(422, "dato_invalido"),
    # El mensaje original dice qué base falló (detalle interno): se manda uno fijo.
    ServicioNoDisponibleError: Traduccion(status.HTTP_503_SERVICE_UNAVAILABLE,
                                          "servicio_no_disponible", MENSAJE_NO_DISPONIBLE),
    # Un SigafError "a secas" no debería lanzarse nunca: se trata como error interno.
    SigafError: Traduccion(status.HTTP_500_INTERNAL_SERVER_ERROR, "error_interno",
                           MENSAJE_INTERNO),
}


def traduccion_de(error: SigafError) -> Traduccion:
    # Siempre encuentra una: SigafError está en la MRO de toda excepción de negocio.
    return next(TRADUCCIONES[clase] for clase in type(error).__mro__ if clase in TRADUCCIONES)


def cuerpo(error: str, mensaje: str) -> dict[str, str]:
    return {"error": error, "mensaje": mensaje}


async def manejar_error_de_negocio(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, SigafError):   # solo se registra para SigafError
        return await manejar_error_inesperado(request, exc)
    t = traduccion_de(exc)
    if t.estado >= 500:
        # Al log va el tipo y el texto original (para depurar); al cliente, no.
        log.warning("%s %s -> %s: %s", request.method, request.url.path,
                    type(exc).__name__, exc.mensaje)
    return JSONResponse(status_code=t.estado,
                        content=cuerpo(t.error, t.mensaje_fijo or exc.mensaje))


async def manejar_error_inesperado(request: Request, exc: Exception) -> JSONResponse:
    """Cualquier otra excepción (bug, base caída, permiso de la base...): 500 genérico.

    La traza completa solo queda en el log del servidor.
    """
    log.error("Error no controlado en %s %s", request.method, request.url.path,
              exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        content=cuerpo("error_interno", MENSAJE_INTERNO))


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(SigafError, manejar_error_de_negocio)
    app.add_exception_handler(Exception, manejar_error_inesperado)
