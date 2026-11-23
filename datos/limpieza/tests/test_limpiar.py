"""Pruebas de la limpieza (sin base de datos)."""

from pathlib import Path

import pandas as pd
import pytest

from limpieza import ArchivoInvalidoError, CalificacionInvalidaError, leer_csv
from limpieza.limpiar import (
    COLUMNAS_ALUMNOS,
    COLUMNAS_CALIFICACIONES,
    convertir_calificacion,
    guardar_reporte,
    limpiar_alumnos,
    limpiar_calificaciones,
    nombre_propio,
    normalizar_matricula,
)

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplos"


# --- funciones pequeñas -------------------------------------------------------

@pytest.mark.parametrize("entrada, esperado", [
    (" a-000102 ", "A000102"), ("a 000 102", "A000102"), ("479329", "479329"), ("A.000101", "A000101"),
])
def test_normalizar_matricula(entrada, esperado):
    assert normalizar_matricula(entrada) == esperado


@pytest.mark.parametrize("entrada, esperado", [
    ("  maría josé ", "María José"),
    ("GARCÍA  de la cruz", "García de la Cruz"),
    ("de la Torre", "De la Torre"),
])
def test_nombre_propio(entrada, esperado):
    assert nombre_propio(entrada) == esperado


@pytest.mark.parametrize("entrada, valor, escala_100", [
    ("8,5", 8.5, False), ("9", 9.0, False), ("95", 9.5, True), ("100", 10.0, True), (" 0 ", 0.0, False),
])
def test_convertir_calificacion_valida(entrada, valor, escala_100):
    assert convertir_calificacion(entrada) == (valor, escala_100)


@pytest.mark.parametrize("entrada", ["NP", "", "-1", "101", "nan", "11.5", "11.5e3"])
def test_convertir_calificacion_invalida(entrada):
    with pytest.raises(CalificacionInvalidaError):
        convertir_calificacion(entrada)


# --- lectura ------------------------------------------------------------------

def test_leer_csv_no_existe(tmp_path):
    with pytest.raises(ArchivoInvalidoError, match="no existe"):
        leer_csv(tmp_path / "nada.csv", COLUMNAS_ALUMNOS)


def test_leer_csv_vacio(tmp_path):
    ruta = tmp_path / "vacio.csv"
    ruta.write_text("", encoding="utf-8")
    with pytest.raises(ArchivoInvalidoError, match="vacío"):
        leer_csv(ruta, COLUMNAS_ALUMNOS)


def test_leer_csv_faltan_columnas(tmp_path):
    ruta = tmp_path / "mal.csv"
    ruta.write_text("matricula,nombre\nA000001,Ana\n", encoding="utf-8")
    with pytest.raises(ArchivoInvalidoError, match="faltan columnas"):
        leer_csv(ruta, COLUMNAS_ALUMNOS)


def test_leer_csv_normaliza_encabezados(tmp_path):
    ruta = tmp_path / "ok.csv"
    ruta.write_text("Matrícula,NOMBRE,Apellidos,Carrera,Semestre\nA000001,Ana,Gil,ISC,3\n", encoding="utf-8")
    df = leer_csv(ruta, COLUMNAS_ALUMNOS)
    assert list(df.columns) == COLUMNAS_ALUMNOS
    assert df.index[0] == 2          # fila 2, como en Excel


# --- limpieza de alumnos ------------------------------------------------------

def test_limpiar_alumnos_ejemplo():
    df, rep = limpiar_alumnos(leer_csv(EJEMPLOS / "alumnos_sucio.csv", COLUMNAS_ALUMNOS))
    assert rep.filas_leidas == 9
    assert sorted(df["matricula"]) == ["A000101", "A000102", "A000105", "A000107"]
    maria = df[df["matricula"] == "A000101"].iloc[0]
    assert maria["semestre"] == 8              # duplicada: se conserva la última
    assert maria["apellidos"] == "García de la Cruz"
    assert df[df["matricula"] == "A000105"].iloc[0]["carrera"] == "LAE"
    motivos = [d["motivo"] for d in rep.descartes]
    assert "semestre fuera de 1 a 12" in motivos           # 15 y "siete"
    assert "falta nombre o apellidos" in motivos
    assert "matrícula con formato inválido" in motivos
    assert "matrícula duplicada (se conserva la última)" in motivos
    assert rep.filas_validas == 4


def test_reporte_sin_datos_personales():
    _, rep = limpiar_alumnos(leer_csv(EJEMPLOS / "alumnos_sucio.csv", COLUMNAS_ALUMNOS))
    texto = str(rep.a_dict())
    for dato in ("García", "Hernández", "A000101"):
        assert dato not in texto


# --- limpieza de calificaciones -----------------------------------------------

def test_limpiar_calificaciones_ejemplo():
    df, rep = limpiar_calificaciones(leer_csv(EJEMPLOS / "calificaciones_sucio.csv", COLUMNAS_CALIFICACIONES))
    a101 = df[df["matricula"] == "A000101"].set_index("tipo")["valor"].to_dict()
    assert a101 == {"parcial1": 8.5, "parcial2": 9.5}       # 11.5 se descarta
    a102 = df[df["matricula"] == "A000102"].set_index("tipo")["valor"].to_dict()
    assert a102 == {"parcial1": 6.5, "final": 7.0}          # duplicado: la última
    assert set(df["materia"]) == {"ISC-701"} and set(df["periodo"]) == {"2026-AGO-DIC"}
    assert rep.correcciones["calificación en escala 0-100 convertida a 0-10"] == 1
    assert rep.correcciones["calificación con coma decimal"] == 1
    motivos = [d["motivo"] for d in rep.descartes]
    assert motivos.count("calificación no numérica o fuera de rango") == 2   # NP y 11.5
    assert "tipo de calificación desconocido" in motivos                     # extra


def test_limpiar_no_modifica_el_original():
    original = pd.DataFrame([{"matricula": " a1 ", "materia": "x", "periodo": "y", "tipo": "p1", "valor": "9"}])
    copia = original.copy()
    limpiar_calificaciones(original)
    pd.testing.assert_frame_equal(original, copia)


def test_guardar_reporte(tmp_path):
    _, rep = limpiar_alumnos(leer_csv(EJEMPLOS / "alumnos_sucio.csv", COLUMNAS_ALUMNOS))
    ruta = tmp_path / "rep.json"
    guardar_reporte([rep], ruta)
    assert '"filas_validas": 4' in ruta.read_text(encoding="utf-8")
