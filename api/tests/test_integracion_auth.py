"""Inicio de sesión contra el esquema real (sigaf-db), sin dejar rastro (issue #11).

Necesita 01-08 + pruebas.sql cargados y se conecta como sigaf_api_svc, igual que la API.
Se omite si no hay SIGAF_PASS_API (el CI no tiene base).

El login abre sus propias transacciones y hace commit (búsqueda, perfil, bitácora).
Para no dejar renglones en bitacora_acceso, BaseQueRevierte ejecuta TODO de verdad
(incluido el INSERT, con los permisos reales de la API) y al final hace rollback.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import Mock

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.datos.postgres import BaseDeDatos
from app.dependencias import obtener_bd
from app.dominio.excepciones import CredencialesInvalidasError
from app.dominio.personas import Administrador, Alumno, Persona, Profesor
from app.main import crear_app
from app.repositorios.usuarios import RepositorioUsuarios
from app.servicios.autenticacion import ServicioAutenticacion, es_hash_bcrypt
from tests.conftest import Revertir, solo_con_base
from tests.fakes import mongo_falso
from tests.test_datos_de_prueba import contrasena_del_readme

pytestmark = solo_con_base


class BaseQueRevierte(BaseDeDatos):
    """Cada transacción corre completa contra la base y termina en rollback."""

    @contextmanager
    def transaccion(self, persona: Persona | None = None,
                    centro_academico_id: int | None = None) -> Iterator[psycopg.Cursor]:
        try:
            with super().transaccion(persona, centro_academico_id) as cur:
                yield cur
                raise Revertir
        except Revertir:
            pass


@pytest.fixture
def bd(bd_real) -> BaseQueRevierte:
    return BaseQueRevierte(bd_real._config, bd_real._pool)


@pytest.fixture
def contrasena() -> str:
    return contrasena_del_readme().decode()


# --- Repositorio: el SQL contra el esquema real ----------------------------

def test_por_correo_trae_hash_bcrypt_y_rol(bd_real):
    with bd_real.transaccion() as cur:
        fila = RepositorioUsuarios(cur).por_correo("alumno1@sigaf.test")
        assert RepositorioUsuarios(cur).por_correo("nadie@sigaf.test") is None
    assert fila["rol"] == "alumno" and fila["activo"] is True
    assert es_hash_bcrypt(fila["hash_contrasena"])


def test_perfil_de_alumno_y_profesor_con_en_todos(bd_real):
    with bd_real.transaccion() as cur:
        cur.execute("""SELECT u.correo, a.alumno_id, c.centro_academico_id
                       FROM usuario u JOIN alumno a USING (usuario_id)
                       JOIN carrera c USING (carrera_id)
                       WHERE u.correo = 'alumno1@sigaf.test'""")
        esperado_alumno = cur.fetchone()
        alumno = RepositorioUsuarios(cur).por_correo("alumno1@sigaf.test")
        profe = RepositorioUsuarios(cur).por_correo("profe1@sigaf.test")

    filas = bd_real.en_todos(lambda c: RepositorioUsuarios(c).alumno_de(alumno["usuario_id"]))
    assert filas == [{"alumno_id": esperado_alumno["alumno_id"],
                      "centro_academico_id": esperado_alumno["centro_academico_id"]}]
    filas = bd_real.en_todos(lambda c: RepositorioUsuarios(c).profesor_de(profe["usuario_id"]))
    assert len(filas) == 1 and filas[0]["profesor_id"] > 0


def test_la_api_no_puede_leer_la_bitacora_de_accesos(bd_real):
    # db/08: sigaf_api solo inserta. Leerla tiene que fallar por permisos.
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with bd_real.transaccion() as cur:
            cur.execute("SELECT count(*) FROM bitacora_acceso")


# --- Servicio: bcrypt real, bitácora con los permisos reales ---------------

@pytest.mark.parametrize(
    ("correo", "clase"),
    [("admin@sigaf.test", Administrador), ("profe1@sigaf.test", Profesor),
     ("alumno1@sigaf.test", Alumno)],
)
def test_cuentas_de_prueba_entran_con_la_contrasena_del_readme(bd, contrasena, correo, clase):
    sesion = ServicioAutenticacion(bd, bd._config).iniciar_sesion(correo, contrasena, "127.0.0.1")
    assert isinstance(sesion.persona, clase)
    if clase is not Administrador:
        assert sesion.persona.centro_academico_id is not None


@pytest.mark.parametrize(
    ("correo", "tecleada"),
    [("alumno1@sigaf.test", "otra-contrasena"), ("nadie@sigaf.test", None)],
    ids=["contrasena-mala", "correo-inexistente"],
)
def test_fallos_responden_igual_y_la_bitacora_acepta_el_registro(bd, contrasena, correo,
                                                                  tecleada):
    # Si el INSERT en bitacora_acceso no tuviera permiso, aquí saldría un error de psycopg.
    with pytest.raises(CredencialesInvalidasError):
        ServicioAutenticacion(bd, bd._config).iniciar_sesion(correo, tecleada or contrasena,
                                                             "10.0.0.1")


def test_cuenta_con_hash_que_no_es_bcrypt_no_da_500(bd, contrasena):
    # profe2@sigaf.test lo crea pruebas_seguridad.sql (S5) con '$2b$12$hashDeEjemploNoReal'.
    with bd.transaccion() as cur:
        if RepositorioUsuarios(cur).por_correo("profe2@sigaf.test") is None:
            pytest.skip("falta correr pruebas_seguridad.sql (crea profe2)")
    with pytest.raises(CredencialesInvalidasError):
        ServicioAutenticacion(bd, bd._config).iniciar_sesion("profe2@sigaf.test", contrasena)


# --- HTTP: login -> token -> ruta protegida, todo contra la base -----------

def test_flujo_http_completo_contra_la_base(bd, contrasena):
    # Sin "with TestClient": no corre el lifespan (el directorio de pruebas.sql apunta a
    # laptop1..4, que no existen aquí). La base se inyecta con dependency_overrides.
    app = crear_app(bd._config, fabrica_pool=lambda config: Mock(), fabrica_mongo=mongo_falso)
    app.dependency_overrides[obtener_bd] = lambda: bd
    cliente = TestClient(app)

    r = cliente.post("/auth/login", json={"correo": " Alumno1@SIGAF.test ",
                                          "contrasena": contrasena})
    assert r.status_code == 200, r.text
    assert r.json()["rol"] == "alumno"
    encabezados = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = cliente.get("/alumno/boleta", headers=encabezados)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)

    assert cliente.get("/profesor/grupos", headers=encabezados).status_code == 403
    r = cliente.post("/auth/login", json={"correo": "alumno1@sigaf.test",
                                          "contrasena": "otra-contrasena"})
    assert r.status_code == 401 and r.json()["error"] == "credenciales_invalidas"
