"""Estadísticas contra el MongoDB real (sigaf-mongo, cargado por el ETL).

Se omiten si no hay SIGAF_PASS_API o si MongoDB no responde. Solo leen.
"""

from collections.abc import Iterator

import pytest
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.config import Configuracion
from app.datos.mongo import RepositorioEstadisticas, crear_cliente_mongo
from app.dominio.personas import Administrador, Alumno, Profesor
from app.servicios.estadisticas import ServicioEstadisticas
from tests.conftest import solo_con_base

pytestmark = solo_con_base
PERIODO = "2026-AGO-DIC"     # el periodo actual del generador
ADMIN = Administrador(1, "admin@sigaf.test")


@pytest.fixture(scope="module")
def mongo_db() -> Iterator[Database]:
    config = Configuracion.desde_entorno()
    cliente = crear_cliente_mongo(config)
    try:
        cliente.admin.command("ping")
    except PyMongoError:
        cliente.close()
        pytest.skip("MongoDB (sigaf-mongo) no responde")
    try:
        yield cliente[config.mongo_db]
    finally:
        cliente.close()


@pytest.fixture(scope="module")
def srv(mongo_db, bd_real) -> ServicioEstadisticas:
    return ServicioEstadisticas(RepositorioEstadisticas(mongo_db), bd_real)


def test_el_etl_ya_cargo_datos(mongo_db):
    for coleccion in ("resumen_grupo", "actividad_alumno", "historico_calificaciones"):
        assert mongo_db[coleccion].estimated_document_count() > 0, coleccion


def test_agregados_del_periodo(srv):
    distribucion = srv.distribucion(ADMIN, PERIODO)
    if distribucion.total == 0:
        pytest.skip(f"no hay calificaciones de {PERIODO} en MongoDB")
    assert sum(r.total for r in distribucion.rangos) == distribucion.total
    materias = srv.promedio_por_materia(ADMIN, PERIODO, cuantas=5)
    assert 1 <= len(materias) <= 5
    assert [m.promedio for m in materias] == sorted(m.promedio for m in materias)
    assert {c.centro for c in srv.entregas_por_centro(ADMIN, PERIODO)}


def test_actividad_de_un_alumno_real(srv, mongo_db):
    doc = mongo_db["actividad_alumno"].find_one({}, {"alumno_id": 1})
    actividad = srv.mi_actividad(Alumno(1, "a@sigaf.test", doc["alumno_id"]))
    assert actividad and all(a.actualizado_en is not None for a in actividad)


def test_resumen_de_un_grupo_del_profesor(srv, mongo_db, bd_real):
    doc = mongo_db["resumen_grupo"].find_one({}, {"grupo_id": 1})
    with bd_real.transaccion() as cur:
        cur.execute("SELECT g.profesor_id, p.usuario_id FROM grupo g "
                    "JOIN profesor p USING (profesor_id) WHERE g.grupo_id = %s", (doc["grupo_id"],))
        fila = cur.fetchone()
    profesor = Profesor(fila["usuario_id"], "p@sigaf.test", fila["profesor_id"])
    assert srv.resumen_de_grupo(profesor, doc["grupo_id"])
