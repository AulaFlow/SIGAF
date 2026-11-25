from __future__ import annotations

from collections.abc import Callable

import psycopg

from ..datos.enrutador import BaseDistribuida
from ..datos.postgres import BaseDeDatos
from ..dominio.excepciones import NoEncontradoError
from ..dominio.personas import Administrador
from ..esquemas.administrador import DatosDeAlumno
from ..esquemas.inscripciones import InscripcionCreada, InscripcionPorAdmin
from ..repositorios.administrador import RepositorioAdministrador
from .inscripciones import ServicioInscripciones

Consulta = Callable[[psycopg.Cursor], list[int]]


class ServicioAdministrador:
    """Operaciones del administrador.

    El administrador no pertenece a ningún centro, así que su token no dice a qué
    fragmento ir. Antes de operar se averigua el centro del registro (grupo o alumno)
    y la transacción se abre en ese fragmento con centro_academico_id explícito.
    """

    def __init__(self, bd: BaseDeDatos) -> None:
        self._bd = bd

    def inscribir(self, admin: Administrador, datos: InscripcionPorAdmin) -> InscripcionCreada:
        centro = self._ubicar(
            admin, lambda cur: RepositorioAdministrador(cur).centros_del_grupo(datos.grupo_id),
            "El grupo no existe")
        # Si el alumno es de otro centro, en ese fragmento no existe: el procedimiento
        # responde P0002 ("El alumno ... no existe") y la API, 404.
        return ServicioInscripciones(self._bd).inscribir(
            admin, datos.grupo_id, datos.alumno_id, centro_academico_id=centro)

    def datos_alumno(self, admin: Administrador, alumno_id: int) -> DatosDeAlumno:
        centro = self._ubicar(
            admin, lambda cur: RepositorioAdministrador(cur).centros_del_alumno(alumno_id),
            "El alumno no existe")
        with self._bd.transaccion(admin, centro_academico_id=centro) as cur:
            fila = RepositorioAdministrador(cur).datos_alumno(alumno_id)
        if fila is None:   # existe el alumno pero no tiene datos personales registrados
            raise NoEncontradoError("El alumno no tiene datos personales registrados")
        return DatosDeAlumno(**fila)

    def _ubicar(self, admin: Administrador, consulta: Consulta, si_no_existe: str) -> int:
        """Centro del registro.

        PROVISIONAL, pendiente de decisión del equipo (fragmentación): se pregunta en
        cada fragmento con en_todos(). Las otras opciones solo cambian este método.
        Con una sola base (desarrollo sin directorio) se pregunta en esa.
        """
        if isinstance(self._bd, BaseDistribuida):
            centros = set(self._bd.en_todos(consulta, admin))
        else:
            with self._bd.transaccion(admin) as cur:
                centros = set(consulta(cur))
        if not centros:
            raise NoEncontradoError(si_no_existe)
        if len(centros) > 1:
            # Los ids de A y B no se repiten (reparto, #8); si pasa, es un error de datos.
            raise RuntimeError("El mismo id aparece en más de un centro")
        return centros.pop()
