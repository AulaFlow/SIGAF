"""Pruebas contra PostgreSQL real (contenedor sigaf-db).

Se saltan si no hay SIGAF_PASS_API, así el CI (sin base) no falla.
Ninguna deja cambios: todo termina en rollback.
"""

import pytest

from app.dominio.excepciones import EntregaFueraDeTiempoError
from app.dominio.personas import Alumno
from tests.conftest import Revertir as _Revertir
from tests.conftest import solo_con_base

pytestmark = solo_con_base


@pytest.fixture
def bd(bd_real):
    return bd_real


def test_sesion_con_tls_search_path_y_llaves(bd):
    with bd.transaccion() as cur:
        cur.execute("SELECT current_user AS usuario, current_setting('search_path') AS ruta, "
                    "(SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()) AS con_ssl")
        fila = cur.fetchone()
        usuario, search_path, con_ssl = fila["usuario"], fila["ruta"], fila["con_ssl"]
        cur.execute("SELECT length(fn_seudonimizar(%s)) AS largo", ("A123456",))
        assert cur.fetchone()["largo"] == 64
    assert usuario == "sigaf_api_svc"
    assert search_path.startswith("sigaf")
    assert con_ssl is True


def test_llave_de_datos_en_la_sesion(bd):
    with bd.transaccion() as cur:
        cur.execute("SELECT current_setting('sigaf.llave_datos', true) AS llave")
        assert len(cur.fetchone()["llave"]) >= 32


def test_alumno_solo_ve_sus_datos(bd):
    with bd.transaccion() as cur:
        cur.execute("SELECT alumno_id, usuario_id FROM alumno ORDER BY alumno_id LIMIT 1")
        fila = cur.fetchone()
        alumno_id, usuario_id = fila["alumno_id"], fila["usuario_id"]
    with bd.transaccion(Alumno(usuario_id, "a@sigaf.test", alumno_id)) as cur:
        cur.execute("SELECT alumno_id FROM fn_mis_datos()")
        filas = cur.fetchall()
    assert filas in ([{"alumno_id": alumno_id}], [])   # [] si ese alumno no tiene datos personales


def test_entrega_despues_del_margen_es_entrega_fuera_de_tiempo(bd):
    with bd.transaccion() as cur:
        cur.execute(
            """SELECT t.tarea_id, i.inscripcion_id
               FROM tarea t
               JOIN inscripcion i ON i.grupo_id = t.grupo_id AND i.estado = 'activa'
               WHERE t.fecha_limite + t.margen_tardia < now()
                 AND NOT EXISTS (SELECT 1 FROM entrega e
                                 WHERE e.tarea_id = t.tarea_id
                                   AND e.inscripcion_id = i.inscripcion_id)
               LIMIT 1"""
        )
        caso = cur.fetchone()
    if caso is None:
        pytest.skip("no hay una tarea cerrada sin entrega para probar")
    with pytest.raises(EntregaFueraDeTiempoError, match="fuera de tiempo"):
        with bd.transaccion() as cur:
            cur.execute("INSERT INTO entrega (tarea_id, inscripcion_id) VALUES (%s, %s)",
                        (caso["tarea_id"], caso["inscripcion_id"]))


def test_rollback_no_deja_rastro(bd):
    with bd.transaccion() as cur:
        cur.execute("SELECT count(*) AS total FROM notificacion")
        antes = cur.fetchone()["total"]
    with pytest.raises(_Revertir):
        with bd.transaccion() as cur:
            cur.execute("SELECT usuario_id FROM usuario ORDER BY usuario_id LIMIT 1")
            cur.execute(
                "INSERT INTO notificacion (usuario_id, tipo, texto) VALUES (%s, 'aviso', 'prueba')",
                (cur.fetchone()["usuario_id"],),
            )
            raise _Revertir
    with bd.transaccion() as cur:
        cur.execute("SELECT count(*) AS total FROM notificacion")
        assert cur.fetchone()["total"] == antes
