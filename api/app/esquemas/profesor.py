from __future__ import annotations

from .base import Salida


class GrupoDelProfesor(Salida):
    grupo_id: int
    clave: str
    materia_clave: str
    materia: str
    periodo: str
    cupo: int
    inscritos: int


class AlumnoDelGrupo(Salida):
    """Sin matrícula: en la base solo está su seudónimo, que no le sirve al profesor."""

    alumno_id: int
    nombre: str
    apellidos: str
