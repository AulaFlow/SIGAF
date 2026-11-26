"""Fábricas de servicios para las rutas. En las pruebas se reemplazan con
app.dependency_overrides para no necesitar base de datos."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi import Path as RutaParam

from ..dependencias import BD, Estadisticas
from ..esquemas.base import MAX_BIGINT
from ..servicios.alumno import ServicioAlumno
from ..servicios.autenticacion import ServicioAutenticacion
from ..servicios.inscripciones import ServicioInscripciones
from ..servicios.profesor import ServicioProfesor


def servicio_alumno(bd: BD) -> ServicioAlumno:
    return ServicioAlumno(bd)


def servicio_profesor(bd: BD) -> ServicioProfesor:
    return ServicioProfesor(bd)


def servicio_inscripciones(bd: BD) -> ServicioInscripciones:
    return ServicioInscripciones(bd)


def servicio_autenticacion(bd: BD, request: Request) -> ServicioAutenticacion:
    return ServicioAutenticacion(bd, request.app.state.config)   # la llave del JWT (#11)


Alumnos = Annotated[ServicioAlumno, Depends(servicio_alumno)]
Autenticacion = Annotated[ServicioAutenticacion, Depends(servicio_autenticacion)]
Profesores = Annotated[ServicioProfesor, Depends(servicio_profesor)]
Inscripciones = Annotated[ServicioInscripciones, Depends(servicio_inscripciones)]
__all__ = ["Alumnos", "Autenticacion", "Estadisticas", "IdRuta", "Inscripciones", "Profesores"]

# Id en la URL: entero positivo que cabe en BIGINT (FastAPI convierte el texto).
IdRuta = Annotated[int, RutaParam(gt=0, le=MAX_BIGINT)]
