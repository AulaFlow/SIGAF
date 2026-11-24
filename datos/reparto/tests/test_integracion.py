"""Reparto real contra los dos fragmentos. Se salta si no hay bases:

    export SIGAF_DSN_A="host=haproxy port=5432 dbname=postgres user=sigaf_dba sslmode=verify-ca sslrootcert=/certs/ca.crt"
    export SIGAF_DSN_B="host=haproxy port=5434 ..."
    export SIGAF_REPARTO_PRUEBAS=1          # OJO: vacía los dos fragmentos
"""

import os

import pytest

from reparto import __main__ as cli
from reparto.repartidor import por_centro

pytestmark = pytest.mark.skipif(os.environ.get("SIGAF_REPARTO_PRUEBAS") != "1",
                                reason="sin fragmentos de prueba (SIGAF_REPARTO_PRUEBAS=1)")


def test_reparto_real(monkeypatch):
    monkeypatch.setenv("SIGAF_ALUMNOS", "60")
    assert cli.main(["todo"]) == 0
    for fragmento, propios in (("A", {1, 3, 5}), ("B", {2, 4, 6})):
        with cli.conectar(fragmento) as conn:
            filas = por_centro(conn)
            con_datos = {centro for _, centro, alumnos, _, _ in filas if alumnos}
            assert con_datos == propios, f"el fragmento {fragmento} tiene centros ajenos"
            directorio = conn.execute("SELECT count(*) FROM sigaf.directorio_fragmento").fetchone()[0]
            assert directorio == 6
    # Volver a repartir sin generar falla: A ya no tiene datos de B
    assert cli.main(["repartir"]) == 1
