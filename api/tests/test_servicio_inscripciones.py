import pytest

from app.dominio.excepciones import InscripcionDuplicadaError, PermisoDenegadoError
from app.dominio.personas import Administrador, Alumno, Profesor
from app.servicios.inscripciones import ServicioInscripciones
from tests.fakes import ErrorBD, bd_falsa


def test_alumno_se_inscribe_a_si_mismo():
    bd, cur = bd_falsa({"p_inscripcion": 77})
    r = ServicioInscripciones(bd).inscribir(Alumno(1, "a@sigaf.test", 7), grupo_id=4)
    assert (r.inscripcion_id, r.alumno_id, r.grupo_id) == (77, 7, 4)
    assert cur.sql_de_negocio()[0] == ("CALL sp_inscribir_alumno(%s, %s, NULL)", (7, 4))


def test_alumno_no_inscribe_a_otro():
    bd, cur = bd_falsa()
    with pytest.raises(PermisoDenegadoError):
        ServicioInscripciones(bd).inscribir(Alumno(1, "a@sigaf.test", 7), 4, alumno_id=8)
    assert cur.ejecutadas == []                  # ni abrió transacción


def test_admin_inscribe_a_cualquiera():
    bd, cur = bd_falsa({"p_inscripcion": 78})
    r = ServicioInscripciones(bd).inscribir(Administrador(1, "x@sigaf.test"), 4, alumno_id=8)
    assert r.alumno_id == 8
    assert cur.sql_de_negocio()[0][1] == (8, 4)


def test_profesor_no_inscribe():
    bd, _ = bd_falsa()
    with pytest.raises(PermisoDenegadoError):
        ServicioInscripciones(bd).inscribir(Profesor(1, "p@sigaf.test", 5), 4, alumno_id=8)


def test_duplicada_desde_el_procedimiento():
    bd, cur = bd_falsa()

    def execute(sql, parametros=()):
        if sql.startswith("CALL"):
            raise ErrorBD("P0001", "El alumno ya está inscrito en esta materia en el periodo")

    cur.execute = execute
    with pytest.raises(InscripcionDuplicadaError):
        ServicioInscripciones(bd).inscribir(Alumno(1, "a@sigaf.test", 7), 4)
