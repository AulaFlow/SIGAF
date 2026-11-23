"""Prueba de integración de la carga. Necesita una base con el esquema de
SIGAF (db/01, 02, 03 y 05) y los datos de db/pruebas.sql. Se salta si no
hay base configurada:

    export SIGAF_DSN_PRUEBAS="postgresql://postgres@localhost:5432/postgres"
    export PGPASSWORD=dev
"""

import os
from pathlib import Path

import pytest

from limpieza import CargaError
from limpieza.cargar import cargar, llaves_de_entorno
from limpieza.limpiar import (
    COLUMNAS_ALUMNOS,
    COLUMNAS_CALIFICACIONES,
    leer_csv,
    limpiar_alumnos,
    limpiar_calificaciones,
)

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplos"
DSN = os.environ.get("SIGAF_DSN_PRUEBAS")
LLAVES = {
    "SIGAF_LLAVE_DATOS": "llave-de-prueba-datos-0123456789abcdef",
    "SIGAF_LLAVE_SEUDONIMO": "llave-de-prueba-seudonimo-0123456789ab",
}


def test_sin_llaves_no_carga(monkeypatch):
    monkeypatch.delenv("SIGAF_LLAVE_DATOS", raising=False)
    with pytest.raises(CargaError, match="Faltan"):
        llaves_de_entorno()


@pytest.mark.skipif(not DSN, reason="sin base de pruebas (SIGAF_DSN_PRUEBAS)")
def test_carga_completa(monkeypatch):
    import psycopg

    for k, v in LLAVES.items():
        monkeypatch.setenv(k, v)
    alumnos = limpiar_alumnos(leer_csv(EJEMPLOS / "alumnos_sucio.csv", COLUMNAS_ALUMNOS))
    califs = limpiar_calificaciones(leer_csv(EJEMPLOS / "calificaciones_sucio.csv", COLUMNAS_CALIFICACIONES))
    resultado = cargar(DSN, alumnos, None)
    assert resultado["alumnos"] == 3                       # la carrera IND no existe en la base
    assert "la carrera no existe en la base" in [d["motivo"] for d in alumnos[1].descartes]

    # Inscribe a los nuevos alumnos para poder calificarlos
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SET search_path TO sigaf, public")
        cur.execute("SELECT set_config('sigaf.llave_seudonimo', %s, false)", (LLAVES["SIGAF_LLAVE_SEUDONIMO"],))
        for m in ("A000101", "A000102"):
            cur.execute("SELECT alumno_id FROM alumno WHERE matricula = fn_seudonimizar(%s)", (m,))
            cur.execute("CALL sp_inscribir_alumno(%s, 2, NULL)", (cur.fetchone()[0],))

    resultado = cargar(DSN, None, califs)
    assert resultado["calificaciones"] == 4
    assert "el alumno no está inscrito en esa materia y periodo" in [d["motivo"] for d in califs[1].descartes]

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SET search_path TO sigaf, public")
        cur.execute("SELECT set_config('sigaf.llave_seudonimo', %s, false)", (LLAVES["SIGAF_LLAVE_SEUDONIMO"],))
        cur.execute("""SELECT i.promedio_parciales FROM inscripcion i JOIN alumno a USING (alumno_id)
                       WHERE a.matricula = fn_seudonimizar('A000101')""")
        assert float(cur.fetchone()[0]) == 9.0             # (8.5 + 9.5) / 2, lo calculó el trigger


@pytest.mark.skipif(not DSN, reason="sin base de pruebas (SIGAF_DSN_PRUEBAS)")
def test_error_hace_rollback(monkeypatch):
    import pandas as pd
    import psycopg

    from limpieza.limpiar import Reporte

    for k, v in LLAVES.items():
        monkeypatch.setenv(k, v)
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM sigaf.alumno")
        antes = cur.fetchone()[0]
    # Segunda fila con semestre 99: la base la rechaza (CHECK) y debe revertirse TODO
    df = pd.DataFrame([
        {"matricula": "A000201", "nombre": "Uno", "apellidos": "Prueba", "carrera": "ISC", "semestre": 3},
        {"matricula": "A000202", "nombre": "Dos", "apellidos": "Prueba", "carrera": "ISC", "semestre": 99},
    ])
    with pytest.raises(CargaError, match="rollback"):
        cargar(DSN, (df, Reporte("prueba")), None)
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM sigaf.alumno")
        assert cur.fetchone()[0] == antes                  # no quedó ni el primero
