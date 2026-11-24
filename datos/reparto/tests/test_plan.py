"""Pruebas del plan de reparto: que no se olvide ninguna tabla y que el orden respete las llaves foráneas."""

import re
from pathlib import Path

import pytest

from reparto import plan
from reparto.repartidor import Conteo, lista_centros

RAIZ = Path(__file__).resolve().parents[3]
TABLAS_SQL = RAIZ / "db" / "01_tablas.sql"


def tablas_del_esquema() -> dict[str, set[str]]:
    """{tabla: tablas a las que apunta con REFERENCES}, leído de db/01_tablas.sql."""
    texto = TABLAS_SQL.read_text(encoding="utf-8")
    tablas: dict[str, set[str]] = {}
    for nombre, cuerpo in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", texto, re.DOTALL):
        tablas[nombre] = set(re.findall(r"REFERENCES (\w+)", cuerpo)) - {nombre}
    return tablas


def test_el_reparto_es_el_del_equipo():
    assert plan.CENTROS_A == (1, 3, 5)      # CCB, CCA, CCSH
    assert plan.CENTROS_B == (2, 4, 6)      # CCEA, CCS, CCDC
    assert not set(plan.CENTROS_A) & set(plan.CENTROS_B)


def test_todas_las_tablas_del_esquema_tienen_regla():
    assert set(tablas_del_esquema()) == plan.tablas_cubiertas()


def test_copia_primero_los_padres():
    esquema = tablas_del_esquema()
    vistas: set[str] = set()
    for regla in plan.ORDEN_COPIA:
        if regla.filtro == "grupo_id IS NULL":   # avisos generales: no apuntan a ningún grupo
            continue
        faltan = esquema[regla.tabla] - vistas - {"directorio_fragmento", *plan.SOLO_EN_A}
        assert not faltan, f"{regla.tabla} se copia antes que {faltan}"
        vistas.add(regla.tabla)


def test_borra_primero_los_hijos():
    esquema = tablas_del_esquema()
    borradas: set[str] = set()
    for regla in plan.ORDEN_BORRADO:
        hijos = {t for t in (r.tabla for r in plan.FRAGMENTADAS) if regla.tabla in esquema[t]}
        assert hijos <= borradas, f"{regla.tabla} se borra antes que sus hijos {hijos - borradas}"
        borradas.add(regla.tabla)


def test_bitacora_se_borra_despues_de_las_calificaciones():
    orden = [r.tabla for r in plan.ORDEN_BORRADO]
    assert orden.index("calificacion") < orden.index("bitacora_calificacion") < orden.index("inscripcion")
    assert sorted(orden) == sorted(r.tabla for r in plan.FRAGMENTADAS)


def test_tarea_se_copia_antes_que_inscripcion():
    # Si no, el trigger trg_tarea_notificar crearía notificaciones repetidas en B.
    orden = [r.tabla for r in plan.ORDEN_COPIA]
    assert orden.index("tarea") < orden.index("inscripcion") < orden.index("notificacion")


def test_where_pone_los_centros():
    regla = plan.Regla("grupo", "centro_academico_id = ANY({c})")
    assert regla.where("ARRAY[2]") == " WHERE centro_academico_id = ANY(ARRAY[2])"
    assert plan.Regla("rol", replicada=True).where("ARRAY[2]") == ""


def test_nombre_distingue_avisos_generales():
    generales, de_grupo = [r for r in plan.ORDEN_COPIA if r.tabla == "aviso"]
    assert (generales.nombre, de_grupo.nombre) == ("aviso (generales)", "aviso")


def test_lista_centros_solo_acepta_numeros():
    assert lista_centros((2, 4, 6)) == "ARRAY[2,4,6]::smallint[]"
    with pytest.raises(ValueError):
        lista_centros(["2); DROP TABLE alumno; --"])


@pytest.mark.parametrize(("conteo", "esperado"), [
    (Conteo("grupo", False, 10, 0, 10), True),
    (Conteo("grupo", False, 10, 1, 9), False),     # se quedó una fila en A
    (Conteo("grupo", False, 10, 0, 11), False),    # se duplicó en B
    (Conteo("rol", True, 3, 3, 3), True),
    (Conteo("rol", True, 3, 3, 2), False),
])
def test_conteo_cuadra(conteo, esperado):
    assert conteo.cuadra is esperado
