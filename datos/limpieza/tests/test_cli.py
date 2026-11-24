"""Pruebas de la línea de comandos (solo limpieza, sin base)."""

import json
from pathlib import Path

import pytest

from limpieza.__main__ import main

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplos"


def test_cli_limpia_y_guarda_reporte(tmp_path, capsys):
    reporte = tmp_path / "rep.json"
    codigo = main(["--alumnos", str(EJEMPLOS / "alumnos_sucio.csv"),
                   "--calificaciones", str(EJEMPLOS / "calificaciones_sucio.csv"),
                   "--reporte", str(reporte)])
    assert codigo == 0
    datos = json.loads(reporte.read_text(encoding="utf-8"))
    assert [r["filas_validas"] for r in datos] == [4, 5]
    assert "descartado" in capsys.readouterr().out


def test_cli_archivo_inexistente(tmp_path, capsys):
    assert main(["--alumnos", str(tmp_path / "no.csv")]) == 1
    assert "no existe" in capsys.readouterr().err


def test_cli_sin_archivos():
    with pytest.raises(SystemExit):
        main([])
