"""Manejadores de errores (#7): cada excepción de negocio -> código HTTP y
{"error", "mensaje"}, sin detalles internos."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.dominio.excepciones import (
    CalificacionInvalidaError,
    CredencialesInvalidasError,
    DatoInvalidoError,
    EntregaFueraDeTiempoError,
    InscripcionDuplicadaError,
    NoEncontradoError,
    PermisoDenegadoError,
    RegistroDuplicadoError,
    ReglaDeNegocioError,
    ServicioNoDisponibleError,
    SigafError,
)
from app.errores_http import (
    MENSAJE_INTERNO,
    MENSAJE_NO_DISPONIBLE,
    manejar_error_de_negocio,
    registrar_manejadores,
)


class SubclaseNueva(InscripcionDuplicadaError):
    """Una excepción que no está en la tabla: hereda la traducción de su padre."""


def _cliente(error: Exception) -> TestClient:
    app = FastAPI()
    registrar_manejadores(app)

    @app.get("/falla")
    def falla() -> None:
        raise error

    # raise_server_exceptions=False: así vemos la respuesta 500 que recibe el cliente.
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("error", "estado", "codigo"),
    [
        (NoEncontradoError("La tarea no existe o no es de tus grupos"), 404, "no_encontrado"),
        (PermisoDenegadoError("Un alumno solo puede inscribirse a sí mismo"), 403,
         "permiso_denegado"),
        (EntregaFueraDeTiempoError("Ya pasó el margen"), 409, "entrega_fuera_de_tiempo"),
        (InscripcionDuplicadaError("Ya está inscrito"), 409, "inscripcion_duplicada"),
        (RegistroDuplicadoError("Ya existe un registro igual"), 409, "registro_duplicado"),
        (ReglaDeNegocioError("El grupo no tiene cupo"), 409, "regla_de_negocio"),
        (DatoInvalidoError("El administrador debe indicar alumno_id"), 422, "dato_invalido"),
        (CalificacionInvalidaError("Entre 0 y 10"), 422, "calificacion_invalida"),
        (SubclaseNueva("Ya está inscrito"), 409, "inscripcion_duplicada"),
    ],
)
def test_errores_de_negocio_con_su_mensaje(error, estado, codigo):
    r = _cliente(error).get("/falla")
    assert r.status_code == estado
    assert r.json() == {"error": codigo, "mensaje": error.mensaje}


def test_servicio_no_disponible_no_dice_cual_base_fallo():
    r = _cliente(ServicioNoDisponibleError("La base de analítica no responde")).get("/falla")
    assert r.status_code == 503
    assert r.json() == {"error": "servicio_no_disponible", "mensaje": MENSAJE_NO_DISPONIBLE}


def test_sigaf_error_generico_es_error_interno():
    r = _cliente(SigafError("detalle interno")).get("/falla")
    assert r.status_code == 500
    assert r.json() == {"error": "error_interno", "mensaje": MENSAJE_INTERNO}


def test_error_inesperado_no_filtra_detalles(caplog):
    secreto = 'relation "sigaf.alumno_datos_personales" permission denied'
    r = _cliente(RuntimeError(secreto)).get("/falla")
    assert r.status_code == 500
    assert r.json() == {"error": "error_interno", "mensaje": MENSAJE_INTERNO}
    assert secreto not in r.text
    assert secreto in caplog.text            # el detalle sí queda en el log del servidor


def test_manejador_de_negocio_con_otra_excepcion_responde_500():
    # Defensa: si alguien lo registrara para otra clase, no rompe ni filtra nada.
    peticion = Request({"type": "http", "method": "GET", "path": "/x", "headers": []})
    respuesta = asyncio.run(manejar_error_de_negocio(peticion, ValueError("x")))
    assert respuesta.status_code == 500


def test_credenciales_invalidas_es_401_con_www_authenticate():
    # Issue #11: Traduccion puede llevar encabezados; solo el 401 del login los usa.
    r = _cliente(CredencialesInvalidasError("Correo o contraseña incorrectos")).get("/falla")
    assert r.status_code == 401
    assert r.json() == {"error": "credenciales_invalidas",
                        "mensaje": "Correo o contraseña incorrectos"}
    assert r.headers["www-authenticate"] == "Bearer"


def test_los_demas_errores_no_mandan_www_authenticate():
    r = _cliente(NoEncontradoError("No existe")).get("/falla")
    assert "www-authenticate" not in r.headers
