from __future__ import annotations

from ..datos.postgres import BaseDeDatos
from ..dominio.excepciones import NoEncontradoError
from ..dominio.personas import Alumno
from ..esquemas.alumno import MateriaBoleta, MisDatos, Pendiente, SituacionAcademica
from ..esquemas.entregas import EntregaNueva, EntregaRegistrada
from ..repositorios.alumno import RepositorioAlumno
from ..repositorios.entregas import RepositorioEntregas


class ServicioAlumno:
    """Todo lo que hace un alumno sobre SUS datos. El alumno_id sale siempre del
    objeto Alumno (construido a partir del token), nunca de la petición."""

    def __init__(self, bd: BaseDeDatos) -> None:
        self._bd = bd

    def mis_datos(self, alumno: Alumno) -> MisDatos:
        with self._bd.transaccion(alumno) as cur:
            fila = RepositorioAlumno(cur).mis_datos()
        if fila is None:
            raise NoEncontradoError("No hay datos personales registrados")
        return MisDatos(**fila)

    def boleta(self, alumno: Alumno) -> list[MateriaBoleta]:
        with self._bd.transaccion(alumno) as cur:
            filas = RepositorioAlumno(cur).boleta(alumno.alumno_id)
        return [MateriaBoleta(**f) for f in filas]

    def pendientes(self, alumno: Alumno) -> list[Pendiente]:
        with self._bd.transaccion(alumno) as cur:
            filas = RepositorioAlumno(cur).pendientes(alumno.alumno_id)
        return [Pendiente(**f) for f in filas]

    def situacion(self, alumno: Alumno) -> SituacionAcademica:
        with self._bd.transaccion(alumno) as cur:
            fila = RepositorioAlumno(cur).situacion(alumno.alumno_id)
        if fila is None:
            raise NoEncontradoError("No se encontró la situación académica")
        return SituacionAcademica(**fila)

    def entregar(self, alumno: Alumno, tarea_id: int, datos: EntregaNueva) -> EntregaRegistrada:
        with self._bd.transaccion(alumno) as cur:
            repo = RepositorioEntregas(cur)
            inscripcion_id = repo.inscripcion_para_tarea(tarea_id, alumno.alumno_id)
            if inscripcion_id is None:
                # Mismo mensaje si no existe o si no es suya: no revela tareas ajenas.
                raise NoEncontradoError("La tarea no existe o no es de tus grupos")
            fila = repo.registrar(tarea_id, inscripcion_id, datos)
        # Si pasó el margen, la base lanzó SG001 y aquí ya llegó EntregaFueraDeTiempoError.
        return EntregaRegistrada(**fila)
