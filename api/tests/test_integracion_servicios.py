"""El SQL de repositorios y servicios contra el esquema real (sigaf-db).

Las lecturas usan los servicios tal cual. Las escrituras usan los repositorios
dentro de una transacción que termina en rollback: no dejan rastro.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.dominio.excepciones import NoEncontradoError, ReglaDeNegocioError
from app.dominio.personas import Alumno, Profesor
from app.esquemas.alumno import Pendiente
from app.esquemas.entregas import EntregaNueva, EntregaRegistrada
from app.esquemas.tareas import Tarea, TareaNueva
from app.repositorios.entregas import RepositorioEntregas
from app.repositorios.inscripciones import RepositorioInscripciones
from app.repositorios.profesor import RepositorioProfesor
from app.servicios.alumno import ServicioAlumno
from app.servicios.profesor import ServicioProfesor
from tests.conftest import Revertir, solo_con_base

pytestmark = solo_con_base


@pytest.fixture(scope="module")
def alumno(bd_real) -> Alumno:
    with bd_real.transaccion() as cur:
        cur.execute("""SELECT a.alumno_id, a.usuario_id FROM alumno a
                       JOIN inscripcion i ON i.alumno_id = a.alumno_id AND i.estado = 'activa'
                       ORDER BY a.alumno_id LIMIT 1""")
        fila = cur.fetchone()
    return Alumno(fila["usuario_id"], "alumno@sigaf.test", fila["alumno_id"])


@pytest.fixture(scope="module")
def profesor_y_grupo(bd_real) -> tuple[Profesor, int]:
    with bd_real.transaccion() as cur:
        cur.execute("""SELECT p.profesor_id, p.usuario_id, g.grupo_id
                       FROM profesor p
                       JOIN grupo g ON g.profesor_id = p.profesor_id
                       JOIN inscripcion i ON i.grupo_id = g.grupo_id AND i.estado = 'activa'
                       ORDER BY g.grupo_id DESC LIMIT 1""")
        fila = cur.fetchone()
    return Profesor(fila["usuario_id"], "profe@sigaf.test", fila["profesor_id"]), fila["grupo_id"]


# ---- lecturas del alumno ------------------------------------------------------
def test_boleta_y_situacion(bd_real, alumno):
    srv = ServicioAlumno(bd_real)
    assert len(srv.boleta(alumno)) >= 1
    assert srv.situacion(alumno).materias_aprobadas >= 0


def test_pendientes_solo_los_que_aun_se_pueden_entregar(bd_real, alumno):
    ahora = datetime.now(UTC)
    for p in ServicioAlumno(bd_real).pendientes(alumno):
        assert isinstance(p, Pendiente)
        assert p.cierre_entrega > ahora
        assert p.solo_tardia == (p.fecha_limite < ahora)


def test_mis_datos(bd_real, alumno):
    try:
        datos = ServicioAlumno(bd_real).mis_datos(alumno)
    except NoEncontradoError:
        pytest.skip("ese alumno no tiene datos personales cargados")
    assert datos.alumno_id == alumno.alumno_id and datos.nombre


# ---- lecturas del profesor ----------------------------------------------------
def test_grupos_y_alumnos_del_profesor(bd_real, profesor_y_grupo):
    profesor, grupo_id = profesor_y_grupo
    srv = ServicioProfesor(bd_real)
    assert grupo_id in {g.grupo_id for g in srv.grupos(profesor)}
    assert isinstance(srv.alumnos_de_grupo(profesor, grupo_id), list)


def test_grupo_ajeno_no_se_ve(bd_real, profesor_y_grupo):
    profesor, _ = profesor_y_grupo
    with pytest.raises(NoEncontradoError):
        ServicioProfesor(bd_real).alumnos_de_grupo(profesor, 9_000_000_000)


# ---- escrituras (todas con rollback) --------------------------------------------
def test_tarea_entrega_y_calificaciones_sin_dejar_rastro(bd_real, profesor_y_grupo):
    profesor, grupo_id = profesor_y_grupo
    limite = datetime.now(UTC) + timedelta(days=2)
    with pytest.raises(Revertir):
        with bd_real.transaccion(profesor) as cur:
            repo = RepositorioProfesor(cur)

            # 1. Sin margen: la base pone el DEFAULT de 48 h (db/07).
            nueva = TareaNueva(titulo="IT", fecha_limite=limite)
            tarea = Tarea(**repo.crear_tarea(grupo_id, nueva))
            assert tarea.margen_tardia_horas == 48.0
            assert tarea.cierre_entrega == tarea.fecha_limite + timedelta(hours=48)

            # 2. Con margen 0.
            cero = Tarea(**repo.crear_tarea(
                grupo_id, TareaNueva(titulo="IT0", fecha_limite=limite, margen_tardia_horas=0)))
            assert cero.margen_tardia_horas == 0.0

            # 3. Un alumno del grupo entrega: la base pone entregada_en y estado.
            cur.execute("SELECT alumno_id FROM inscripcion WHERE grupo_id = %s "
                        "AND estado = 'activa' LIMIT 1", (grupo_id,))
            alumno_id = cur.fetchone()["alumno_id"]
            entregas = RepositorioEntregas(cur)
            inscripcion_id = entregas.inscripcion_para_tarea(tarea.tarea_id, alumno_id)
            entrega = EntregaRegistrada(**entregas.registrar(
                tarea.tarea_id, inscripcion_id,
                EntregaNueva(archivo_ruta="entregas/it.pdf", archivo_tamano_bytes=10,
                             archivo_tipo="application/pdf")))
            assert entrega.estado == "a_tiempo"

            # 4. El profesor la califica (solo si es de su grupo).
            calificada = repo.calificar_entrega(profesor.profesor_id, entrega.entrega_id, 9, "ok")
            assert calificada["calificacion"] == 9
            assert repo.calificar_entrega(profesor.profesor_id + 10**9, entrega.entrega_id,
                                          9, None) is None

            # 5. Calificación de un parcial (el tipo que aún no tenga esa inscripción).
            cur.execute("""SELECT t.tipo FROM unnest(ARRAY['parcial1','parcial2','parcial3',
                           'final']) AS t(tipo) WHERE NOT EXISTS (SELECT 1 FROM calificacion c
                           WHERE c.inscripcion_id = %s AND c.tipo = t.tipo) LIMIT 1""",
                        (inscripcion_id,))
            libre = cur.fetchone()
            if libre is not None:
                fila = repo.registrar_calificacion(profesor.profesor_id, inscripcion_id,
                                                   libre["tipo"], 8)
                assert fila["valor"] == 8 and fila["validada"] is False
            raise Revertir


def test_inscribir_con_el_procedimiento(bd_real):
    with pytest.raises(Revertir):
        with bd_real.transaccion() as cur:
            cur.execute("""
                SELECT a.alumno_id, g.grupo_id
                FROM alumno a
                JOIN materia m ON m.carrera_id = a.carrera_id
                JOIN grupo g   ON g.materia_id = m.materia_id
                WHERE NOT EXISTS (SELECT 1 FROM inscripcion i JOIN grupo g2 USING (grupo_id)
                                  WHERE i.alumno_id = a.alumno_id AND i.estado = 'activa'
                                    AND g2.materia_id = g.materia_id
                                    AND g2.periodo_id = g.periodo_id)
                LIMIT 1""")
            caso = cur.fetchone()
            if caso is None:
                pytest.skip("no hay un alumno libre para inscribir")
            try:
                inscripcion_id = RepositorioInscripciones(cur).inscribir(caso["alumno_id"],
                                                                         caso["grupo_id"])
            except ReglaDeNegocioError as e:    # p. ej. grupo sin cupo: también es válido
                pytest.skip(f"el procedimiento lo rechazó: {e.mensaje}")
            assert inscripcion_id > 0
            raise Revertir
