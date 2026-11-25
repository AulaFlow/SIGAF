from __future__ import annotations

from ..datos.postgres import BaseDeDatos
from ..dominio.excepciones import NoEncontradoError
from ..dominio.personas import Profesor
from ..esquemas.calificaciones import CalificacionNueva, CalificacionRegistrada
from ..esquemas.entregas import CalificacionDeEntrega, EntregaCalificada
from ..esquemas.profesor import AlumnoDelGrupo, GrupoDelProfesor
from ..esquemas.tareas import Tarea, TareaNueva
from ..repositorios.profesor import RepositorioProfesor

GRUPO_AJENO = "El grupo no existe o no es tuyo"
INSCRIPCION_AJENA = "La inscripción no existe, no está activa o no es de tus grupos"


class ServicioProfesor:
    """Casos de uso del profesor. Todo se limita a SUS grupos (profesor_id del token)."""

    def __init__(self, bd: BaseDeDatos) -> None:
        self._bd = bd

    def grupos(self, profesor: Profesor) -> list[GrupoDelProfesor]:
        with self._bd.transaccion(profesor) as cur:
            filas = RepositorioProfesor(cur).grupos(profesor.profesor_id)
        return [GrupoDelProfesor(**f) for f in filas]

    def alumnos_de_grupo(self, profesor: Profesor, grupo_id: int) -> list[AlumnoDelGrupo]:
        with self._bd.transaccion(profesor) as cur:
            repo = RepositorioProfesor(cur)
            if not repo.grupo_es_suyo(grupo_id, profesor.profesor_id):
                raise NoEncontradoError(GRUPO_AJENO)
            filas = repo.alumnos_de_grupo(profesor.profesor_id, grupo_id)
        return [AlumnoDelGrupo(**f) for f in filas]

    def crear_tarea(self, profesor: Profesor, grupo_id: int, datos: TareaNueva) -> Tarea:
        with self._bd.transaccion(profesor) as cur:
            repo = RepositorioProfesor(cur)
            if not repo.grupo_es_suyo(grupo_id, profesor.profesor_id):
                raise NoEncontradoError(GRUPO_AJENO)
            fila = repo.crear_tarea(grupo_id, datos)
        return Tarea(**fila)

    def calificar_entrega(self, profesor: Profesor, entrega_id: int,
                          datos: CalificacionDeEntrega) -> EntregaCalificada:
        with self._bd.transaccion(profesor) as cur:
            fila = RepositorioProfesor(cur).calificar_entrega(
                profesor.profesor_id, entrega_id, datos.calificacion, datos.retroalimentacion
            )
        if fila is None:
            raise NoEncontradoError("La entrega no existe o no es de tus grupos")
        return EntregaCalificada(**fila)

    def registrar_calificacion(self, profesor: Profesor,
                               datos: CalificacionNueva) -> CalificacionRegistrada:
        with self._bd.transaccion(profesor) as cur:
            fila = RepositorioProfesor(cur).registrar_calificacion(
                profesor.profesor_id, datos.inscripcion_id, datos.tipo, datos.valor
            )
        if fila is None:
            raise NoEncontradoError(INSCRIPCION_AJENA)
        return CalificacionRegistrada(**fila)
