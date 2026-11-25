import psycopg.errors
import pytest

from app.datos.errores import traducir_error_bd
from app.dominio.excepciones import (
    CalificacionInvalidaError,
    DatoInvalidoError,
    EntregaFueraDeTiempoError,
    InscripcionDuplicadaError,
    NoEncontradoError,
    RegistroDuplicadoError,
    ReglaDeNegocioError,
)
from tests.fakes import ErrorBD


def test_sg001_es_entrega_fuera_de_tiempo():
    error = ErrorBD("SG001", "La tarea 4 cerró el 2026-11-20 (límite + margen de 48 h)")
    traducido = traducir_error_bd(error)
    assert isinstance(traducido, EntregaFueraDeTiempoError)
    assert "tarea 4" in traducido.mensaje


def test_entrega_fuera_de_tiempo_es_regla_de_negocio():
    assert issubclass(EntregaFueraDeTiempoError, ReglaDeNegocioError)


@pytest.mark.parametrize(
    ("error", "esperada"),
    [
        (ErrorBD("P0002", "El grupo 9 no existe"), NoEncontradoError),
        (ErrorBD("23505", tabla="inscripcion"), InscripcionDuplicadaError),
        (ErrorBD("23505", tabla="entrega"), RegistroDuplicadoError),
        (ErrorBD("23514", restriccion="calificacion_valor_check"), CalificacionInvalidaError),
        (ErrorBD("23514", restriccion="chk_tarea_margen_tardia"), DatoInvalidoError),
        (ErrorBD("P0001", "El alumno ya está inscrito en esta materia en el periodo"),
         InscripcionDuplicadaError),
        (ErrorBD("P0001", "El grupo 3 no tiene cupo (40/40)"), ReglaDeNegocioError),
    ],
)
def test_traduccion_por_sqlstate(error, esperada):
    assert type(traducir_error_bd(error)) is esperada


def test_margen_negativo_no_se_confunde_con_calificacion():
    traducido = traducir_error_bd(ErrorBD("23514", restriccion="chk_tarea_margen_tardia"))
    assert not isinstance(traducido, CalificacionInvalidaError)


def test_sqlstate_en_la_clase_tambien_funciona():
    # Errores con subclase propia en psycopg (p. ej. UniqueViolation) traen e.sqlstate.
    assert isinstance(traducir_error_bd(psycopg.errors.UniqueViolation()), RegistroDuplicadoError)


@pytest.mark.parametrize("sqlstate", ["28000", "08006", "42501", None])
def test_errores_desconocidos_no_se_traducen(sqlstate):
    assert traducir_error_bd(ErrorBD(sqlstate)) is None
