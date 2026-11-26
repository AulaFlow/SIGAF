"""Las cuentas de db/pruebas.sql entran con la contraseña de db/README.md (#11).

La contraseña se lee del README (no se copia aquí): así vive en un solo lugar y la
prueba avisa si alguien cambia uno de los dos archivos y no el otro.
"""

import re
from pathlib import Path

import bcrypt
import pytest

from app.servicios.autenticacion import es_hash_bcrypt

DB = Path(__file__).resolve().parents[2] / "db"
FILA_USUARIO = re.compile(r"\('([^']+@sigaf\.test)',\s*'([^']*)',\s*(\d)\)")


def contrasena_del_readme() -> bytes:
    texto = (DB / "README.md").read_text(encoding="utf-8")
    seccion = texto.split("comparten esta contraseña de desarrollo:", 1)[1]
    return re.search(r"```\s*\n(.+?)\n```", seccion).group(1).strip().encode()


def cuentas_de_pruebas_sql() -> list[tuple[str, str]]:
    texto = (DB / "pruebas.sql").read_text(encoding="utf-8")
    return [(correo, hash_) for correo, hash_, _ in FILA_USUARIO.findall(texto)]


def test_pruebas_sql_tiene_las_seis_cuentas():
    correos = [c for c, _ in cuentas_de_pruebas_sql()]
    assert correos == ["admin@sigaf.test", "profe1@sigaf.test", "alumno1@sigaf.test",
                       "alumno2@sigaf.test", "alumno3@sigaf.test", "alumno4@sigaf.test"]


@pytest.mark.parametrize(("correo", "hash_"), cuentas_de_pruebas_sql())
def test_cada_cuenta_entra_con_la_contrasena_del_readme(correo, hash_):
    assert es_hash_bcrypt(hash_) and hash_.startswith("$2b$12$"), correo
    assert bcrypt.checkpw(contrasena_del_readme(), hash_.encode()), correo


def test_cada_cuenta_tiene_su_propia_sal():
    sales = [h[:29] for _, h in cuentas_de_pruebas_sql()]     # $2b$12$ + 22 de sal
    assert len(set(sales)) == len(sales)


def test_la_contrasena_de_desarrollo_se_ve_de_prueba():
    assert b"NO-PRODUCCION" in contrasena_del_readme()
