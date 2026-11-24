from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.dominio.excepciones import NoEncontradoError
from app.dominio.personas import Profesor
from app.esquemas.calificaciones import CalificacionNueva
from app.esquemas.entregas import CalificacionDeEntrega
from app.esquemas.tareas import TareaNueva
from app.repositorios.profesor import SQL_CREAR_TAREA, SQL_CREAR_TAREA_CON_MARGEN
from app.servicios.profesor import ServicioProfesor
from tests.fakes import bd_falsa

PROFE = Profesor(20, "p@sigaf.test", profesor_id=5)
LIMITE = datetime.now(UTC) + timedelta(days=3)
FILA_TAREA = {"tarea_id": 1, "grupo_id": 4, "titulo": "P1", "descripcion": None,
              "fecha_limite": LIMITE, "margen_tardia_horas": Decimal("48"),
              "cierre_entrega": LIMITE + timedelta(hours=48)}


def servicio(*respuestas):
    bd, cur = bd_falsa(*respuestas)
    return ServicioProfesor(bd), cur


def test_grupos_del_profesor_del_token():
    srv, cur = servicio([{"grupo_id": 4, "clave": "7A", "materia_clave": "ISC701",
                          "materia": "Datos", "periodo": "2026-AGO-DIC", "cupo": 40,
                          "inscritos": 32}])
    assert srv.grupos(PROFE)[0].inscritos == 32
    assert cur.sql_de_negocio()[0][1] == (5,)


def test_alumnos_de_grupo_propio():
    srv, cur = servicio({"?column?": 1}, [{"alumno_id": 7, "nombre": "Ana", "apellidos": "Ruiz"}])
    alumnos = srv.alumnos_de_grupo(PROFE, 4)
    assert alumnos[0].nombre == "Ana"
    assert cur.sql_de_negocio()[1][1] == (5, 4)  # fn_alumnos_de_profesor(profesor del token)


def test_alumnos_de_grupo_ajeno():
    srv, cur = servicio(None)
    with pytest.raises(NoEncontradoError, match="no es tuyo"):
        srv.alumnos_de_grupo(PROFE, 4)
    assert len(cur.sql_de_negocio()) == 1


def test_crear_tarea_sin_margen_usa_default_de_la_base():
    srv, cur = servicio({"?column?": 1}, FILA_TAREA)
    tarea = srv.crear_tarea(PROFE, 4, TareaNueva(titulo="P1", fecha_limite=LIMITE))
    assert tarea.margen_tardia_horas == 48.0
    sql, params = cur.sql_de_negocio()[1]
    assert sql == SQL_CREAR_TAREA and len(params) == 4


def test_crear_tarea_con_margen():
    srv, cur = servicio({"?column?": 1}, {**FILA_TAREA, "margen_tardia_horas": Decimal("0")})
    srv.crear_tarea(PROFE, 4, TareaNueva(titulo="P1", fecha_limite=LIMITE, margen_tardia_horas=0))
    sql, params = cur.sql_de_negocio()[1]
    assert sql == SQL_CREAR_TAREA_CON_MARGEN and params[-1] == 0


def test_crear_tarea_en_grupo_ajeno():
    srv, cur = servicio(None)
    with pytest.raises(NoEncontradoError):
        srv.crear_tarea(PROFE, 4, TareaNueva(titulo="P1", fecha_limite=LIMITE))
    assert len(cur.sql_de_negocio()) == 1
    assert cur.ejecutadas  # hubo rollback, no commit (lo cubre test_postgres)


def test_calificar_entrega_propia():
    srv, cur = servicio(
        {"entrega_id": 9, "calificacion": Decimal("9.5"), "retroalimentacion": "Bien"}
    )
    r = srv.calificar_entrega(PROFE, 9, CalificacionDeEntrega(calificacion="9.5",
                                                               retroalimentacion="Bien"))
    assert r.calificacion == 9.5
    assert cur.sql_de_negocio()[0][1] == (Decimal("9.5"), "Bien", 9, 5)


def test_calificar_entrega_ajena():
    srv, _ = servicio(None)
    with pytest.raises(NoEncontradoError):
        srv.calificar_entrega(PROFE, 9, CalificacionDeEntrega(calificacion="9"))


def test_registrar_calificacion_propia():
    srv, cur = servicio({"calificacion_id": 1, "inscripcion_id": 3, "tipo": "parcial1",
                         "valor": Decimal("8"), "validada": False})
    r = srv.registrar_calificacion(PROFE, CalificacionNueva(inscripcion_id=3, tipo="parcial1",
                                                            valor="8"))
    assert r.valor == 8.0 and r.validada is False
    assert cur.sql_de_negocio()[0][1] == ("parcial1", Decimal("8"), 3, 5)


def test_registrar_calificacion_ajena():
    srv, _ = servicio(None)
    with pytest.raises(NoEncontradoError, match="no es de tus grupos"):
        srv.registrar_calificacion(PROFE, CalificacionNueva(inscripcion_id=3, tipo="final",
                                                            valor="8"))
