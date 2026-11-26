"""Esquemas de POST /auth/login (issue #11)."""

import pytest
from pydantic import ValidationError

from app.dominio.personas import Rol
from app.esquemas.auth import LARGO_MAXIMO_CONTRASENA, Login, Token


def test_correo_se_limpia_y_pasa_a_minusculas():
    assert Login(correo="  Alumno00012@SIGAF.Test ", contrasena="x").correo == \
        "alumno00012@sigaf.test"


def test_contrasena_no_se_recorta():
    # Entrada quita espacios a todo; la contraseña es la excepción.
    assert Login(correo="a@sigaf.test", contrasena="  con espacios  ").contrasena == \
        "  con espacios  "


def test_contrasena_de_mas_de_72_pasa_el_esquema():
    # La rechaza el servicio con 401; un 422 aquí devolvería la contraseña en "input".
    larga = "x" * 200
    assert Login(correo="a@sigaf.test", contrasena=larga).contrasena == larga


def test_la_contrasena_no_aparece_en_el_repr():
    assert "secreta" not in repr(Login(correo="a@sigaf.test", contrasena="secreta"))


@pytest.mark.parametrize(
    "datos",
    [
        {"correo": "a@sigaf.test"},                                     # falta contraseña
        {"contrasena": "x"},                                            # falta correo
        {"correo": "a@sigaf.test", "contrasena": ""},                   # vacía
        {"correo": "a@sigaf.test", "contrasena": 123456},               # no es texto
        {"correo": "a@sigaf.test", "contrasena": {"$ne": ""}},          # inyección NoSQL
        {"correo": ["a@sigaf.test"], "contrasena": "x"},
        {"correo": "sin-arroba", "contrasena": "x"},
        {"correo": "a b@sigaf.test", "contrasena": "x"},
        {"correo": "a@sigaf", "contrasena": "x"},
        {"correo": "a" * 116 + "@s.mx", "contrasena": "x"},            # 121 > 120
        {"correo": "a@sigaf.test", "contrasena": "x" * (LARGO_MAXIMO_CONTRASENA + 1)},
        {"correo": "a@sigaf.test", "contrasena": "x", "rol": "administrador"},   # extra
    ],
    ids=["sin-contrasena", "sin-correo", "vacia", "numero", "nosql", "lista", "sin-arroba",
         "espacio", "sin-dominio", "correo-largo", "contrasena-enorme", "rol-colado"],
)
def test_entradas_invalidas(datos):
    with pytest.raises(ValidationError):
        Login(**datos)


def test_token_de_salida():
    token = Token(access_token="abc", expira_en=3600, rol=Rol.ALUMNO)
    assert token.model_dump() == {"access_token": "abc", "token_type": "bearer",
                                  "expira_en": 3600, "rol": "alumno"}
