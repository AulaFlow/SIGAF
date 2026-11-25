from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.dominio.excepciones import EntregaFueraDeTiempoError, NoEncontradoError
from app.dominio.personas import Alumno
from app.esquemas.entregas import EntregaNueva
from app.servicios.alumno import ServicioAlumno
from tests.fakes import ErrorBD, bd_falsa

ALUMNO = Alumno(10, "a@sigaf.test", alumno_id=7)
AHORA = datetime.now(UTC)


def servicio(*respuestas):
    bd, cur = bd_falsa(*respuestas)
    return ServicioAlumno(bd), cur


def test_mis_datos_usa_la_sesion_del_alumno():
    srv, cur = servicio({"alumno_id": 7, "nombre": "Ana", "apellidos": "Ruiz"})
    datos = srv.mis_datos(ALUMNO)
    assert datos.nombre == "Ana"
    assert ("SELECT set_config(%s, %s, true)", ("sigaf.alumno_sesion", "7")) in cur.ejecutadas
    assert cur.sql_de_negocio()[0][1] == ()      # fn_mis_datos() no recibe id


def test_mis_datos_sin_registro():
    srv, _ = servicio(None)
    with pytest.raises(NoEncontradoError):
        srv.mis_datos(ALUMNO)


def test_boleta_filtra_por_el_alumno_del_token():
    fila = {"inscripcion_id": 1, "materia_clave": "ISC701", "materia": "Datos",
            "parcial1": Decimal("8.5"), "parcial2": None, "parcial3": None,
            "promedio_parciales": Decimal("8.5"), "final": None}
    srv, cur = servicio([fila])
    boleta = srv.boleta(ALUMNO)
    assert boleta[0].parcial1 == 8.5 and boleta[0].final is None
    assert cur.sql_de_negocio()[0][1] == (7,)


def test_pendientes_con_cierre_y_solo_tardia():
    fila = {"tarea_id": 3, "titulo": "P1", "materia": "Datos",
            "fecha_limite": AHORA - timedelta(hours=1),
            "cierre_entrega": AHORA + timedelta(hours=47),
            "margen_tardia_horas": Decimal("48"), "solo_tardia": True}
    srv, cur = servicio([fila])
    p = srv.pendientes(ALUMNO)[0]
    assert p.solo_tardia and p.margen_tardia_horas == 48.0
    sql, params = cur.sql_de_negocio()[0]
    assert "cierre_entrega > now()" in sql and params == (7,)


def test_situacion():
    srv, _ = servicio({"materias_aprobadas": 5, "materias_reprobadas": 1,
                       "creditos_aprobados": 40, "promedio_general": Decimal("8.7")})
    assert srv.situacion(ALUMNO).promedio_general == 8.7


def test_situacion_inexistente():
    srv, _ = servicio(None)
    with pytest.raises(NoEncontradoError):
        srv.situacion(ALUMNO)


def test_entregar_usa_su_inscripcion_y_no_manda_fecha():
    srv, cur = servicio(
        {"inscripcion_id": 99},
        {"entrega_id": 1, "tarea_id": 3, "entregada_en": AHORA, "estado": "tardia"},
    )
    r = srv.entregar(ALUMNO, 3, EntregaNueva())
    assert r.estado == "tardia"
    (sql1, p1), (sql2, p2) = cur.sql_de_negocio()
    assert p1 == (3, 7)                          # tarea, alumno del token
    assert p2[:2] == (3, 99)                     # tarea, SU inscripción
    assert "entregada_en" not in sql2.split("RETURNING")[0]


def test_entregar_tarea_ajena():
    srv, cur = servicio(None)
    with pytest.raises(NoEncontradoError, match="no es de tus grupos"):
        srv.entregar(ALUMNO, 3, EntregaNueva())
    assert len(cur.sql_de_negocio()) == 1        # no intentó insertar


def test_entregar_fuera_de_tiempo():
    bd, cur = bd_falsa({"inscripcion_id": 99})
    original = cur.execute

    def execute(sql, parametros=()):
        original(sql, parametros)
        if sql.lstrip().startswith("INSERT INTO entrega"):
            raise ErrorBD("SG001", "Entrega fuera de tiempo para la tarea 3")

    cur.execute = execute
    with pytest.raises(EntregaFueraDeTiempoError, match="tarea 3"):
        ServicioAlumno(bd).entregar(ALUMNO, 3, EntregaNueva())
