"""Reglas de negocio puras (sin base de datos), reutilizables y fáciles de probar."""

from __future__ import annotations

from decimal import Decimal

from .excepciones import CalificacionInvalidaError

CALIFICACION_MINIMA = Decimal("0")
CALIFICACION_MAXIMA = Decimal("10")


def validar_calificacion(valor: Decimal) -> Decimal:
    """Escala 0-10 con máximo 2 decimales, igual que NUMERIC(4,2) y los CHECK de la base."""
    if not valor.is_finite() or not CALIFICACION_MINIMA <= valor <= CALIFICACION_MAXIMA:
        raise CalificacionInvalidaError("La calificación debe estar entre 0 y 10")
    exponente = valor.as_tuple().exponent
    if isinstance(exponente, int) and exponente < -2:
        raise CalificacionInvalidaError("La calificación admite máximo 2 decimales")
    return valor
