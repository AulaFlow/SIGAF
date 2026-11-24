"""Pruebas del enrutador por centro (issue #6). Corren sin base de datos."""

import pytest
from fastapi.testclient import TestClient

from app.datos.enrutador import (
    SQL_DIRECTORIO,
    BaseDistribuida,
    CentroDesconocidoError,
    DirectorioInvalidoError,
    Enrutador,
    Nodo,
    armar_fragmentos,
    crear_base_distribuida,
)
from app.datos.postgres import BaseDeDatos
from app.dependencias import BD
from app.main import crear_app
from tests.fakes import ConexionFalsa, PoolFalso, configuracion

# Igual que db/pruebas.sql: A = CCB(1), CCA(3), CCSH(5) · B = CCEA(2), CCS(4), CCDC(6)
DIRECTORIO = [
    (1, "A", "pg-a:5432", "pg-a-rep:5433"),
    (2, "B", "pg-b:5434", "pg-b-rep:5435"),
    (3, "A", "pg-a:5432", "pg-a-rep:5433"),
    (4, "B", "pg-b:5434", "pg-b-rep:5435"),
    (5, "A", "pg-a:5432", "pg-a-rep:5433"),
    (6, "B", "pg-b:5434", "pg-b-rep:5435"),
]


def _enrutador() -> tuple[Enrutador, PoolFalso, PoolFalso]:
    pool_a, pool_b = PoolFalso(), PoolFalso()
    return Enrutador(armar_fragmentos(DIRECTORIO), {"A": pool_a, "B": pool_b}), pool_a, pool_b


# --- Directorio -------------------------------------------------------------

def test_agrupa_centros_por_fragmento():
    fragmentos = armar_fragmentos(DIRECTORIO)
    assert sorted(fragmentos) == ["A", "B"]
    assert fragmentos["A"].centros == (1, 3, 5)
    assert fragmentos["B"].centros == (2, 4, 6)
    assert fragmentos["B"].primario == Nodo("pg-b", 5434)
    assert fragmentos["B"].replica == Nodo("pg-b-rep", 5435)


def test_nodo_sin_puerto_usa_5432():
    assert Nodo.desde_texto("laptop1") == Nodo("laptop1", 5432)


@pytest.mark.parametrize("texto", ["laptop1:abc", "laptop1:0", "laptop1:70000"])
def test_nodo_con_puerto_invalido(texto):
    with pytest.raises(DirectorioInvalidoError):
        Nodo.desde_texto(texto)


def test_fragmento_con_dos_primarios_es_invalido():
    filas = [(1, "A", "laptop1:5432", "laptop3:5432"), (3, "A", "otra:5432", "laptop3:5432")]
    with pytest.raises(DirectorioInvalidoError):
        armar_fragmentos(filas)


def test_directorio_vacio_es_invalido():
    with pytest.raises(DirectorioInvalidoError):
        Enrutador({}, {})


def test_falta_pool_de_un_fragmento():
    with pytest.raises(DirectorioInvalidoError):
        Enrutador(armar_fragmentos(DIRECTORIO), {"A": PoolFalso()})


# --- Enrutamiento ------------------------------------------------------------

@pytest.mark.parametrize("centro, fragmento", [(1, "A"), (3, "A"), (5, "A"),
                                               (2, "B"), (4, "B"), (6, "B")])
def test_cada_centro_va_a_su_fragmento(centro, fragmento):
    enrutador, pool_a, pool_b = _enrutador()
    assert enrutador.fragmento_de(centro) == fragmento
    assert enrutador.pool_para(centro) is (pool_a if fragmento == "A" else pool_b)


def test_centro_desconocido():
    enrutador, _, _ = _enrutador()
    with pytest.raises(CentroDesconocidoError) as error:
        enrutador.pool_para(99)
    assert error.value.centro_academico_id == 99


def test_sin_centro_usa_el_primer_fragmento():
    enrutador, pool_a, _ = _enrutador()
    assert enrutador.pool_para(None) is pool_a


def test_transaccion_va_al_fragmento_del_centro():
    enrutador, pool_a, pool_b = _enrutador()
    bd = BaseDistribuida(configuracion(), enrutador)
    with bd.transaccion(centro_academico_id=4) as cur:    # CCS -> B
        cur.execute("SELECT 1")
    assert (pool_a.prestadas, pool_b.prestadas) == (0, 1)
    assert pool_b.conexion.commits == 1 and pool_b.devueltas == 1


def test_en_todos_junta_resultados_de_a_y_b():
    pool_a = PoolFalso(ConexionFalsa(filas=[("alumno A",)]))
    pool_b = PoolFalso(ConexionFalsa(filas=[("alumno B",)]))
    bd = BaseDistribuida(configuracion(),
                         Enrutador(armar_fragmentos(DIRECTORIO), {"A": pool_a, "B": pool_b}))

    def consulta(cur):
        cur.execute("SELECT nombre FROM alumno")
        return cur.fetchall()

    assert bd.en_todos(consulta) == [("alumno A",), ("alumno B",)]
    assert pool_a.conexion.commits == 1 and pool_b.conexion.commits == 1


def test_en_todos_no_regresa_resultados_a_medias():
    pool_a, pool_b = PoolFalso(), PoolFalso()
    bd = BaseDistribuida(configuracion(),
                         Enrutador(armar_fragmentos(DIRECTORIO), {"A": pool_a, "B": pool_b}))
    llamadas = []

    def consulta(cur):
        llamadas.append(cur)
        if len(llamadas) == 2:
            raise RuntimeError("se cayó el fragmento B")
        return [1]

    with pytest.raises(RuntimeError):
        bd.en_todos(consulta)
    assert pool_b.conexion.rollbacks == 1


# --- Arranque de la API ------------------------------------------------------

def test_arranque_con_directorio_vacio_usa_un_solo_pool():
    inicial = PoolFalso()
    bd, nuevos = crear_base_distribuida(configuracion(), inicial, lambda c: PoolFalso(),
                                        lambda p: p.open())
    assert type(bd) is BaseDeDatos and nuevos == []
    assert inicial.devueltas == 1
    assert inicial.conexion.cursor_falso.ejecutadas[0][0] == SQL_DIRECTORIO


def test_arranque_abre_un_pool_por_fragmento_y_reusa_el_inicial():
    inicial = PoolFalso(ConexionFalsa(filas=DIRECTORIO))
    creados = {}

    def fabrica(config):
        creados[(config.db_host, config.db_puerto)] = PoolFalso()
        return creados[(config.db_host, config.db_puerto)]

    config = configuracion(db_host="pg-a", db_puerto=5432)
    bd, nuevos = crear_base_distribuida(config, inicial, fabrica, lambda p: p.open())
    assert isinstance(bd, BaseDistribuida)
    assert list(creados) == [("pg-b", 5434)]          # A ya era el pool inicial
    assert bd.pool_para(1) is inicial
    assert bd.pool_para(2) is creados[("pg-b", 5434)]
    assert nuevos == [creados[("pg-b", 5434)]] and nuevos[0].abierto


def test_lifespan_cierra_todos_los_pools():
    inicial = PoolFalso(ConexionFalsa(filas=DIRECTORIO))
    otros = []

    def fabrica(config):
        if config.db_host == "localhost":
            return inicial
        otros.append(PoolFalso())
        return otros[-1]

    app = crear_app(configuracion(), fabrica_pool=fabrica)

    @app.get("/_centro/{centro}")
    def ruta(centro: int, bd: BD) -> dict:
        return {"fragmento": bd.enrutador.fragmento_de(centro)}

    with TestClient(app) as client:
        assert client.get("/_centro/4").json() == {"fragmento": "B"}
    assert inicial.cerrado and len(otros) == 2 and all(p.cerrado for p in otros)
