"""Rutas de administrador contra el esquema real (sigaf-db), sin dejar rastro.

Se conectan como sigaf_api_svc, igual que la API.
"""

import pytest

from app.dominio.excepciones import NoEncontradoError
from app.dominio.personas import Administrador
from app.esquemas.administrador import DatosDeAlumno
from app.repositorios.administrador import RepositorioAdministrador
from app.repositorios.inscripciones import RepositorioInscripciones
from app.servicios.administrador import ServicioAdministrador
from tests.conftest import Revertir, solo_con_base

pytestmark = solo_con_base
ADMIN = Administrador(usuario_id=1, correo="admin@sigaf.test")


def test_centro_del_grupo_y_del_alumno(bd_real):
    with bd_real.transaccion(ADMIN) as cur:
        cur.execute("SELECT grupo_id, centro_academico_id FROM grupo LIMIT 1")
        grupo = cur.fetchone()
        cur.execute("""SELECT a.alumno_id, c.centro_academico_id FROM alumno a
                       JOIN carrera c ON c.carrera_id = a.carrera_id LIMIT 1""")
        alumno = cur.fetchone()
        repo = RepositorioAdministrador(cur)
        assert repo.centros_del_grupo(grupo["grupo_id"]) == [grupo["centro_academico_id"]]
        assert repo.centros_del_alumno(alumno["alumno_id"]) == [alumno["centro_academico_id"]]
        assert repo.centros_del_grupo(10**15) == []


def test_admin_inscribe_en_el_centro_del_grupo(bd_real):
    with pytest.raises(Revertir):
        with bd_real.transaccion(ADMIN) as cur:
            # Un alumno y un grupo de su carrera en el que no esté inscrito en esa materia.
            cur.execute("""
                SELECT a.alumno_id, g.grupo_id FROM alumno a
                JOIN materia m ON m.carrera_id = a.carrera_id
                JOIN grupo g ON g.materia_id = m.materia_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM inscripcion i JOIN grupo g2 ON g2.grupo_id = i.grupo_id
                    WHERE i.alumno_id = a.alumno_id AND g2.materia_id = g.materia_id
                      AND g2.periodo_id = g.periodo_id AND i.estado = 'activa')
                  AND (SELECT count(*) FROM inscripcion i WHERE i.grupo_id = g.grupo_id
                       AND i.estado = 'activa') < g.cupo
                LIMIT 1""")
            par = cur.fetchone()
            if par is None:
                pytest.skip("no hay un par alumno-grupo libre en los datos de prueba")
            repo = RepositorioAdministrador(cur)
            assert repo.centros_del_grupo(par["grupo_id"])
            assert RepositorioInscripciones(cur).inscribir(par["alumno_id"], par["grupo_id"]) > 0
            raise Revertir


def test_alumno_inexistente_es_404(bd_real):
    with pytest.raises(NoEncontradoError):
        ServicioAdministrador(bd_real).datos_alumno(ADMIN, 10**15)


@pytest.mark.xfail(reason="Necesita db/08_permisos_admin.sql (decisión de seguridad pendiente)",
                   strict=False)
def test_admin_lee_datos_personales(bd_real):
    with bd_real.transaccion(ADMIN) as cur:
        cur.execute("SELECT alumno_id FROM alumno_datos_personales LIMIT 1")
        alumno_id = cur.fetchone()["alumno_id"]
    datos = ServicioAdministrador(bd_real).datos_alumno(ADMIN, alumno_id)
    assert isinstance(datos, DatosDeAlumno) and datos.nombre and datos.apellidos
