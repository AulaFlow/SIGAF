"""ETL real desde PostgreSQL con la cuenta del ETL. Se salta si no hay base:

    export SIGAF_DSN_ETL_PRUEBAS="postgresql://sigaf_etl_svc@localhost:5432/postgres"
    export PGPASSWORD=<contraseña de sigaf_etl_svc>
(base con db/01, 02, 03, 05, 06 y datos del generador o de pruebas.sql)
"""

import os

import mongomock
import pytest

from analitica import ProcesoETL
from analitica.fuentes import FuentePostgres
from analitica.graficas import generar_todas
from tests.test_analitica import RepositorioEnMemoria

DSN = os.environ.get("SIGAF_DSN_ETL_PRUEBAS")
pytestmark = pytest.mark.skipif(not DSN, reason="sin base de pruebas (SIGAF_DSN_ETL_PRUEBAS)")


def test_etl_real_y_graficas(tmp_path):
    repo = RepositorioEnMemoria(mongomock.MongoClient()["sigaf"])
    with FuentePostgres("unico", DSN) as fuente:
        resultado = ProcesoETL(repo).ejecutar([fuente])
    assert resultado.por_coleccion["historico_calificaciones"] > 0
    assert repo.contar("resumen_grupo") > 0
    # Ningún documento trae datos personales
    doc = repo.agregar("actividad_alumno", [{"$limit": 1}])[0]
    assert not {"nombre", "apellidos", "matricula", "correo"} & set(doc)
    assert len(generar_todas(repo, tmp_path)) == 3


def test_fuente_fuera_de_with():
    fuente = FuentePostgres("x", DSN)
    with pytest.raises(RuntimeError, match="with"):
        next(fuente.calificaciones())
