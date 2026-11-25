from __future__ import annotations

from ..datos.postgres import BaseDeDatos
from ..dominio.personas import Persona
from ..esquemas.inscripciones import InscripcionCreada
from ..repositorios.inscripciones import RepositorioInscripciones


class ServicioInscripciones:
    """Decisión del equipo: inscriben el alumno (a sí mismo) y el administrador."""

    def __init__(self, bd: BaseDeDatos) -> None:
        self._bd = bd

    def inscribir(self, persona: Persona, grupo_id: int,
                  alumno_id: int | None = None) -> InscripcionCreada:
        # Polimorfismo: cada tipo de Persona decide a quién puede inscribir.
        objetivo = persona.alumno_a_inscribir(alumno_id)
        with self._bd.transaccion(persona) as cur:
            inscripcion_id = RepositorioInscripciones(cur).inscribir(objetivo, grupo_id)
        return InscripcionCreada(inscripcion_id=inscripcion_id, alumno_id=objetivo,
                                 grupo_id=grupo_id)
