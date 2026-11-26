"""Pruebas de monitoreo/graficas.py (issue #26). Correr desde db/monitoreo: pytest"""

from datetime import datetime
from pathlib import Path

import pytest

import graficas as g

ENCABEZADO = "fecha,fragmento,nodo,rol,estado,lag_mb,conexiones,tamano_bytes\n"

# Dos fotos normales y una tercera donde pg-a1 se cayó y pg-a2 quedó de primario
FILAS = """\
2026-11-25 10:00:00,A,pg-a1,Leader,running,,4,10485760
2026-11-25 10:00:00,A,pg-a2,Sync Standby,streaming,0,3,10485760
2026-11-25 10:00:00,B,pg-b1,Leader,running,,3,20971520
2026-11-25 10:00:00,B,pg-b2,Sync Standby,streaming,0,3,20971520
2026-11-25 10:05:00,A,pg-a1,Leader,running,,6,15728640
2026-11-25 10:05:00,A,pg-a2,Sync Standby,streaming,1,3,15728640
2026-11-25 10:10:00,A,pg-a1,Replica,stopped,,,
2026-11-25 10:10:00,A,pg-a2,Leader,running,,2,15728640
"""


@pytest.fixture
def historial(tmp_path: Path) -> Path:
    ruta = tmp_path / "historial.csv"
    ruta.write_text(ENCABEZADO + FILAS + "fila,rota\n", encoding="utf-8")
    return ruta


def test_lee_y_omite_filas_rotas(historial):
    m = g.leer_historial(historial)
    assert len(m) == 8
    assert m[0].fecha == datetime(2026, 11, 25, 10, 0)
    caido = next(x for x in m if x.estado == "stopped")
    assert caido.conexiones is None and caido.tamano_bytes is None


@pytest.mark.parametrize(
    ("rol", "estado", "esperado"),
    [("Leader", "running", "Primario"), ("Sync Standby", "streaming", "Réplica"),
     ("Replica", "streaming", "Réplica"), ("Leader", "stopped", "Caído"),
     ("Replica", "start failed", "Caído")],
)
def test_rol_simple(rol, estado, esperado):
    m = g.Medicion(datetime.now(), "A", "pg-a1", rol, estado, None, None, None)
    assert m.rol_simple == esperado


def test_tamano_solo_cuenta_el_primario(historial):
    series = g.tamano_por_fragmento(g.leer_historial(historial))
    # A: 10 MB, 15 MB y, tras el failover, 15 MB medido en pg-a2
    assert [mb for _, mb in series["A"]] == [10.0, 15.0, 15.0]
    assert [mb for _, mb in series["B"]] == [20.0]


def test_serie_por_nodo_salta_huecos(historial):
    conexiones = g.serie_por_nodo(g.leer_historial(historial), "conexiones")
    assert [c for _, c in conexiones["pg-a1"]] == [4, 6]       # caído = sin dato
    lag = g.serie_por_nodo(g.leer_historial(historial), "lag_mb")
    assert set(lag) == {"pg-a2", "pg-b2"}                     # los primarios no tienen lag


def test_grafica_roles_marca_el_failover(historial):
    fig = g.grafica_roles(g.leer_historial(historial))
    ax = fig.axes[0]
    etiquetas = {t.get_text() for t in ax.get_legend().get_texts()}
    assert etiquetas == {"Primario", "Réplica", "Caído"}
    assert [t.get_text() for t in ax.get_yticklabels()] == ["pg-a1", "pg-a2", "pg-b1", "pg-b2"]


def test_titulos_y_ejes(historial):
    m = g.leer_historial(historial)
    ax = g.grafica_tamano(m).axes[0]
    assert ax.get_ylabel() == "Tamaño (MB)" and "Crecimiento" in ax.get_title()
    assert ax.get_xlabel() == "Fecha y hora"
    assert len(ax.get_lines()) == 2                             # A y B


def test_genera_los_4_png(historial, tmp_path):
    archivos = g.generar(historial, tmp_path / "salida")
    assert [a.name for a in archivos] == list(g.GRAFICAS)
    for a in archivos:
        assert a.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_historial_vacio_no_truena(tmp_path):
    vacio = tmp_path / "vacio.csv"
    vacio.write_text(ENCABEZADO, encoding="utf-8")
    assert len(g.generar(vacio, tmp_path / "s")) == 4


def test_main_sin_csv(tmp_path, capsys):
    assert g.main(["--csv", str(tmp_path / "no.csv"), "--salida", str(tmp_path)]) == 1
    assert "estado.sh" in capsys.readouterr().out


def test_tamano_empieza_en_cero(historial):
    ax = g.grafica_tamano(g.leer_historial(historial)).axes[0]
    assert ax.get_ylim()[0] == 0
    assert any("MB" in t.get_text() for t in ax.texts)          # etiqueta con el último valor
