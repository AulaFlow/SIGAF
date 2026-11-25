from __future__ import annotations

from .base import Entrada, Id, Salida


class InscripcionNueva(Entrada):
    """El alumno se inscribe a sí mismo: no manda alumno_id (sale del token)."""

    grupo_id: Id


class InscripcionPorAdmin(InscripcionNueva):
    alumno_id: Id


class InscripcionCreada(Salida):
    inscripcion_id: int
    alumno_id: int
    grupo_id: int
