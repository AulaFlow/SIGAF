"""Rutas del administrador (#7) y formato de error de punta a punta, sin base."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.dominio.excepciones import InscripcionDuplicadaError, NoEncontradoError
from app.dominio.personas import Administrador, Alumno, Persona, Profesor
from app.esquemas.administrador import DatosDeAlumno
from app.esquemas.inscripciones import InscripcionCreada, InscripcionPorAdmin
from app.main import crear_app
from app.rutas.admin import servicio_administrador
from app.seguridad import usuario_actual
from app.servicios.administrador import ServicioAdministrador
from tests.fakes import configuracion, mongo_falso

ADMIN = Administrador(usuario_id=1, correo="admin@sigaf.test")
ALUMNO = Alumno(usuario_id=10, correo="alumno@sigaf.test", alumno_id=7, centro_academico_id=2)
PROFESOR = Profesor(usuario_id=20, correo="profe@sigaf.test", profesor_id=3,
                    centro_academico_id=1)
RUTAS = [("post", "/admin/inscripciones"), ("get", "/admin/alumnos/8/datos")]


class Entorno:
    def __init__(self) -> None:
        self.app = crear_app(configuracion(), fabrica_pool=lambda config: None,
                             fabrica_mongo=mongo_falso)
        self.servicio = Mock(spec=ServicioAdministrador)
        self.app.dependency_overrides[servicio_administrador] = lambda: self.servicio
        self.cliente = TestClient(self.app)

    def como(self, persona: Persona | None) -> TestClient:
        if persona is not None:
            self.app.dependency_overrides[usuario_actual] = lambda: persona
        return self.cliente


@pytest.fixture
def e() -> Entorno:
    return Entorno()


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS)
def test_sin_sesion_responde_401(e, metodo, ruta):
    assert e.como(None).request(metodo, ruta, json={}).status_code == 401


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS)
@pytest.mark.parametrize("persona", [ALUMNO, PROFESOR])
def test_otros_roles_reciben_403(e, metodo, ruta, persona):
    assert e.como(persona).request(metodo, ruta, json={"grupo_id": 5, "alumno_id": 8}
                                   ).status_code == 403
    assert e.servicio.method_calls == []


def test_admin_inscribe(e):
    e.servicio.inscribir.return_value = InscripcionCreada(inscripcion_id=90, alumno_id=8,
                                                          grupo_id=5)
    r = e.como(ADMIN).post("/admin/inscripciones", json={"grupo_id": 5, "alumno_id": 8})
    assert r.status_code == 201 and r.json()["inscripcion_id"] == 90
    e.servicio.inscribir.assert_called_once_with(ADMIN, InscripcionPorAdmin(grupo_id=5,
                                                                            alumno_id=8))


@pytest.mark.parametrize("cuerpo", [
    {"grupo_id": 5},                                   # falta alumno_id
    {"grupo_id": 5, "alumno_id": "8"},                 # texto donde va número
    {"grupo_id": 5, "alumno_id": {"$gt": 0}},          # intento de inyección NoSQL
    {"grupo_id": 5, "alumno_id": 8, "estado": "x"},    # campo no declarado
    {"grupo_id": 0, "alumno_id": 8},                   # id no positivo
])
def test_inscripcion_invalida_es_422_sin_llamar_al_servicio(e, cuerpo):
    assert e.como(ADMIN).post("/admin/inscripciones", json=cuerpo).status_code == 422
    e.servicio.inscribir.assert_not_called()


def test_inscripcion_duplicada_es_409_con_formato(e):
    e.servicio.inscribir.side_effect = InscripcionDuplicadaError("Ya está inscrito")
    r = e.como(ADMIN).post("/admin/inscripciones", json={"grupo_id": 5, "alumno_id": 8})
    assert r.status_code == 409
    assert r.json() == {"error": "inscripcion_duplicada", "mensaje": "Ya está inscrito"}


def test_admin_ve_datos_de_un_alumno(e):
    e.servicio.datos_alumno.return_value = DatosDeAlumno(
        alumno_id=8, matricula="f" * 64, nombre="Ana", apellidos="Pérez Luna")
    r = e.como(ADMIN).get("/admin/alumnos/8/datos")
    assert r.status_code == 200 and r.json()["apellidos"] == "Pérez Luna"
    e.servicio.datos_alumno.assert_called_once_with(ADMIN, 8)


@pytest.mark.parametrize("alumno_id", ["0", "-1", "abc", str(2**63)])
def test_id_invalido_en_la_url_es_422(e, alumno_id):
    assert e.como(ADMIN).get(f"/admin/alumnos/{alumno_id}/datos").status_code == 422
    e.servicio.datos_alumno.assert_not_called()


def test_alumno_inexistente_es_404_con_formato(e):
    e.servicio.datos_alumno.side_effect = NoEncontradoError("El alumno no existe")
    r = e.como(ADMIN).get("/admin/alumnos/8/datos")
    assert r.status_code == 404
    assert r.json() == {"error": "no_encontrado", "mensaje": "El alumno no existe"}


def test_openapi_documenta_las_2_rutas_de_admin_igual_que_las_demas(e):
    rutas = {r: m for r, m in e.app.openapi()["paths"].items() if r.startswith("/admin")}
    assert set(rutas) == {"/admin/inscripciones", "/admin/alumnos/{alumno_id}/datos"}
    for ruta, metodos in rutas.items():
        for op in metodos.values():
            assert op["tags"] == ["administrador"] and op["summary"], ruta
            assert op["security"] == [{"HTTPBearer": []}], ruta
            assert {"401", "403", "404"} <= set(op["responses"]), ruta


def test_la_fabrica_arma_el_servicio_con_la_base():
    bd = object()
    servicio = servicio_administrador(bd)
    assert isinstance(servicio, ServicioAdministrador) and servicio._bd is bd
