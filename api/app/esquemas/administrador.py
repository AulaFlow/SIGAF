from __future__ import annotations

from .base import Salida


class DatosDeAlumno(Salida):
    """Lo que regresa fn_datos_alumno (nombre y apellidos ya descifrados por la base)."""

    alumno_id: int
    matricula: str      # seudónimo HMAC de 64 caracteres: la matrícula real no se guarda
    nombre: str
    apellidos: str
