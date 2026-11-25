import pytest

from app.datos.postgres import BaseDeDatos, crear_pool
from app.dominio.excepciones import EntregaFueraDeTiempoError
from app.dominio.personas import Alumno, Profesor
from tests.fakes import LLAVE, ErrorBD, PoolFalso, configuracion

SET_CONFIG = "SELECT set_config(%s, %s, true)"


@pytest.fixture
def pool() -> PoolFalso:
    return PoolFalso()


@pytest.fixture
def bd(pool: PoolFalso) -> BaseDeDatos:
    return BaseDeDatos(configuracion(), pool)


def test_filas_como_diccionario(bd, pool):
    from psycopg.rows import dict_row

    with bd.transaccion():
        pass
    assert pool.conexion.row_factory is dict_row


def test_commit_y_regresa_al_pool(bd, pool):
    with bd.transaccion() as cur:
        cur.execute("SELECT 1")
    assert pool.conexion.commits == 1 and pool.conexion.rollbacks == 0
    assert pool.prestadas == pool.devueltas == 1


def test_pone_llaves_y_search_path_con_parametros(bd, pool):
    with bd.transaccion():
        pass
    ejecutadas = pool.conexion.cursor_falso.ejecutadas
    assert (SET_CONFIG, ("search_path", "sigaf, public")) in ejecutadas
    assert (SET_CONFIG, ("sigaf.llave_datos", LLAVE)) in ejecutadas
    assert all(LLAVE not in sql for sql, _ in ejecutadas)   # la llave nunca va dentro del SQL


def test_alumno_autenticado_queda_en_la_sesion(bd, pool):
    with bd.transaccion(Alumno(1, "a@sigaf.test", alumno_id=42)):
        pass
    assert (SET_CONFIG, ("sigaf.alumno_sesion", "42")) in pool.conexion.cursor_falso.ejecutadas


def test_profesor_no_pone_alumno_sesion(bd, pool):
    with bd.transaccion(Profesor(1, "p@sigaf.test", profesor_id=3)):
        pass
    nombres = [p[0] for _, p in pool.conexion.cursor_falso.ejecutadas]
    assert "sigaf.alumno_sesion" not in nombres


def test_error_sg001_rollback_y_se_traduce(bd, pool):
    error = ErrorBD("SG001", "fuera de tiempo")
    with pytest.raises(EntregaFueraDeTiempoError) as info:
        with bd.transaccion():
            raise error
    assert info.value.__cause__ is error          # se conserva el error original
    assert pool.conexion.rollbacks == 1 and pool.conexion.commits == 0
    assert pool.devueltas == 1


def test_error_de_bd_desconocido_pasa_tal_cual(bd, pool):
    error = ErrorBD("08006", "se cayó la conexión")
    with pytest.raises(ErrorBD) as info:
        with bd.transaccion():
            raise error
    assert info.value is error
    assert pool.conexion.rollbacks == 1 and pool.devueltas == 1


def test_cualquier_otro_error_tambien_hace_rollback(bd, pool):
    with pytest.raises(ZeroDivisionError):
        with bd.transaccion():
            1 / 0  # noqa: B018
    assert pool.conexion.rollbacks == 1 and pool.conexion.commits == 0
    assert pool.devueltas == 1


def test_pool_para_es_el_punto_de_extension_del_enrutador(pool):
    otro = PoolFalso()

    class BaseEnrutada(BaseDeDatos):
        def pool_para(self, centro_academico_id=None):
            return otro if centro_academico_id == 4 else super().pool_para(centro_academico_id)

    bd = BaseEnrutada(configuracion(), pool)
    with bd.transaccion(centro_academico_id=4):
        pass
    assert otro.prestadas == 1 and pool.prestadas == 0


def test_crear_pool_no_conecta_hasta_abrirlo():
    nuevo = crear_pool(configuracion())
    try:
        assert nuevo.max_size == 2 and nuevo.min_size == 1
        assert nuevo.closed      # open=False: el lifespan lo abre
    finally:
        nuevo.close()


def test_incluso_interrupciones_hacen_rollback(bd, pool):
    with pytest.raises(KeyboardInterrupt):
        with bd.transaccion():
            raise KeyboardInterrupt
    assert pool.conexion.rollbacks == 1 and pool.devueltas == 1
