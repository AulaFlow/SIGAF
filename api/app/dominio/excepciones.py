"""Excepciones de negocio de SIGAF.

No saben nada de HTTP: la capa de rutas decide qué código responder.
Así el dominio se puede probar y reutilizar sin FastAPI.
"""

from __future__ import annotations


class SigafError(Exception):
    """Base de todos los errores de negocio de SIGAF."""

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class NoEncontradoError(SigafError):
    """El registro pedido no existe (o no le pertenece al usuario)."""


class PermisoDenegadoError(SigafError):
    """El usuario autenticado no puede hacer esta operación."""


class ReglaDeNegocioError(SigafError):
    """La base rechazó la operación por una regla (RAISE ... P0001)."""


class RegistroDuplicadoError(ReglaDeNegocioError):
    """Se violó una restricción UNIQUE."""


class InscripcionDuplicadaError(RegistroDuplicadoError):
    """El alumno ya está inscrito en esa materia en el periodo."""


class EntregaFueraDeTiempoError(ReglaDeNegocioError):
    """La entrega llegó después de fecha_limite + margen_tardia (SQLSTATE SG001)."""


class DatoInvalidoError(SigafError):
    """Un valor no cumple una restricción CHECK de la base."""


class CalificacionInvalidaError(DatoInvalidoError):
    """La calificación está fuera de 0 a 10 o no es válida."""
