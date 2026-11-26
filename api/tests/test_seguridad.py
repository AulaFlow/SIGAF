"""Token de sesión (issue #11): crear_token() y persona_desde_token()."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from app.dominio.personas import Administrador, Alumno, Profesor
from app.seguridad import ALGORITMO, crear_token, persona_desde_token

LLAVE = "j" * 32
OTRA_LLAVE = "k" * 32

ALUMNO = Alumno(10, "alumno@sigaf.test", alumno_id=7, centro_academico_id=2)
PROFESOR = Profesor(20, "profe@sigaf.test", profesor_id=3, centro_academico_id=5)
ADMIN = Administrador(1, "admin@sigaf.test")


def claims_validos(**cambios: object) -> dict:
    """Claims de un alumno válido; con cambios=None se quita ese claim."""
    ahora = datetime.now(UTC)
    claims = {"sub": "10", "rol": "alumno", "correo": "alumno@sigaf.test", "centro": 2,
              "alumno_id": 7, "iat": ahora, "exp": ahora + timedelta(minutes=5)}
    claims.update(cambios)
    return {k: v for k, v in claims.items() if v is not None}


def firmar(claims: dict, llave: str = LLAVE, algoritmo: str = ALGORITMO) -> str:
    return jwt.encode(claims, llave, algorithm=algoritmo)


def assert_401(token: str, llave: str = LLAVE) -> None:
    with pytest.raises(HTTPException) as error:
        persona_desde_token(token, llave)
    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


# --- Ida y vuelta: lo que se firma es lo que se lee ------------------------

@pytest.mark.parametrize("persona", [ALUMNO, PROFESOR, ADMIN], ids=["alumno", "profesor", "admin"])
def test_ida_y_vuelta_conserva_clase_ids_y_centro(persona):
    leida = persona_desde_token(crear_token(persona, LLAVE, 60), LLAVE)
    assert type(leida) is type(persona)
    assert leida.rol is persona.rol
    assert (leida.usuario_id, leida.correo, leida.centro_academico_id) == (
        persona.usuario_id, persona.correo, persona.centro_academico_id)
    assert getattr(leida, "alumno_id", None) == getattr(persona, "alumno_id", None)
    assert getattr(leida, "profesor_id", None) == getattr(persona, "profesor_id", None)


def test_contenido_del_token():
    ahora = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)   # en el pasado: iat futuro se rechaza
    token = crear_token(ALUMNO, LLAVE, 30, ahora=ahora)
    claims = jwt.decode(token, LLAVE, algorithms=[ALGORITMO], options={"verify_exp": False})
    assert claims["sub"] == "10"                                   # texto, no número
    assert claims["exp"] - claims["iat"] == 30 * 60
    assert jwt.get_unverified_header(token)["alg"] == "HS256"
    assert "profesor_id" not in claims
    assert not any("contrasena" in k or "hash" in k for k in claims)


# --- Tokens que deben rechazarse ------------------------------------------

def test_token_vencido():
    hace_dos_horas = datetime.now(UTC) - timedelta(hours=2)
    assert_401(crear_token(ALUMNO, LLAVE, 60, ahora=hace_dos_horas))


def test_firma_con_otra_llave():
    assert_401(crear_token(ALUMNO, OTRA_LLAVE, 60))


def test_claim_alterado_invalida_la_firma():
    # Un alumno que cambia su alumno_id en el token: la firma ya no cuadra.
    cabecera, _, firma = crear_token(ALUMNO, LLAVE, 60).split(".")
    otro = firmar(claims_validos(alumno_id=8), OTRA_LLAVE).split(".")[1]
    assert_401(f"{cabecera}.{otro}.{firma}")


def test_alg_none_rechazado():
    assert_401(jwt.encode(claims_validos(), None, algorithm="none"))


def test_otro_algoritmo_rechazado():
    # Aunque la firma sea válida con esa llave, solo aceptamos HS256.
    llave_larga = "j" * 64                     # HS512 pide 64 bytes
    assert_401(firmar(claims_validos(), llave_larga, algoritmo="HS512"), llave_larga)


@pytest.mark.parametrize("falta", ["sub", "rol", "correo", "iat", "exp"])
def test_falta_claim_obligatorio(falta):
    assert_401(firmar(claims_validos(**{falta: None})))


@pytest.mark.parametrize(
    "cambio",
    [
        {"rol": "superusuario"},                  # rol que no existe
        {"rol": "profesor"},                      # profesor sin profesor_id
        {"alumno_id": None},                      # alumno sin alumno_id
        {"alumno_id": "7"},                       # id como texto
        {"alumno_id": 0},                         # id no positivo
        {"sub": "abc"},
        {"sub": "-1"},
        {"centro": "dos"},
        {"correo": "sin-arroba"},
        {"correo": 123},
    ],
    ids=lambda c: next(iter(c.items())).__repr__(),
)
def test_claims_invalidos(cambio):
    assert_401(firmar(claims_validos(**cambio)))


@pytest.mark.parametrize("basura", ["", "abc", "a.b.c", "Bearer x.y.z"])
def test_texto_que_no_es_token(basura):
    assert_401(basura)
