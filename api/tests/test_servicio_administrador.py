"""ServicioAdministrador (#7): el admin no tiene centro, así que primero se busca
el fragmento del grupo o del alumno y luego se opera solo en ese fragmento."""

from __future__ import annotations

import pytest

from app.datos.enrutador import BaseDistribuida, Enrutador, armar_fragmentos
from app.dominio.excepciones import NoEncontradoError
from app.dominio.personas import Administrador
from app.esquemas.inscripciones import InscripcionPorAdmin
from app.repositorios.administrador import (
    SQL_CENTRO_DEL_ALUMNO,
    SQL_CENTRO_DEL_GRUPO,
    SQL_DATOS_ALUMNO,
)
from app.repositorios.inscripciones import SQL_INSCRIBIR
from app.servicios.administrador import ServicioAdministrador
from tests.fakes import PoolFalso, bd_falsa, configuracion

ADMIN = Administrador(usuario_id=1, correo="admin@sigaf.test")
DATOS = {"alumno_id": 8, "matricula": "f" * 64, "nombre": "Ana", "apellidos": "Pérez Luna"}

# A = centros 1, 3, 5 · B = centros 2, 4, 6 (igual que el reparto del #8)
DIRECTORIO = [(c, "A" if c % 2 else "B", "pg-a:5432" if c % 2 else "pg-b:5434",
               "rep-a:5433" if c % 2 else "rep-b:5435") for c in range(1, 7)]


def _distribuida() -> tuple[BaseDistribuida, PoolFalso, PoolFalso]:
    pool_a, pool_b = PoolFalso(), PoolFalso()
    enrutador = Enrutador(armar_fragmentos(DIRECTORIO), {"A": pool_a, "B": pool_b})
    return BaseDistribuida(configuracion(), enrutador), pool_a, pool_b


def _sql(pool: PoolFalso) -> list[tuple[str, tuple]]:
    return pool.conexion.cursor_falso.sql_de_negocio()


# ------------------------------------------------------------ con dos fragmentos

def test_inscribe_en_el_fragmento_del_grupo():
    bd, pool_a, pool_b = _distribuida()
    # A no tiene el grupo (fetchall vacío); B sí, del centro 4, y luego inscribe.
    pool_b.conexion.cursor_falso.responder([{"centro_academico_id": 4}], {"p_inscripcion": 90})
    r = ServicioAdministrador(bd).inscribir(ADMIN, InscripcionPorAdmin(grupo_id=5, alumno_id=8))
    assert (r.inscripcion_id, r.alumno_id, r.grupo_id) == (90, 8, 5)
    assert _sql(pool_a) == [(SQL_CENTRO_DEL_GRUPO, (5,))]                 # solo preguntó
    assert _sql(pool_b) == [(SQL_CENTRO_DEL_GRUPO, (5,)), (SQL_INSCRIBIR, (8, 5))]
    assert pool_b.conexion.commits == 2


def test_datos_del_alumno_en_su_fragmento():
    bd, pool_a, pool_b = _distribuida()
    pool_a.conexion.cursor_falso.responder([{"centro_academico_id": 3}], DATOS)
    r = ServicioAdministrador(bd).datos_alumno(ADMIN, 8)
    assert (r.nombre, r.apellidos) == ("Ana", "Pérez Luna")
    assert _sql(pool_a) == [(SQL_CENTRO_DEL_ALUMNO, (8,)), (SQL_DATOS_ALUMNO, (8,))]
    assert _sql(pool_b) == [(SQL_CENTRO_DEL_ALUMNO, (8,))]


def test_grupo_que_no_esta_en_ningun_fragmento_es_404_sin_inscribir():
    bd, pool_a, pool_b = _distribuida()
    with pytest.raises(NoEncontradoError, match="grupo"):
        ServicioAdministrador(bd).inscribir(ADMIN, InscripcionPorAdmin(grupo_id=5, alumno_id=8))
    assert all(sql != SQL_INSCRIBIR for sql, _ in _sql(pool_a) + _sql(pool_b))


def test_mismo_id_en_dos_centros_es_error_de_datos():
    bd, pool_a, pool_b = _distribuida()
    pool_a.conexion.cursor_falso.responder([{"centro_academico_id": 1}])
    pool_b.conexion.cursor_falso.responder([{"centro_academico_id": 2}])
    with pytest.raises(RuntimeError):
        ServicioAdministrador(bd).datos_alumno(ADMIN, 8)


# ------------------------------------------------------------ con una sola base

def test_una_sola_base_pregunta_ahi_mismo():
    bd, cur = bd_falsa([{"centro_academico_id": 2}], {"p_inscripcion": 91})
    r = ServicioAdministrador(bd).inscribir(ADMIN, InscripcionPorAdmin(grupo_id=4, alumno_id=8))
    assert r.inscripcion_id == 91
    assert cur.sql_de_negocio() == [(SQL_CENTRO_DEL_GRUPO, (4,)), (SQL_INSCRIBIR, (8, 4))]


def test_alumno_inexistente_es_404():
    bd, cur = bd_falsa([])
    with pytest.raises(NoEncontradoError, match="alumno no existe"):
        ServicioAdministrador(bd).datos_alumno(ADMIN, 8)
    assert cur.sql_de_negocio() == [(SQL_CENTRO_DEL_ALUMNO, (8,))]


def test_alumno_sin_datos_personales_es_404():
    bd, _ = bd_falsa([{"centro_academico_id": 2}], None)
    with pytest.raises(NoEncontradoError, match="datos personales"):
        ServicioAdministrador(bd).datos_alumno(ADMIN, 8)
