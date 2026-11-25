from __future__ import annotations

from ..datos.mongo import RepositorioEstadisticas
from ..datos.postgres import BaseDeDatos
from ..dominio.excepciones import NoEncontradoError, PermisoDenegadoError
from ..dominio.personas import Alumno, Persona, Profesor, Rol
from ..esquemas.estadisticas import (
    ActividadDelAlumno,
    Distribucion,
    EntregasCentro,
    PromedioMateria,
    RangoCalificaciones,
    ResumenDeGrupo,
)
from ..repositorios.profesor import RepositorioProfesor

# Los indicadores agregados (sin datos personales) los ven profesores y administradores.
ROLES_AGREGADOS = (Rol.PROFESOR, Rol.ADMINISTRADOR)
MAXIMO_MATERIAS = 50


class ServicioEstadisticas:
    """Lee la base analítica (MongoDB). Para saber si un grupo es del profesor
    consulta PostgreSQL, que es la fuente de verdad (consistencia fuerte)."""

    def __init__(self, repo: RepositorioEstadisticas, bd: BaseDeDatos) -> None:
        self._repo = repo
        self._bd = bd

    @staticmethod
    def _exigir_rol(persona: Persona) -> None:
        if not persona.es(*ROLES_AGREGADOS):
            raise PermisoDenegadoError("Solo profesores y administradores ven estadísticas")

    def mi_actividad(self, alumno: Alumno) -> list[ActividadDelAlumno]:
        return [ActividadDelAlumno(**d) for d in self._repo.actividad_de_alumno(alumno.alumno_id)]

    def resumen_de_grupo(self, profesor: Profesor, grupo_id: int) -> list[ResumenDeGrupo]:
        with self._bd.transaccion(profesor) as cur:
            es_suyo = RepositorioProfesor(cur).grupo_es_suyo(grupo_id, profesor.profesor_id)
        if not es_suyo:
            raise NoEncontradoError("El grupo no existe o no es tuyo")
        return [ResumenDeGrupo(**d) for d in self._repo.resumen_de_grupo(grupo_id)]

    def distribucion(self, persona: Persona, periodo: str, tipo: str | None = None) -> Distribucion:
        self._exigir_rol(persona)
        cubetas = {d["_id"]: d["total"] for d in self._repo.distribucion(periodo, tipo)
                   if d["_id"] != "fuera_de_rango"}
        rangos = [RangoCalificaciones(desde=i, total=cubetas.get(i, 0)) for i in range(11)]
        return Distribucion(periodo=periodo, tipo=tipo, rangos=rangos,
                            total=sum(r.total for r in rangos))

    def promedio_por_materia(self, persona: Persona, periodo: str,
                             cuantas: int = 12) -> list[PromedioMateria]:
        self._exigir_rol(persona)
        cuantas = max(1, min(cuantas, MAXIMO_MATERIAS))
        return [PromedioMateria(materia_clave=d["_id"], materia=d["materia"],
                                promedio=round(d["promedio"], 2), alumnos=d["alumnos"])
                for d in self._repo.promedio_por_materia(periodo, cuantas)]

    def entregas_por_centro(self, persona: Persona, periodo: str) -> list[EntregasCentro]:
        self._exigir_rol(persona)
        return [EntregasCentro(centro=d["_id"], a_tiempo=d["a_tiempo"], tardias=d["tardias"],
                               no_entregadas=d["no_entregadas"])
                for d in self._repo.entregas_por_centro(periodo)]
