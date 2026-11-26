"""Consultas del login (issue #11): SQL con parámetros y búsqueda en A o en B."""

import pytest

from app.datos.enrutador import BaseDistribuida, Enrutador, armar_fragmentos
from app.datos.postgres import BaseDeDatos
from app.repositorios.usuarios import (
    SQL_ALUMNO_DE_USUARIO,
    SQL_PROFESOR_DE_USUARIO,
    SQL_REGISTRAR_ACCESO,
    SQL_USUARIO_POR_CORREO,
    RepositorioUsuarios,
)
from tests.fakes import CursorFalso, PoolFalso, configuracion

# A = centros 1, 3, 5 · B = centros 2, 4, 6 (como en test_enrutamiento_servicios)
DIRECTORIO = [(c, "A" if c % 2 else "B", "pg-a:5432" if c % 2 else "pg-b:5434",
               "rep-a:5433" if c % 2 else "rep-b:5435") for c in range(1, 7)]

TODAS_LAS_SQL = [SQL_USUARIO_POR_CORREO, SQL_ALUMNO_DE_USUARIO, SQL_PROFESOR_DE_USUARIO,
                 SQL_REGISTRAR_ACCESO]


@pytest.mark.parametrize("sql", TODAS_LAS_SQL)
def test_sql_solo_con_parametros(sql):
    assert "%s" in sql and "{" not in sql        # nada de f-strings ni .format


def test_registrar_acceso_no_usa_returning():
    # sigaf_api no tiene SELECT en bitacora_acceso (db/09): RETURNING fallaría.
    assert "RETURNING" not in SQL_REGISTRAR_ACCESO.upper()


def test_por_correo_manda_el_correo_como_parametro():
    cur = CursorFalso().responder({"usuario_id": 5})
    assert RepositorioUsuarios(cur).por_correo("a@sigaf.test' OR '1'='1") == {"usuario_id": 5}
    sql, parametros = cur.ejecutadas[0]
    assert sql == SQL_USUARIO_POR_CORREO
    assert parametros == ("a@sigaf.test' OR '1'='1",)      # viaja aparte, no dentro del SQL


def test_por_correo_sin_usuario_regresa_none():
    assert RepositorioUsuarios(CursorFalso().responder(None)).por_correo("x@sigaf.test") is None


def test_registrar_acceso_manda_los_cuatro_valores():
    cur = CursorFalso()
    RepositorioUsuarios(cur).registrar_acceso(None, False, "sin_usuario", "10.0.0.1")
    assert cur.ejecutadas == [(SQL_REGISTRAR_ACCESO, (None, False, "sin_usuario", "10.0.0.1"))]


def test_alumno_del_fragmento_b_se_encuentra_con_en_todos():
    # usuario está en los dos fragmentos, pero el alumno solo en B: hay que preguntar en ambos.
    pool_a, pool_b = PoolFalso(), PoolFalso()
    pool_a.conexion.cursor_falso.responder([])
    pool_b.conexion.cursor_falso.responder([{"alumno_id": 1_000_000_007, "centro_academico_id": 4}])
    bd = BaseDistribuida(configuracion(),
                         Enrutador(armar_fragmentos(DIRECTORIO), {"A": pool_a, "B": pool_b}))

    filas = bd.en_todos(lambda cur: RepositorioUsuarios(cur).alumno_de(10))

    assert filas == [{"alumno_id": 1_000_000_007, "centro_academico_id": 4}]
    assert (pool_a.prestadas, pool_b.prestadas) == (1, 1)


def test_profesor_con_una_sola_base_se_encuentra_con_en_todos():
    pool = PoolFalso()
    pool.conexion.cursor_falso.responder([{"profesor_id": 3, "centro_academico_id": 1}])
    bd = BaseDeDatos(configuracion(), pool)

    filas = bd.en_todos(lambda cur: RepositorioUsuarios(cur).profesor_de(20))

    assert filas == [{"profesor_id": 3, "centro_academico_id": 1}]
    assert pool.conexion.cursor_falso.sql_de_negocio() == [(SQL_PROFESOR_DE_USUARIO, (20,))]
