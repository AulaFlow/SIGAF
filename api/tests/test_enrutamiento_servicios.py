"""Con dos fragmentos, cada consulta de un servicio va al fragmento del centro
de la persona autenticada (enrutador de alex, #6 + centro en Persona)."""

from decimal import Decimal

from app.datos.enrutador import BaseDistribuida, Enrutador, armar_fragmentos
from app.dominio.personas import Alumno, Profesor
from app.esquemas.calificaciones import CalificacionNueva
from app.servicios.alumno import ServicioAlumno
from app.servicios.profesor import ServicioProfesor
from tests.fakes import PoolFalso, configuracion

# A = centros 1, 3, 5 · B = centros 2, 4, 6
DIRECTORIO = [(c, "A" if c % 2 else "B", "pg-a:5432" if c % 2 else "pg-b:5434",
               "rep-a:5433" if c % 2 else "rep-b:5435") for c in range(1, 7)]


def _base() -> tuple[BaseDistribuida, PoolFalso, PoolFalso]:
    pool_a, pool_b = PoolFalso(), PoolFalso()
    enrutador = Enrutador(armar_fragmentos(DIRECTORIO), {"A": pool_a, "B": pool_b})
    return BaseDistribuida(configuracion(), enrutador), pool_a, pool_b


def test_alumno_de_un_centro_del_fragmento_b_consulta_en_b():
    bd, pool_a, pool_b = _base()
    pool_b.conexion.cursor_falso.responder([])
    ServicioAlumno(bd).boleta(Alumno(1, "a@sigaf.test", 7, centro_academico_id=4))
    assert (pool_a.prestadas, pool_b.prestadas) == (0, 1)


def test_profesor_de_un_centro_del_fragmento_a_escribe_en_a():
    bd, pool_a, pool_b = _base()
    pool_a.conexion.cursor_falso.responder(
        {"calificacion_id": 1, "inscripcion_id": 3, "tipo": "parcial1",
         "valor": Decimal("8"), "validada": False})
    ServicioProfesor(bd).registrar_calificacion(
        Profesor(2, "p@sigaf.test", 5, centro_academico_id=3),
        CalificacionNueva(inscripcion_id=3, tipo="parcial1", valor="8"),
    )
    assert (pool_a.prestadas, pool_b.prestadas) == (1, 0)
    assert pool_a.conexion.commits == 1


def test_centro_explicito_gana_sobre_el_de_la_persona():
    bd, pool_a, pool_b = _base()
    with bd.transaccion(Alumno(1, "a@sigaf.test", 7, centro_academico_id=4),
                        centro_academico_id=1):
        pass
    assert (pool_a.prestadas, pool_b.prestadas) == (1, 0)


def test_sin_centro_va_al_primer_fragmento():
    bd, pool_a, pool_b = _base()
    with bd.transaccion(Alumno(1, "a@sigaf.test", 7)):
        pass
    assert (pool_a.prestadas, pool_b.prestadas) == (1, 0)
