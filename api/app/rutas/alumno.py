"""Rutas del alumno. Todo es sobre SUS datos: el alumno_id sale del token."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from ..dominio.personas import Alumno, Rol
from ..esquemas.alumno import MateriaBoleta, MisDatos, Pendiente, SituacionAcademica
from ..esquemas.entregas import EntregaNueva, EntregaRegistrada
from ..esquemas.estadisticas import ActividadDelAlumno
from ..esquemas.inscripciones import InscripcionCreada, InscripcionNueva
from ..seguridad import requiere_rol
from .respuestas import CONFLICTO, NO_ENCONTRADO, SIN_ANALITICA, errores
from .servicios import Alumnos, Estadisticas, IdRuta, Inscripciones

router = APIRouter(prefix="/alumno", tags=["alumno"], responses=errores())

AlumnoActual = Annotated[Alumno, Depends(requiere_rol(Rol.ALUMNO))]


@router.get("/datos", response_model=MisDatos, summary="Mis datos personales",
            responses=errores(NO_ENCONTRADO))
def mis_datos(alumno: AlumnoActual, servicio: Alumnos) -> MisDatos:
    """Nombre y apellidos del alumno, descifrados en la base solo para él."""
    return servicio.mis_datos(alumno)


@router.get("/boleta", response_model=list[MateriaBoleta], summary="Mi boleta")
def boleta(alumno: AlumnoActual, servicio: Alumnos) -> list[MateriaBoleta]:
    """Materias inscritas con sus parciales, promedio y final."""
    return servicio.boleta(alumno)


@router.get("/pendientes", response_model=list[Pendiente], summary="Mis tareas pendientes")
def pendientes(alumno: AlumnoActual, servicio: Alumnos) -> list[Pendiente]:
    """Tareas sin entregar que todavía aceptan entrega (a tiempo o como tardía)."""
    return servicio.pendientes(alumno)


@router.get("/situacion", response_model=SituacionAcademica, summary="Mi situación académica",
            responses=errores(NO_ENCONTRADO))
def situacion(alumno: AlumnoActual, servicio: Alumnos) -> SituacionAcademica:
    """Materias aprobadas y reprobadas, créditos y promedio general."""
    return servicio.situacion(alumno)


@router.post("/tareas/{tarea_id}/entregas", response_model=EntregaRegistrada,
             status_code=status.HTTP_201_CREATED, summary="Entregar una tarea",
             responses=errores(NO_ENCONTRADO, CONFLICTO))
def entregar(tarea_id: IdRuta, datos: EntregaNueva, alumno: AlumnoActual,
             servicio: Alumnos) -> EntregaRegistrada:
    """La fecha la pone la base. Pasado el margen de la tarea se rechaza (409)."""
    return servicio.entregar(alumno, tarea_id, datos)


@router.post("/inscripciones", response_model=InscripcionCreada,
             status_code=status.HTTP_201_CREATED, summary="Inscribirme a un grupo",
             responses=errores(NO_ENCONTRADO, CONFLICTO))
def inscribirme(datos: InscripcionNueva, alumno: AlumnoActual,
                servicio: Inscripciones) -> InscripcionCreada:
    """El alumno solo se inscribe a sí mismo; el grupo va en el body."""
    return servicio.inscribir(alumno, datos.grupo_id)


@router.get("/actividad", response_model=list[ActividadDelAlumno], summary="Mi actividad",
            responses=errores(SIN_ANALITICA))
def mi_actividad(alumno: AlumnoActual, servicio: Estadisticas) -> list[ActividadDelAlumno]:
    """Entregas a tiempo, tardías, no entregadas y faltas por periodo (desde MongoDB;
    puede ir un poco atrás de PostgreSQL: ver actualizado_en)."""
    return servicio.mi_actividad(alumno)
