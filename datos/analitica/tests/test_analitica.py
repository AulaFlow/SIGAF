"""Pruebas del ETL y las gráficas con MongoDB en memoria (mongomock)."""

from collections.abc import Iterator

import mongomock
import pytest

from analitica import (
    ActividadAlumno,
    ETLError,
    ProcesoETL,
    RegistroCalificacion,
    RepositorioMongo,
    ResumenGrupo,
)
from analitica.graficas import (
    GRAFICAS,
    DistribucionCalificaciones,
    EntregasPorCentro,
    PromedioPorMateria,
    SinDatosError,
    generar_todas,
)


class FuenteFalsa:
    """Fuente en memoria que cumple el protocolo FuenteAcademica."""

    def __init__(self, nombre: str, centro: int, clave: str, desplazamiento: int = 0) -> None:
        self.nombre = nombre
        self.c, self.clave, self.d = centro, clave, desplazamiento

    def resumen_grupos(self) -> Iterator[ResumenGrupo]:
        for g in range(3):
            yield ResumenGrupo(self.d + g, "2026-AGO-DIC", self.c, f"M{g}", f"Materia {g}",
                               30, 6.0 + g, 70.0, 90.0)

    def actividad_alumnos(self) -> Iterator[ActividadAlumno]:
        for a in range(10):
            yield ActividadAlumno(self.d + a, "2026-AGO-DIC", self.c, self.clave, 8, 2, 1, 0)

    def calificaciones(self) -> Iterator[RegistroCalificacion]:
        for i in range(50):
            yield RegistroCalificacion(self.d * 100 + i, i, "2026-AGO-DIC", self.c, "M0", "parcial1", (i % 11) * 1.0)


class FuenteRota(FuenteFalsa):
    def actividad_alumnos(self) -> Iterator[ActividadAlumno]:
        raise ConnectionError("se cayó el nodo")


class RepositorioEnMemoria(RepositorioMongo):
    """mongomock no soporta bulk_write con la versión actual de pymongo:
    en las pruebas se escribe documento por documento (mismo resultado)."""

    def _escribir(self, coleccion, docs):
        self._db[coleccion].delete_many({"_id": {"$in": [d["_id"] for d in docs]}})
        self._db[coleccion].insert_many(docs)
        return len(docs)


@pytest.fixture
def repo() -> RepositorioMongo:
    r = RepositorioEnMemoria(mongomock.MongoClient()["prueba"])
    r.crear_indices()
    return r


@pytest.fixture
def repo_lleno(repo: RepositorioMongo) -> RepositorioMongo:
    ProcesoETL(repo, tam_lote=7).ejecutar([FuenteFalsa("A", 1, "CCB"), FuenteFalsa("B", 2, "CCEA", 1000)])
    return repo


# --- modelos ------------------------------------------------------------------

def test_modelo_ida_y_vuelta():
    r = ResumenGrupo(5, "2026-AGO-DIC", 1, "ISC-701", "Datos", 30, 8.1, 90.0, 95.5)
    doc = r.a_documento()
    assert doc["_id"] == "2026-AGO-DIC:5" and "actualizado_en" in doc
    assert ResumenGrupo.desde_documento(doc) == r


def test_ids_estables_por_tipo():
    assert ActividadAlumno(7, "P", 1, "CCB", 0, 0, 0, 0).id == "P:7"
    assert RegistroCalificacion(42, 1, "P", 1, "M", "final", 9.0).id == "42"


# --- ETL ----------------------------------------------------------------------

def test_etl_carga_los_dos_fragmentos(repo_lleno: RepositorioMongo):
    assert repo_lleno.contar("resumen_grupo") == 6
    assert repo_lleno.contar("actividad_alumno") == 20
    assert repo_lleno.contar("historico_calificaciones") == 100


def test_etl_es_idempotente(repo_lleno: RepositorioMongo):
    ProcesoETL(repo_lleno).ejecutar([FuenteFalsa("A", 1, "CCB")])     # correr otra vez no duplica
    assert repo_lleno.contar("historico_calificaciones") == 100


def test_etl_reporta_el_fragmento_que_falla(repo: RepositorioMongo):
    with pytest.raises(ETLError, match="fragmento B"):
        ProcesoETL(repo).ejecutar([FuenteFalsa("A", 1, "CCB"), FuenteRota("B", 2, "CCEA", 1000)])
    assert repo.contar("resumen_grupo") == 6   # A quedó cargado (consistencia eventual)


def test_resultado_por_coleccion():
    r = ProcesoETL(RepositorioEnMemoria(mongomock.MongoClient()["x"])).ejecutar([FuenteFalsa("A", 1, "CCB")])
    assert r.fragmentos == ["A"]
    assert r.por_coleccion == {"resumen_grupo": 3, "actividad_alumno": 10, "historico_calificaciones": 50}


# --- consultas de las gráficas ------------------------------------------------

def test_promedio_por_materia_ordena_de_menor_a_mayor(repo_lleno: RepositorioMongo):
    g = PromedioPorMateria(repo_lleno, cuantas=2)
    datos = repo_lleno.agregar(g.coleccion, g.pipeline())
    assert [d["_id"] for d in datos] == ["M0", "M1"]
    assert datos[0]["promedio"] == 6.0 and datos[0]["alumnos"] == 60


def test_entregas_suma_por_centro(repo_lleno: RepositorioMongo):
    g = EntregasPorCentro(repo_lleno)
    datos = repo_lleno.agregar(g.coleccion, g.pipeline())
    assert [d["_id"] for d in datos] == ["CCB", "CCEA"]
    assert datos[0]["a_tiempo"] == 80 and datos[0]["tardias"] == 20 and datos[0]["no_entregadas"] == 10


def test_filtro_de_periodo(repo_lleno: RepositorioMongo):
    g = DistribucionCalificaciones(repo_lleno, periodo="2025-ENE-JUN")
    assert repo_lleno.agregar(g.coleccion, g.pipeline()) == []


# --- archivos -----------------------------------------------------------------

def test_genera_las_tres_graficas(repo_lleno: RepositorioMongo, tmp_path):
    rutas = generar_todas(repo_lleno, tmp_path)
    assert len(rutas) == len(GRAFICAS) == 3
    for ruta in rutas:
        assert ruta.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and ruta.stat().st_size > 10_000


def test_sin_datos_avisa(repo: RepositorioMongo, tmp_path):
    with pytest.raises(SinDatosError, match="ETL|datos"):
        DistribucionCalificaciones(repo).guardar(tmp_path)
