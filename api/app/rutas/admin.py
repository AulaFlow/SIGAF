"""Rutas del administrador (issue #7, Ricardo).

El administrador no tiene centro: el servicio averigua el fragmento del grupo o del
alumno antes de operar (ver ServicioAdministrador._ubicar).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from ..dependencias import BD
from ..dominio.personas import Administrador, Rol
from ..esquemas.administrador import DatosDeAlumno
from ..esquemas.inscripciones import InscripcionCreada, InscripcionPorAdmin
from ..seguridad import requiere_rol
from ..servicios.administrador import ServicioAdministrador
from .respuestas import CONFLICTO, NO_ENCONTRADO, errores
from .servicios import IdRuta

router = APIRouter(prefix="/admin", tags=["administrador"], responses=errores())

AdminActual = Annotated[Administrador, Depends(requiere_rol(Rol.ADMINISTRADOR))]


def servicio_administrador(bd: BD) -> ServicioAdministrador:
    return ServicioAdministrador(bd)


Administracion = Annotated[ServicioAdministrador, Depends(servicio_administrador)]


@router.post("/inscripciones", response_model=InscripcionCreada,
             status_code=status.HTTP_201_CREATED, summary="Inscribir a un alumno",
             responses=errores(NO_ENCONTRADO, CONFLICTO))
def inscribir(datos: InscripcionPorAdmin, admin: AdminActual,
              servicio: Administracion) -> InscripcionCreada:
    """Inscribe a cualquier alumno en un grupo de su carrera (alumno_id y grupo_id en el body)."""
    return servicio.inscribir(admin, datos)


@router.get("/alumnos/{alumno_id}/datos", response_model=DatosDeAlumno,
            summary="Datos personales de un alumno", responses=errores(NO_ENCONTRADO))
def datos_alumno(alumno_id: IdRuta, admin: AdminActual,
                 servicio: Administracion) -> DatosDeAlumno:
    """Nombre y apellidos descifrados por la base (fn_datos_alumno)."""
    return servicio.datos_alumno(admin, alumno_id)
