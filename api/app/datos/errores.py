"""Traduce los errores de PostgreSQL a excepciones de negocio de SIGAF.

Se decide por SQLSTATE (el código estándar del error), no por el texto.
Lo que no se reconoce devuelve None y el llamador lo deja pasar tal cual:
un error inesperado debe verse como 500, no disfrazarse de error de negocio.
"""

from __future__ import annotations

import psycopg

from ..dominio.excepciones import (
    CalificacionInvalidaError,
    DatoInvalidoError,
    EntregaFueraDeTiempoError,
    InscripcionDuplicadaError,
    NoEncontradoError,
    RegistroDuplicadoError,
    ReglaDeNegocioError,
    SigafError,
)

SQLSTATE_ENTREGA_FUERA_DE_TIEMPO = "SG001"   # propio, lo lanza trg_estado_entrega (db/07)
SQLSTATE_REGLA = "P0001"                     # RAISE EXCEPTION genérico
SQLSTATE_NO_ENCONTRADO = "P0002"
SQLSTATE_UNICO = "23505"                     # unique_violation
SQLSTATE_CHECK = "23514"                     # check_violation


def _sqlstate(error: psycopg.Error) -> str | None:
    # psycopg 3.3 no tiene subclase para SG001: llega como DatabaseError y el
    # código está en e.sqlstate o en e.diag.sqlstate.
    return error.sqlstate or error.diag.sqlstate


def traducir_error_bd(error: psycopg.Error) -> SigafError | None:
    estado = _sqlstate(error)
    mensaje = error.diag.message_primary or "La base de datos rechazó la operación"
    restriccion = error.diag.constraint_name or ""
    tabla = error.diag.table_name or ""

    if estado == SQLSTATE_ENTREGA_FUERA_DE_TIEMPO:
        return EntregaFueraDeTiempoError(mensaje)
    if estado == SQLSTATE_NO_ENCONTRADO:
        return NoEncontradoError(mensaje)
    if estado == SQLSTATE_UNICO:
        if tabla == "inscripcion":
            return InscripcionDuplicadaError("El alumno ya está inscrito en ese grupo")
        return RegistroDuplicadoError("Ya existe un registro igual")
    if estado == SQLSTATE_CHECK:
        if "calificacion" in restriccion:
            return CalificacionInvalidaError("La calificación debe estar entre 0 y 10")
        return DatoInvalidoError(f"Valor inválido ({restriccion or 'restricción CHECK'})")
    if estado == SQLSTATE_REGLA:
        # sp_inscribir_alumno usa P0001 para varios casos; el duplicado se
        # reconoce por su mensaje. (Mejora futura: un SQLSTATE propio, como SG001.)
        if "ya está inscrito" in mensaje:
            return InscripcionDuplicadaError(mensaje)
        return ReglaDeNegocioError(mensaje)
    return None
