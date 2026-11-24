"""Pruebas del Repartidor con conexiones falsas (sin PostgreSQL)."""

import pytest

from reparto import plan, repartidor
from reparto.repartidor import Nodos, Repartidor, RepartoError, por_centro, vaciar
from tests.falsos import ConexionFalsa

NODOS = {"A": Nodos("haproxy:5432", "haproxy:5433"), "B": Nodos("haproxy:5434", "haproxy:5435")}


def nuevo(falla_en=None):
    a, b = ConexionFalsa("A", falla_en), ConexionFalsa("B")
    return a, b, Repartidor(a, b, NODOS, avisar=lambda _m: None)


def conteos_simulados(monkeypatch, antes: int = 5, sin_mover: int = 0):
    """Imita los count(*): en A antes hay `antes` filas; después A queda en `sin_mover` y B en `antes`."""
    llamadas = {"n": 0}
    total = len(plan.ORDEN_COPIA)

    def contar(conn, regla, _c):
        llamadas["n"] += 1
        if llamadas["n"] <= total or regla.replicada:
            return antes
        return sin_mover if conn.nombre == "A" else antes

    monkeypatch.setattr(repartidor, "_contar", contar)


def test_copia_cada_regla_por_bloques():
    a, b, r = nuevo()
    r.copiar_a_b()
    assert len(b.escrito) == 2 * len(plan.ORDEN_COPIA)
    assert any("COPY (SELECT * FROM sigaf.grupo WHERE centro_academico_id = ANY(ARRAY[2,4,6]" in s for s in a.sql)
    # La bitácora que crea el trigger en B se quita antes de copiar la original
    i = b.sql.index("DELETE FROM sigaf.bitacora_calificacion")
    assert "bitacora_calificacion FROM STDIN" in b.sql[i + 1]


def test_borra_de_a_en_orden():
    a, _b, r = nuevo()
    r.borrar_de_a()
    borrados = [s.split()[2] for s in a.sql]
    assert borrados == [f"sigaf.{x.tabla}" for x in plan.ORDEN_BORRADO]


def test_directorio_tiene_los_seis_centros():
    a, _b, r = nuevo()
    r.llenar_directorio(a)
    assert sorted(f[:2] for f in a.filas_directorio) == [(1, "A"), (2, "B"), (3, "A"), (4, "B"), (5, "A"), (6, "B")]
    assert (2, "B", "haproxy:5434", "haproxy:5435") in a.filas_directorio


def test_ids_de_b_empiezan_en_mil_millones():
    a, b, r = nuevo()
    r.ajustar_ids({"calificacion": 30000, "rol": 3})
    setval_b = [s for s in b.sql if "setval" in s]
    assert len(setval_b) == 2
    assert "setval(%s, %s)" in setval_b[0]      # calificacion (BIGINT): desde INICIO_IDS_B
    assert any("setval" in s for s in a.sql)


def test_repartir_completo(monkeypatch):
    conteos_simulados(monkeypatch)
    a, b, r = nuevo()
    reporte = r.repartir()
    assert all(c.cuadra for c in reporte)
    assert any(s.startswith("TRUNCATE") for s in b.sql)
    assert a.commits >= 2 and b.commits >= 2


def test_no_reparte_si_a_esta_vacio(monkeypatch):
    conteos_simulados(monkeypatch, antes=0)
    _a, _b, r = nuevo()
    with pytest.raises(RepartoError, match="generador"):
        r.repartir()


def test_avisa_si_no_cuadra(monkeypatch):
    conteos_simulados(monkeypatch, sin_mover=1)        # quedó una fila en A
    _a, _b, r = nuevo()
    with pytest.raises(RepartoError, match="No cuadran"):
        r.repartir()


def test_si_falla_el_borrado_hace_rollback(monkeypatch):
    conteos_simulados(monkeypatch)
    a, _b, r = nuevo(falla_en="DELETE FROM sigaf.profesor")
    with pytest.raises(RepartoError, match="no se pudo borrar"):
        r.repartir()
    assert a.rollbacks == 1


def test_vaciar_reinicia_ids():
    conn = ConexionFalsa("A")
    vaciar(conn)
    assert conn.sql[0].startswith("TRUNCATE")
    assert sum("setval" in s for s in conn.sql) == 2
    assert conn.commits == 1


def test_por_centro():
    assert por_centro(ConexionFalsa("A")) == [("CCB", 1, 260, 2600, 7800)]
