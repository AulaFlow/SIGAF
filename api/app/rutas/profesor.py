"""Rutas del profesor. Todo se limita a SUS grupos (profesor_id del token)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from ..dominio.personas import Profesor, Rol
from ..esquemas.calificaciones import CalificacionNueva, CalificacionRegistrada
from ..esquemas.entregas import CalificacionDeEntrega, EntregaCalificada
from ..esquemas.estadisticas import ResumenDeGrupo
from ..esquemas.profesor import AlumnoDelGrupo, GrupoDelProfesor
from ..esquemas.tareas import Tarea, TareaNueva
from ..seguridad import requiere_rol
from .respuestas import CONFLICTO, NO_ENCONTRADO, SIN_ANALITICA, errores
from .servicios import Estadisticas, IdRuta, Profesores

router = APIRouter(prefix="/profesor", tags=["profesor"], responses=errores())

ProfesorActual = Annotated[Profesor, Depends(requiere_rol(Rol.PROFESOR))]


@router.get("/grupos", response_model=list[GrupoDelProfesor], summary="Mis grupos")
def grupos(profesor: ProfesorActual, servicio: Profesores) -> list[GrupoDelProfesor]:
    """Grupos que imparte el profesor, con cupo e inscritos."""
    return servicio.grupos(profesor)


@router.get("/grupos/{grupo_id}/alumnos", response_model=list[AlumnoDelGrupo],
            summary="Alumnos de mi grupo", responses=errores(NO_ENCONTRADO))
def alumnos_de_grupo(grupo_id: IdRuta, profesor: ProfesorActual,
                     servicio: Profesores) -> list[AlumnoDelGrupo]:
    """Lista del grupo con nombre (descifrado solo para sus grupos), promedio y asistencia."""
    return servicio.alumnos_de_grupo(profesor, grupo_id)


@router.post("/grupos/{grupo_id}/tareas", response_model=Tarea,
             status_code=status.HTTP_201_CREATED, summary="Crear una tarea",
             responses=errores(NO_ENCONTRADO))
def crear_tarea(grupo_id: IdRuta, datos: TareaNueva, profesor: ProfesorActual,
                servicio: Profesores) -> Tarea:
    """El profesor fija la fecha límite y el margen de entrega tardía (48 h si no lo da)."""
    return servicio.crear_tarea(profesor, grupo_id, datos)


@router.put("/entregas/{entrega_id}/calificacion", response_model=EntregaCalificada,
            summary="Calificar una entrega", responses=errores(NO_ENCONTRADO))
def calificar_entrega(entrega_id: IdRuta, datos: CalificacionDeEntrega,
                      profesor: ProfesorActual, servicio: Profesores) -> EntregaCalificada:
    """Calificación de 0 a 10 y retroalimentación opcional."""
    return servicio.calificar_entrega(profesor, entrega_id, datos)


@router.post("/calificaciones", response_model=CalificacionRegistrada,
             status_code=status.HTTP_201_CREATED, summary="Registrar una calificación",
             responses=errores(NO_ENCONTRADO, CONFLICTO))
def registrar_calificacion(datos: CalificacionNueva, profesor: ProfesorActual,
                           servicio: Profesores) -> CalificacionRegistrada:
    """Parcial o final de una inscripción de sus grupos."""
    return servicio.registrar_calificacion(profesor, datos)


@router.get("/grupos/{grupo_id}/resumen", response_model=list[ResumenDeGrupo],
            summary="Resumen de mi grupo", responses=errores(NO_ENCONTRADO, SIN_ANALITICA))
def resumen_de_grupo(grupo_id: IdRuta, profesor: ProfesorActual,
                     servicio: Estadisticas) -> list[ResumenDeGrupo]:
    """Promedio, % de aprobados y % de asistencia del grupo (desde MongoDB)."""
    return servicio.resumen_de_grupo(profesor, grupo_id)
