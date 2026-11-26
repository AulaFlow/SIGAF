"""POST /auth/login (issue #11): la ruta, el 401 con WWW-Authenticate y el flujo
completo login -> token -> ruta protegida."""

from __future__ import annotations

from unittest.mock import Mock

import bcrypt
import pytest
from fastapi.testclient import TestClient

from app.dependencias import obtener_bd
from app.dominio.excepciones import CredencialesInvalidasError
from app.dominio.personas import Alumno
from app.main import crear_app
from app.rutas.servicios import servicio_alumno, servicio_autenticacion
from app.seguridad import crear_token, persona_desde_token
from app.servicios.alumno import ServicioAlumno
from app.servicios.autenticacion import MENSAJE, ServicioAutenticacion, Sesion
from tests.fakes import bd_falsa, configuracion, mongo_falso

CONFIG = configuracion()
ALUMNO = Alumno(10, "alumno@sigaf.test", alumno_id=7, centro_academico_id=2)
CORRECTO = {"correo": "alumno@sigaf.test", "contrasena": "Contraseña-1"}


def _app():
    return crear_app(CONFIG, fabrica_pool=lambda config: None, fabrica_mongo=mongo_falso)


@pytest.fixture
def cliente_y_servicio() -> tuple[TestClient, Mock]:
    app = _app()
    servicio = Mock(spec=ServicioAutenticacion)
    servicio.iniciar_sesion.return_value = Sesion(crear_token(ALUMNO, CONFIG.jwt_llave, 60),
                                                  3600, ALUMNO)
    app.dependency_overrides[servicio_autenticacion] = lambda: servicio
    return TestClient(app), servicio


def test_login_correcto_responde_el_token(cliente_y_servicio):
    cliente, _ = cliente_y_servicio
    r = cliente.post("/auth/login", json=CORRECTO)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["token_type"] == "bearer" and cuerpo["expira_en"] == 3600
    assert cuerpo["rol"] == "alumno"
    assert persona_desde_token(cuerpo["access_token"], CONFIG.jwt_llave).usuario_id == 10


def test_el_servicio_recibe_correo_en_minusculas_contrasena_intacta_e_ip(cliente_y_servicio):
    cliente, servicio = cliente_y_servicio
    cliente.post("/auth/login", json={"correo": " Alumno@SIGAF.test ", "contrasena": " a b "})
    servicio.iniciar_sesion.assert_called_once_with("alumno@sigaf.test", " a b ", "testclient")


def test_credenciales_invalidas_401_con_formato_y_www_authenticate(cliente_y_servicio):
    cliente, servicio = cliente_y_servicio
    servicio.iniciar_sesion.side_effect = CredencialesInvalidasError(MENSAJE)
    r = cliente.post("/auth/login", json=CORRECTO)
    assert r.status_code == 401
    assert r.json() == {"error": "credenciales_invalidas", "mensaje": MENSAJE}
    assert r.headers["www-authenticate"] == "Bearer"


def test_login_no_pide_token(cliente_y_servicio):
    cliente, _ = cliente_y_servicio
    r = cliente.post("/auth/login", json=CORRECTO,
                     headers={"Authorization": "Bearer token-vencido-o-basura"})
    assert r.status_code == 200


@pytest.mark.parametrize(
    "cuerpo",
    [{}, {"correo": "alumno@sigaf.test"}, {**CORRECTO, "rol": "administrador"},
     {**CORRECTO, "correo": "no-es-correo"}, {**CORRECTO, "contrasena": {"$ne": ""}}],
    ids=["vacio", "sin-contrasena", "rol-colado", "correo-invalido", "nosql"],
)
def test_entrada_invalida_422_sin_llamar_al_servicio(cliente_y_servicio, cuerpo):
    cliente, servicio = cliente_y_servicio
    assert cliente.post("/auth/login", json=cuerpo).status_code == 422
    servicio.iniciar_sesion.assert_not_called()


def test_contrasena_larga_no_regresa_en_la_respuesta(cliente_y_servicio):
    # Más de 72 bytes llega al servicio (que responde 401), no a un 422 que la repita.
    cliente, servicio = cliente_y_servicio
    servicio.iniciar_sesion.side_effect = CredencialesInvalidasError(MENSAJE)
    larga = "MiContraseñaSecreta" * 10
    r = cliente.post("/auth/login", json={**CORRECTO, "contrasena": larga})
    assert r.status_code == 401
    assert "MiContraseñaSecreta" not in r.text


def test_la_fabrica_usa_la_configuracion_de_la_app():
    app = _app()
    peticion = Mock(app=app)
    servicio = servicio_autenticacion(bd=object(), request=peticion)
    assert isinstance(servicio, ServicioAutenticacion)
    assert servicio._config is CONFIG


# --- Flujo completo: login con el servicio real -> token -> ruta protegida --

def test_flujo_completo_login_y_luego_boleta():
    hash_ = bcrypt.hashpw(b"Contrasena-1", bcrypt.gensalt(4)).decode()
    bd, cur = bd_falsa(
        {"usuario_id": 10, "correo": "alumno@sigaf.test", "hash_contrasena": hash_,
         "activo": True, "rol": "alumno"},
        [{"alumno_id": 7, "centro_academico_id": 2}],
    )
    app = _app()
    app.dependency_overrides[obtener_bd] = lambda: bd
    alumnos = Mock(spec=ServicioAlumno)
    alumnos.boleta.return_value = []
    app.dependency_overrides[servicio_alumno] = lambda: alumnos
    cliente = TestClient(app)

    r = cliente.post("/auth/login", json={"correo": "ALUMNO@sigaf.test",
                                          "contrasena": "Contrasena-1"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    r = cliente.get("/alumno/boleta", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    (alumno,), _ = alumnos.boleta.call_args
    assert alumno.alumno_id == 7 and alumno.centro_academico_id == 2
    # Quedó en la bitácora; la IP "testclient" no es IP: se guarda NULL.
    assert [p for sql, p in cur.ejecutadas if "bitacora_acceso" in sql] == [
        (10, True, "ok", None)]
