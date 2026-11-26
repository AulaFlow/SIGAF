"""Pruebas de las rutas HTTP (issue #23), sin base de datos ni MongoDB.

La persona y los servicios se sustituyen con app.dependency_overrides: así se prueba
solo la capa HTTP (roles, validación, códigos y a qué servicio llama cada ruta).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencias import obtener_estadisticas
from app.dominio.excepciones import NoEncontradoError
from app.dominio.personas import Administrador, Alumno, Persona, Profesor
from app.esquemas.alumno import MateriaBoleta, MisDatos, Pendiente, SituacionAcademica
from app.esquemas.calificaciones import CalificacionRegistrada
from app.esquemas.entregas import EntregaCalificada, EntregaRegistrada
from app.esquemas.estadisticas import (
    ActividadDelAlumno,
    Distribucion,
    EntregasCentro,
    PromedioMateria,
    RangoCalificaciones,
    ResumenDeGrupo,
)
from app.esquemas.inscripciones import InscripcionCreada
from app.esquemas.profesor import AlumnoDelGrupo, GrupoDelProfesor
from app.esquemas.tareas import Tarea
from app.main import crear_app
from app.rutas.servicios import servicio_alumno, servicio_inscripciones, servicio_profesor
from app.seguridad import requiere_rol, usuario_actual
from app.servicios.alumno import ServicioAlumno
from app.servicios.estadisticas import ServicioEstadisticas
from app.servicios.inscripciones import ServicioInscripciones
from app.servicios.profesor import ServicioProfesor
from tests.fakes import configuracion, mongo_falso

AHORA = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
ALUMNO = Alumno(usuario_id=10, correo="alumno@sigaf.test", alumno_id=7, centro_academico_id=2)
PROFESOR = Profesor(usuario_id=20, correo="profe@sigaf.test", profesor_id=3,
                    centro_academico_id=1)
ADMIN = Administrador(usuario_id=1, correo="admin@sigaf.test")


class Entorno:
    """La app con servicios falsos (Mock con la forma del servicio real)."""

    def __init__(self) -> None:
        self.app: FastAPI = crear_app(configuracion(), fabrica_pool=lambda config: None,
                                      fabrica_mongo=mongo_falso)
        self.alumnos = Mock(spec=ServicioAlumno)
        self.profesores = Mock(spec=ServicioProfesor)
        self.inscripciones = Mock(spec=ServicioInscripciones)
        self.estadisticas = Mock(spec=ServicioEstadisticas)
        o = self.app.dependency_overrides
        o[servicio_alumno] = lambda: self.alumnos
        o[servicio_profesor] = lambda: self.profesores
        o[servicio_inscripciones] = lambda: self.inscripciones
        o[obtener_estadisticas] = lambda: self.estadisticas
        # Sin "with": no corre el lifespan, así que no se abre ninguna base.
        self.cliente = TestClient(self.app)

    def como(self, persona: Persona | None) -> TestClient:
        if persona is None:
            self.app.dependency_overrides.pop(usuario_actual, None)
        else:
            self.app.dependency_overrides[usuario_actual] = lambda: persona
        return self.cliente


@pytest.fixture
def e() -> Entorno:
    return Entorno()


# ---------------------------------------------------------------- sesión y roles

RUTAS_ALUMNO = [("get", "/alumno/datos"), ("get", "/alumno/boleta"),
                ("get", "/alumno/pendientes"), ("get", "/alumno/situacion"),
                ("post", "/alumno/tareas/5/entregas"), ("post", "/alumno/inscripciones"),
                ("get", "/alumno/actividad")]
RUTAS_PROFESOR = [("get", "/profesor/grupos"), ("get", "/profesor/grupos/4/alumnos"),
                  ("post", "/profesor/grupos/4/tareas"),
                  ("put", "/profesor/entregas/9/calificacion"),
                  ("post", "/profesor/calificaciones"), ("get", "/profesor/grupos/4/resumen")]
RUTAS_ESTADISTICAS = [("get", "/estadisticas/distribucion?periodo=2026-AGO-DIC"),
                      ("get", "/estadisticas/promedio-por-materia?periodo=2026-AGO-DIC"),
                      ("get", "/estadisticas/entregas-por-centro?periodo=2026-AGO-DIC")]
TODAS = RUTAS_ALUMNO + RUTAS_PROFESOR + RUTAS_ESTADISTICAS


@pytest.mark.parametrize(("metodo", "ruta"), TODAS)
def test_sin_sesion_responde_401(e, metodo, ruta):
    # Sin encabezado Authorization: usuario_actual() responde 401 (#11).
    r = e.como(None).request(metodo, ruta, json={})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_ALUMNO)
@pytest.mark.parametrize("persona", [PROFESOR, ADMIN])
def test_rutas_de_alumno_rechazan_otros_roles(e, metodo, ruta, persona):
    assert e.como(persona).request(metodo, ruta, json={}).status_code == 403


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_PROFESOR)
@pytest.mark.parametrize("persona", [ALUMNO, ADMIN])
def test_rutas_de_profesor_rechazan_otros_roles(e, metodo, ruta, persona):
    assert e.como(persona).request(metodo, ruta, json={}).status_code == 403


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_ESTADISTICAS)
def test_estadisticas_rechazan_al_alumno(e, metodo, ruta):
    assert e.como(ALUMNO).request(metodo, ruta).status_code == 403


def test_el_rol_se_revisa_antes_de_llamar_al_servicio(e):
    e.como(PROFESOR).get("/alumno/boleta")
    e.alumnos.boleta.assert_not_called()


def test_requiere_rol_sin_roles_es_un_error_de_programacion():
    with pytest.raises(ValueError):
        requiere_rol()


# ---------------------------------------------------------------- alumno

def test_mis_datos(e):
    e.alumnos.mis_datos.return_value = MisDatos(alumno_id=7, nombre="Ana", apellidos="Luna")
    r = e.como(ALUMNO).get("/alumno/datos")
    assert r.status_code == 200
    assert r.json() == {"alumno_id": 7, "nombre": "Ana", "apellidos": "Luna"}
    e.alumnos.mis_datos.assert_called_once_with(ALUMNO)


def test_boleta(e):
    e.alumnos.boleta.return_value = [MateriaBoleta(
        inscripcion_id=1, materia_clave="M01", materia="Bases", parcial1=8, parcial2=None,
        parcial3=None, promedio_parciales=8, final=None)]
    r = e.como(ALUMNO).get("/alumno/boleta")
    assert r.status_code == 200 and r.json()[0]["materia"] == "Bases"
    e.alumnos.boleta.assert_called_once_with(ALUMNO)


def test_pendientes(e):
    e.alumnos.pendientes.return_value = [Pendiente(
        tarea_id=5, titulo="Práctica", materia="Bases", fecha_limite=AHORA,
        margen_tardia_horas=48, cierre_entrega=AHORA, solo_tardia=False)]
    r = e.como(ALUMNO).get("/alumno/pendientes")
    assert r.status_code == 200 and r.json()[0]["tarea_id"] == 5


def test_situacion(e):
    e.alumnos.situacion.return_value = SituacionAcademica(
        materias_aprobadas=10, materias_reprobadas=1, creditos_aprobados=80,
        promedio_general=8.7)
    r = e.como(ALUMNO).get("/alumno/situacion")
    assert r.status_code == 200 and r.json()["promedio_general"] == 8.7


def test_entregar_llama_al_servicio_con_la_tarea_de_la_url(e):
    e.alumnos.entregar.return_value = EntregaRegistrada(
        entrega_id=40, tarea_id=5, entregada_en=AHORA, estado="a_tiempo")
    cuerpo = {"archivo_ruta": "entregas/7/tarea5.pdf", "archivo_tamano_bytes": 1200,
              "archivo_tipo": "application/pdf"}
    r = e.como(ALUMNO).post("/alumno/tareas/5/entregas", json=cuerpo)
    assert r.status_code == 201 and r.json()["estado"] == "a_tiempo"
    persona, tarea_id, datos = e.alumnos.entregar.call_args.args
    assert (persona, tarea_id, datos.archivo_ruta) == (ALUMNO, 5, "entregas/7/tarea5.pdf")


def test_entregar_no_acepta_fecha_del_cliente(e):
    r = e.como(ALUMNO).post("/alumno/tareas/5/entregas",
                            json={"entregada_en": "2020-01-01T00:00:00Z"})
    assert r.status_code == 422
    e.alumnos.entregar.assert_not_called()


@pytest.mark.parametrize("tarea_id", ["0", "-3", "abc", "99999999999999999999"])
def test_id_invalido_en_la_url_responde_422(e, tarea_id):
    r = e.como(ALUMNO).post(f"/alumno/tareas/{tarea_id}/entregas", json={})
    assert r.status_code == 422


def test_inscribirme(e):
    e.inscripciones.inscribir.return_value = InscripcionCreada(
        inscripcion_id=99, alumno_id=7, grupo_id=4)
    r = e.como(ALUMNO).post("/alumno/inscripciones", json={"grupo_id": 4})
    assert r.status_code == 201 and r.json()["alumno_id"] == 7
    e.inscripciones.inscribir.assert_called_once_with(ALUMNO, 4)


def test_inscribirme_no_deja_colar_otro_alumno(e):
    r = e.como(ALUMNO).post("/alumno/inscripciones", json={"grupo_id": 4, "alumno_id": 8})
    assert r.status_code == 422
    e.inscripciones.inscribir.assert_not_called()


def test_mi_actividad(e):
    e.estadisticas.mi_actividad.return_value = [ActividadDelAlumno(
        periodo="2026-AGO-DIC", centro="CCEA", entregas_a_tiempo=8, entregas_tardias=1,
        no_entregadas=1, faltas=2)]
    r = e.como(ALUMNO).get("/alumno/actividad")
    assert r.status_code == 200 and r.json()[0]["centro"] == "CCEA"
    e.estadisticas.mi_actividad.assert_called_once_with(ALUMNO)


def test_error_de_negocio_sale_del_servicio_sin_tocarlo(e):
    # La ruta no traduce errores: lo hace el manejador de Ricardo (#7) -> 404.
    e.alumnos.situacion.side_effect = NoEncontradoError("No se encontró")
    r = e.como(ALUMNO).get("/alumno/situacion")
    assert r.status_code == 404
    assert r.json() == {"error": "no_encontrado", "mensaje": "No se encontró"}


# ---------------------------------------------------------------- profesor

def test_mis_grupos(e):
    e.profesores.grupos.return_value = [GrupoDelProfesor(
        grupo_id=4, clave="A1", materia_clave="M01", materia="Bases", periodo="2026-AGO-DIC",
        cupo=30, inscritos=25)]
    r = e.como(PROFESOR).get("/profesor/grupos")
    assert r.status_code == 200 and r.json()[0]["inscritos"] == 25
    e.profesores.grupos.assert_called_once_with(PROFESOR)


def test_alumnos_de_grupo(e):
    e.profesores.alumnos_de_grupo.return_value = [AlumnoDelGrupo(
        alumno_id=7, nombre="Ana", apellidos="Luna")]
    r = e.como(PROFESOR).get("/profesor/grupos/4/alumnos")
    assert r.status_code == 200
    e.profesores.alumnos_de_grupo.assert_called_once_with(PROFESOR, 4)


def test_crear_tarea(e):
    e.profesores.crear_tarea.return_value = Tarea(
        tarea_id=5, grupo_id=4, titulo="Práctica", descripcion=None, fecha_limite=AHORA,
        margen_tardia_horas=48, cierre_entrega=AHORA)
    r = e.como(PROFESOR).post("/profesor/grupos/4/tareas", json={
        "titulo": "Práctica", "fecha_limite": "2026-11-30T23:59:00-06:00"})
    assert r.status_code == 201 and r.json()["tarea_id"] == 5
    persona, grupo_id, datos = e.profesores.crear_tarea.call_args.args
    assert (persona, grupo_id, datos.titulo) == (PROFESOR, 4, "Práctica")


def test_crear_tarea_exige_zona_horaria(e):
    r = e.como(PROFESOR).post("/profesor/grupos/4/tareas", json={
        "titulo": "Práctica", "fecha_limite": "2026-11-30T23:59:00"})
    assert r.status_code == 422


def test_calificar_entrega(e):
    e.profesores.calificar_entrega.return_value = EntregaCalificada(
        entrega_id=9, calificacion=9.5, retroalimentacion="Bien")
    r = e.como(PROFESOR).put("/profesor/entregas/9/calificacion",
                             json={"calificacion": "9.5", "retroalimentacion": "Bien"})
    assert r.status_code == 200 and r.json()["calificacion"] == 9.5
    persona, entrega_id, _ = e.profesores.calificar_entrega.call_args.args
    assert (persona, entrega_id) == (PROFESOR, 9)


@pytest.mark.parametrize("valor", ["10.5", "-1"])
def test_calificacion_fuera_de_0_a_10_responde_422(e, valor):
    r = e.como(PROFESOR).put("/profesor/entregas/9/calificacion", json={"calificacion": valor})
    assert r.status_code == 422
    e.profesores.calificar_entrega.assert_not_called()


def test_registrar_calificacion(e):
    e.profesores.registrar_calificacion.return_value = CalificacionRegistrada(
        calificacion_id=1, inscripcion_id=3, tipo="parcial1", valor=8.0, validada=False)
    r = e.como(PROFESOR).post("/profesor/calificaciones", json={
        "inscripcion_id": 3, "tipo": "parcial1", "valor": "8"})
    assert r.status_code == 201 and r.json()["tipo"] == "parcial1"


def test_registrar_calificacion_tipo_invalido(e):
    r = e.como(PROFESOR).post("/profesor/calificaciones", json={
        "inscripcion_id": 3, "tipo": "parcial9", "valor": "8"})
    assert r.status_code == 422


def test_resumen_de_grupo(e):
    e.estadisticas.resumen_de_grupo.return_value = [ResumenDeGrupo(
        periodo="2026-AGO-DIC", materia_clave="M01", materia="Bases", alumnos=25,
        promedio=7.8, pct_aprobados=88.0, pct_asistencia=91.5)]
    r = e.como(PROFESOR).get("/profesor/grupos/4/resumen")
    assert r.status_code == 200
    e.estadisticas.resumen_de_grupo.assert_called_once_with(PROFESOR, 4)


# ---------------------------------------------------------------- estadísticas

@pytest.mark.parametrize("persona", [PROFESOR, ADMIN])
def test_distribucion(e, persona):
    e.estadisticas.distribucion.return_value = Distribucion(
        periodo="2026-AGO-DIC", tipo="final", total=3,
        rangos=[RangoCalificaciones(desde=8, total=3)])
    r = e.como(persona).get("/estadisticas/distribucion?periodo=2026-AGO-DIC&tipo=final")
    assert r.status_code == 200 and r.json()["total"] == 3
    e.estadisticas.distribucion.assert_called_once_with(persona, "2026-AGO-DIC", "final")


@pytest.mark.parametrize("consulta", ["", "?periodo=agosto", "?periodo=2026-AGO-DIC&tipo=x"])
def test_distribucion_valida_el_periodo_y_el_tipo(e, consulta):
    assert e.como(PROFESOR).get(f"/estadisticas/distribucion{consulta}").status_code == 422


def test_promedio_por_materia(e):
    e.estadisticas.promedio_por_materia.return_value = [PromedioMateria(
        materia_clave="M01", materia="Bases", promedio=6.9, alumnos=120)]
    r = e.como(ADMIN).get("/estadisticas/promedio-por-materia?periodo=2026-AGO-DIC&cuantas=5")
    assert r.status_code == 200
    e.estadisticas.promedio_por_materia.assert_called_once_with(ADMIN, "2026-AGO-DIC", 5)


@pytest.mark.parametrize("cuantas", ["0", "51"])
def test_promedio_por_materia_limita_cuantas(e, cuantas):
    url = f"/estadisticas/promedio-por-materia?periodo=2026-AGO-DIC&cuantas={cuantas}"
    assert e.como(ADMIN).get(url).status_code == 422


def test_entregas_por_centro(e):
    e.estadisticas.entregas_por_centro.return_value = [EntregasCentro(
        centro="CCB", a_tiempo=900, tardias=200, no_entregadas=100)]
    r = e.como(PROFESOR).get("/estadisticas/entregas-por-centro?periodo=2026-AGO-DIC")
    assert r.status_code == 200 and r.json()[0]["centro"] == "CCB"


# ---------------------------------------------------------------- OpenAPI (para Kevin)

def test_openapi_documenta_las_16_rutas_con_tag_resumen_y_bearer(e):
    esquema = e.app.openapi()
    operaciones = [(ruta, op) for ruta, metodos in esquema["paths"].items()
                   if ruta not in ("/health", "/auth/login")    # sin token: #11
                   and not ruta.startswith("/admin")                # admin: #7
                   for op in metodos.values()]
    assert len(operaciones) == 16
    for ruta, op in operaciones:
        assert op["tags"] and op["summary"], ruta
        assert op["security"] == [{"HTTPBearer": []}], ruta
        assert {"401", "403"} <= set(op["responses"]), ruta


def test_openapi_login_no_pide_token(e):
    op = e.app.openapi()["paths"]["/auth/login"]["post"]
    assert "security" not in op                     # es la ruta para conseguir el token
    assert {"200", "401", "422"} <= set(op["responses"])


def test_exportar_openapi_escribe_el_json(tmp_path):
    import json

    from scripts.exportar_openapi import exportar

    destino = exportar(tmp_path / "openapi.json")
    esquema = json.loads(destino.read_text(encoding="utf-8"))
    assert esquema["info"]["title"] == "SIGAF API"
    assert "/alumno/boleta" in esquema["paths"]


def test_las_fabricas_arman_cada_servicio_con_la_base():
    from app.rutas.servicios import servicio_alumno, servicio_inscripciones, servicio_profesor

    bd = object()
    for fabrica, clase in [(servicio_alumno, ServicioAlumno), (servicio_profesor, ServicioProfesor),
                           (servicio_inscripciones, ServicioInscripciones)]:
        servicio = fabrica(bd)
        assert isinstance(servicio, clase) and servicio._bd is bd
