"""Servicio de inicio de sesión (issue #11): bcrypt, hashes que no son bcrypt,
mismo trabajo en todos los casos y bitácora de accesos."""

from __future__ import annotations

from pathlib import Path

import bcrypt
import pytest

from app.datos.enrutador import BaseDistribuida, Enrutador, armar_fragmentos
from app.datos.postgres import BaseDeDatos
from app.dominio.excepciones import CredencialesInvalidasError
from app.dominio.personas import Administrador, Alumno, Profesor
from app.repositorios.usuarios import SQL_REGISTRAR_ACCESO
from app.seguridad import persona_desde_token
from app.servicios import autenticacion
from app.servicios.autenticacion import (
    HASH_FALSO,
    MENSAJE,
    Motivo,
    ServicioAutenticacion,
    comparar,
    es_hash_bcrypt,
    ip_valida,
)
from tests.fakes import CursorFalso, PoolFalso, bd_falsa, configuracion

CONTRASENA = "Contraseña-de-prueba-1"
# Costo 4 (el mínimo) para que las pruebas sean rápidas; los reales usan 12.
HASH = bcrypt.hashpw(CONTRASENA.encode(), bcrypt.gensalt(4)).decode()
CONFIG = configuracion()


def usuario(rol: str = "alumno", hash_contrasena: str = HASH, activo: bool = True) -> dict:
    return {"usuario_id": 10, "correo": "alumno@sigaf.test", "hash_contrasena": hash_contrasena,
            "activo": activo, "rol": rol}


def bitacora(cur: CursorFalso) -> list[tuple]:
    return [p for sql, p in cur.ejecutadas if sql == SQL_REGISTRAR_ACCESO]


@pytest.fixture
def checkpw_contado(monkeypatch):
    """Cuenta las llamadas a bcrypt.checkpw sin cambiar lo que hace."""
    llamadas: list[bytes] = []
    original = bcrypt.checkpw

    def contar(clave: bytes, hash_: bytes) -> bool:
        llamadas.append(hash_)
        return original(clave, hash_)

    monkeypatch.setattr(autenticacion.bcrypt, "checkpw", contar)
    return llamadas


# --- Inicios de sesión buenos --------------------------------------------

def test_alumno_entra_y_el_token_trae_sus_datos_de_la_base():
    bd, cur = bd_falsa(usuario(), [{"alumno_id": 7, "centro_academico_id": 2}])
    sesion = ServicioAutenticacion(bd, CONFIG).iniciar_sesion("alumno@sigaf.test", CONTRASENA,
                                                              "10.0.0.5")
    persona = persona_desde_token(sesion.token, CONFIG.jwt_llave)
    assert isinstance(persona, Alumno)
    assert (persona.usuario_id, persona.alumno_id, persona.centro_academico_id) == (10, 7, 2)
    assert sesion.expira_en == CONFIG.jwt_minutos * 60
    assert bitacora(cur) == [(10, True, "ok", "10.0.0.5")]


def test_profesor_entra():
    bd, _ = bd_falsa(usuario("profesor"), [{"profesor_id": 3, "centro_academico_id": 5}])
    persona = ServicioAutenticacion(bd, CONFIG).iniciar_sesion("p@sigaf.test", CONTRASENA).persona
    assert isinstance(persona, Profesor) and persona.profesor_id == 3
    assert persona.centro_academico_id == 5


def test_administrador_entra_sin_buscar_perfil():
    bd, cur = bd_falsa(usuario("administrador"))
    persona = ServicioAutenticacion(bd, CONFIG).iniciar_sesion("a@sigaf.test", CONTRASENA).persona
    assert isinstance(persona, Administrador) and persona.centro_academico_id is None
    assert len(cur.sql_de_negocio()) == 2          # buscar usuario + bitácora


def test_alumno_que_vive_en_el_fragmento_b():
    directorio = [(c, "A" if c % 2 else "B", "pg-a:5432" if c % 2 else "pg-b:5434",
                   "rep-a:5433" if c % 2 else "rep-b:5435") for c in range(1, 7)]
    pool_a, pool_b = PoolFalso(), PoolFalso()
    # A: el usuario (replicado), luego [] para el alumno. B: el alumno.
    pool_a.conexion.cursor_falso.responder(usuario(), [])
    pool_b.conexion.cursor_falso.responder([{"alumno_id": 1_000_000_007,
                                             "centro_academico_id": 4}])
    bd = BaseDistribuida(CONFIG, Enrutador(armar_fragmentos(directorio),
                                           {"A": pool_a, "B": pool_b}))

    persona = ServicioAutenticacion(bd, CONFIG).iniciar_sesion("a@sigaf.test", CONTRASENA).persona

    assert persona.alumno_id == 1_000_000_007 and persona.centro_academico_id == 4
    assert bitacora(pool_a.conexion.cursor_falso) == [(10, True, "ok", None)]   # va a A


# --- Inicios de sesión malos: todos responden igual ------------------------

CASOS_MALOS = [
    # (usuario en la base, contraseña tecleada, motivo en la bitácora)
    pytest.param(None, CONTRASENA, Motivo.SIN_USUARIO, id="correo-inexistente"),
    pytest.param(usuario(), "otra", Motivo.CONTRASENA, id="contrasena-mala"),
    pytest.param(usuario(activo=False), CONTRASENA, Motivo.INACTIVO, id="inactivo"),
    pytest.param(usuario(hash_contrasena="sintetico$" + "a" * 64), CONTRASENA,
                 Motivo.HASH_INVALIDO, id="hash-sintetico"),
    pytest.param(usuario(hash_contrasena="$2b$12$hashDeEjemploNoReal"), CONTRASENA,
                 Motivo.HASH_INVALIDO, id="hash-de-pruebas-sql"),
    pytest.param(usuario(hash_contrasena=""), CONTRASENA, Motivo.HASH_INVALIDO, id="hash-vacio"),
    pytest.param(usuario(), CONTRASENA + "x" * 80, Motivo.CONTRASENA, id="mas-de-72-bytes"),
]


@pytest.mark.parametrize(("fila", "tecleada", "motivo"), CASOS_MALOS)
def test_falla_con_el_mismo_error_y_queda_en_la_bitacora(fila, tecleada, motivo, checkpw_contado):
    bd, cur = bd_falsa(fila)
    with pytest.raises(CredencialesInvalidasError) as error:
        ServicioAutenticacion(bd, CONFIG).iniciar_sesion("x@sigaf.test", tecleada, "::1")
    assert error.value.mensaje == MENSAJE                       # mismo texto en todos
    usuario_id = None if fila is None else 10
    assert bitacora(cur) == [(usuario_id, False, motivo.value, "::1")]
    assert len(checkpw_contado) == 1                            # mismo trabajo en todos


def test_mas_de_72_bytes_no_entra_aunque_los_primeros_72_coincidan():
    larga = "a" * 72
    hash_ = bcrypt.hashpw(larga.encode(), bcrypt.gensalt(4)).decode()
    assert comparar(larga, hash_) is Motivo.OK
    assert comparar(larga + "b", hash_) is Motivo.CONTRASENA


def test_hash_con_buen_formato_que_bcrypt_rechaza_no_da_500(monkeypatch):
    def rechazar(clave, hash_):
        raise ValueError("Invalid salt")

    monkeypatch.setattr(autenticacion.bcrypt, "checkpw", rechazar)
    assert comparar(CONTRASENA, HASH) is Motivo.HASH_INVALIDO


@pytest.mark.parametrize(
    ("fila", "esperado"),
    [(usuario(), HASH.encode()), (None, HASH_FALSO),
     (usuario(hash_contrasena="sintetico$abc"), HASH_FALSO)],
    ids=["hash-real", "sin-usuario", "sintetico"],
)
def test_sin_hash_real_se_compara_contra_el_hash_falso(fila, esperado, checkpw_contado):
    bd, _ = bd_falsa(fila, [{"alumno_id": 7, "centro_academico_id": 2}])
    try:
        ServicioAutenticacion(bd, CONFIG).iniciar_sesion("x@sigaf.test", CONTRASENA)
    except CredencialesInvalidasError:
        pass
    assert checkpw_contado == [esperado]


def test_el_hash_falso_tiene_el_costo_de_los_reales():
    assert es_hash_bcrypt(HASH_FALSO.decode()) and HASH_FALSO.startswith(b"$2b$12$")


# --- Bitácora y datos raros ----------------------------------------------

def test_si_la_bitacora_falla_no_hay_sesion():
    class CursorSinBitacora(CursorFalso):
        def execute(self, sql, parametros=()):
            if sql == SQL_REGISTRAR_ACCESO:
                raise RuntimeError("no existe la tabla bitacora_acceso")
            super().execute(sql, parametros)

    pool = PoolFalso()
    pool.conexion.cursor_falso = CursorSinBitacora().responder(usuario("administrador"))
    bd = BaseDeDatos(CONFIG, pool)
    with pytest.raises(RuntimeError, match="bitacora_acceso"):
        ServicioAutenticacion(bd, CONFIG).iniciar_sesion("a@sigaf.test", CONTRASENA)


@pytest.mark.parametrize("filas", [[], [{"alumno_id": 1, "centro_academico_id": 1}] * 2],
                         ids=["sin-perfil", "dos-perfiles"])
def test_rol_alumno_sin_un_perfil_unico_es_error_de_datos(filas):
    bd, cur = bd_falsa(usuario(), filas)
    with pytest.raises(RuntimeError, match="perfiles"):
        ServicioAutenticacion(bd, CONFIG).iniciar_sesion("a@sigaf.test", CONTRASENA)
    assert bitacora(cur) == []


@pytest.mark.parametrize(
    ("ip", "esperado"),
    [("10.0.0.5", "10.0.0.5"), ("::1", "::1"), ("testclient", None), ("", None), (None, None),
     ("10.0.0.5; DROP TABLE x", None)],
)
def test_ip_valida(ip, esperado):
    assert ip_valida(ip) == esperado


@pytest.mark.parametrize("texto", [None, "", "sintetico$abc", "$2b$12$corto", "$2b$99$" + "a" * 53])
def test_no_es_hash_bcrypt(texto):
    assert not es_hash_bcrypt(texto)


def test_motivos_iguales_al_check_de_la_base():
    sql = (Path(__file__).resolve().parents[2] / "db" / "08_bitacora_acceso.sql").read_text(
        encoding="utf-8")
    for motivo in Motivo:
        assert f"'{motivo.value}'" in sql
