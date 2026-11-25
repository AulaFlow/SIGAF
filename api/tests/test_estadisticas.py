"""Estadísticas con MongoDB en memoria (mongomock). Sin red ni base real."""

from datetime import UTC, datetime

import mongomock
import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError
from pymongo.errors import ServerSelectionTimeoutError

from app.datos.mongo import RepositorioEstadisticas
from app.dependencias import Estadisticas
from app.dominio.excepciones import (
    NoEncontradoError,
    PermisoDenegadoError,
    ServicioNoDisponibleError,
)
from app.dominio.personas import Administrador, Alumno, Profesor
from app.esquemas.estadisticas import Distribucion, Periodo
from app.main import crear_app
from app.servicios.estadisticas import ServicioEstadisticas
from tests.fakes import PoolFalso, bd_falsa, configuracion

P = "2026-AGO-DIC"
AHORA = datetime.now(UTC)
ALUMNO = Alumno(1, "a@sigaf.test", alumno_id=7)
PROFE = Profesor(2, "p@sigaf.test", profesor_id=5)
ADMIN = Administrador(3, "x@sigaf.test")


@pytest.fixture
def db():
    db = mongomock.MongoClient()["sigaf_analitica"]
    db.actividad_alumno.insert_many([
        {"_id": f"{P}:7", "alumno_id": 7, "periodo": P, "centro_academico_id": 1, "centro": "CCB",
         "entregas_a_tiempo": 8, "entregas_tardias": 2, "no_entregadas": 1, "faltas": 3,
         "actualizado_en": AHORA},
        {"_id": f"{P}:8", "alumno_id": 8, "periodo": P, "centro_academico_id": 2, "centro": "CCEA",
         "entregas_a_tiempo": 5, "entregas_tardias": 0, "no_entregadas": 4, "faltas": 0,
         "actualizado_en": AHORA},
    ])
    db.resumen_grupo.insert_many([
        {"_id": f"{P}:4", "grupo_id": 4, "periodo": P, "centro_academico_id": 1,
         "materia_clave": "ISC701", "materia": "Datos", "alumnos": 30, "promedio": 7.5,
         "pct_aprobados": 80.0, "pct_asistencia": 90.0, "actualizado_en": AHORA},
        {"_id": f"{P}:9", "grupo_id": 9, "periodo": P, "centro_academico_id": 1,
         "materia_clave": "ISC702", "materia": "Redes", "alumnos": 20, "promedio": 6.1,
         "pct_aprobados": 55.0, "pct_asistencia": 85.0, "actualizado_en": AHORA},
        {"_id": f"{P}:10", "grupo_id": 10, "periodo": P, "centro_academico_id": 1,
         "materia_clave": "ISC703", "materia": "Sin datos", "alumnos": 0, "promedio": None,
         "pct_aprobados": None, "pct_asistencia": None, "actualizado_en": AHORA},
    ])
    db.historico_calificaciones.insert_many([
        {"_id": str(i), "calificacion_id": i, "alumno_id": 7, "periodo": P,
         "centro_academico_id": 1, "materia_clave": "ISC701",
         "tipo": "final" if i % 2 else "parcial1", "valor": v}
        for i, v in enumerate([0, 5.5, 6, 6.9, 10, 9.99, 7])
    ])
    return db


def servicio(db, *respuestas_pg):
    bd, cur = bd_falsa(*respuestas_pg)
    return ServicioEstadisticas(RepositorioEstadisticas(db), bd), cur


def test_alumno_ve_solo_su_actividad(db):
    srv, _ = servicio(db)
    actividad = srv.mi_actividad(ALUMNO)
    assert len(actividad) == 1 and actividad[0].entregas_tardias == 2
    assert actividad[0].actualizado_en is not None      # consistencia eventual visible


def test_resumen_de_grupo_propio(db):
    srv, cur = servicio(db, {"?column?": 1})            # PostgreSQL: el grupo sí es suyo
    resumen = srv.resumen_de_grupo(PROFE, 4)
    assert resumen[0].materia == "Datos"
    assert cur.sql_de_negocio()[0][1] == (4, 5)         # grupo, profesor del token


def test_resumen_de_grupo_ajeno_no_consulta_mongo(db):
    srv, _ = servicio(db, None)
    with pytest.raises(NoEncontradoError):
        srv.resumen_de_grupo(PROFE, 4)


def test_distribucion_en_rangos(db):
    srv, _ = servicio(db)
    d = srv.distribucion(PROFE, P)
    assert isinstance(d, Distribucion) and d.total == 7
    totales = {r.desde: r.total for r in d.rangos}
    assert totales[0] == 1 and totales[5] == 1 and totales[6] == 2 and totales[10] == 1
    assert len(d.rangos) == 11                           # rangos vacíos también aparecen


def test_distribucion_por_tipo(db):
    srv, _ = servicio(db)
    assert srv.distribucion(ADMIN, P, "final").total == 3


def test_promedio_por_materia_ordenado_y_sin_nulos(db):
    srv, _ = servicio(db)
    materias = srv.promedio_por_materia(PROFE, P)
    assert [m.materia_clave for m in materias] == ["ISC702", "ISC701"]
    assert srv.promedio_por_materia(PROFE, P, cuantas=1)[0].materia_clave == "ISC702"
    assert len(srv.promedio_por_materia(PROFE, P, cuantas=0)) == 1     # mínimo 1


def test_entregas_por_centro(db):
    srv, _ = servicio(db)
    centros = {c.centro: c for c in srv.entregas_por_centro(ADMIN, P)}
    assert centros["CCEA"].no_entregadas == 4 and centros["CCB"].a_tiempo == 8


@pytest.mark.parametrize("metodo", ["distribucion", "promedio_por_materia", "entregas_por_centro"])
def test_alumno_no_ve_agregados(db, metodo):
    srv, _ = servicio(db)
    with pytest.raises(PermisoDenegadoError):
        getattr(srv, metodo)(ALUMNO, P)


def test_periodo_sin_datos(db):
    srv, _ = servicio(db)
    assert srv.distribucion(PROFE, "2020-ENE-JUN").total == 0
    assert srv.entregas_por_centro(PROFE, "2020-ENE-JUN") == []


def test_mongo_caido_es_servicio_no_disponible():
    class ColeccionCaida:
        def find(self, *args, **kwargs):
            raise ServerSelectionTimeoutError("no responde")

    class BaseCaida:
        def __getitem__(self, nombre):
            return ColeccionCaida()

    repo = RepositorioEstadisticas(BaseCaida())
    with pytest.raises(ServicioNoDisponibleError) as info:
        repo.actividad_de_alumno(7)
    assert isinstance(info.value.__cause__, ServerSelectionTimeoutError)


def test_periodo_rechaza_operadores_e_inyeccion():
    # El periodo es lo único de texto que llega a MongoDB: con el patrón no puede
    # traer {"$ne": ""} ni comillas, así que solo entra como valor.
    with pytest.raises(ValidationError):
        TypeAdapter(Periodo).validate_python({"$ne": ""})
    with pytest.raises(ValidationError):
        TypeAdapter(Periodo).validate_python("2026-AGO-DIC'; db.drop()")
    assert TypeAdapter(Periodo).validate_python(P) == P


def test_dependencia_arma_el_servicio(db):
    class ClienteFalso(dict):
        cerrado = False

        def close(self):
            ClienteFalso.cerrado = True

    app = crear_app(configuracion(), fabrica_pool=lambda c: PoolFalso(),
                    fabrica_mongo=lambda c: ClienteFalso(sigaf_analitica=db))

    @app.get("/_prueba_estadisticas")
    def prueba(est: Estadisticas) -> dict:
        return {"centros": len(est.entregas_por_centro(ADMIN, P))}

    with TestClient(app) as client:
        assert client.get("/_prueba_estadisticas").json() == {"centros": 2}
    assert ClienteFalso.cerrado                        # el lifespan cierra MongoDB


def test_cliente_real_no_conecta_al_crearse():
    from app.datos.mongo import TIEMPO_ESPERA_MS, crear_cliente_mongo

    cliente = crear_cliente_mongo(configuracion())
    try:
        assert cliente.options.server_selection_timeout == TIEMPO_ESPERA_MS / 1000
        assert cliente.codec_options.tz_aware
    finally:
        cliente.close()
