"""Conexión a PostgreSQL con DB-API 2.0 (psycopg 3), pool y transacciones.

Cada operación de la API corre en UNA transacción, con una conexión prestada
del pool:
    - si todo sale bien  -> commit
    - si algo falla      -> rollback y la base queda como estaba
    - siempre            -> la conexión regresa al pool

Al iniciar la transacción se ponen en la sesión, con set_config(..., true)
(true = solo dura esta transacción; al reutilizar la conexión del pool no
queda nada de la petición anterior):
    - search_path = sigaf, public
    - las llaves de cifrado y seudonimización (vienen de variables de entorno)
    - las variables de la persona autenticada (p. ej. sigaf.alumno_sesion)
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ..config import Configuracion
from ..dominio.personas import Persona
from .errores import traducir_error_bd


class FuenteDeConexiones(Protocol):
    """Lo único que BaseDeDatos necesita de un pool (en pruebas, uno falso)."""

    def getconn(self) -> psycopg.Connection: ...

    def putconn(self, conexion: psycopg.Connection) -> None: ...


def crear_pool(config: Configuracion) -> ConnectionPool:
    """Pool de conexiones de sigaf_api_svc. Se abre y cierra en el lifespan de la app."""
    return ConnectionPool(
        config.dsn,
        min_size=1,
        max_size=config.db_pool_max,
        open=False,
        name="sigaf_api",
        check=ConnectionPool.check_connection,   # descarta conexiones caídas antes de prestarlas
    )


class BaseDeDatos:
    def __init__(self, config: Configuracion, pool: FuenteDeConexiones) -> None:
        self._config = config
        self._pool = pool

    def pool_para(self, centro_academico_id: int | None = None) -> FuenteDeConexiones:
        """Punto de extensión para el enrutador por centro (issue #6 de alex).

        Hoy hay un solo pool. El enrutador sobrescribe este método para elegir
        el pool del fragmento A o B según directorio_fragmento.
        """
        return self._pool

    def _variables_de_sesion(self, persona: Persona | None) -> dict[str, str]:
        variables = {
            "search_path": "sigaf, public",
            "sigaf.llave_datos": self._config.llave_datos,
            "sigaf.llave_seudonimo": self._config.llave_seudonimo,
        }
        if persona is not None:
            variables.update(persona.variables_de_sesion())
        return variables

    @contextmanager
    def transaccion(
        self, persona: Persona | None = None, centro_academico_id: int | None = None
    ) -> Iterator[psycopg.Cursor]:
        pool = self.pool_para(centro_academico_id)
        conexion = pool.getconn()
        try:
            with conexion.cursor(row_factory=dict_row) as cur:   # filas como dict
                for nombre, valor in self._variables_de_sesion(persona).items():
                    # Parámetros %s: el driver manda los valores aparte (nada de f-strings en SQL).
                    cur.execute("SELECT set_config(%s, %s, true)", (nombre, valor))
                yield cur
        except psycopg.Error as error:
            conexion.rollback()
            traducido = traducir_error_bd(error)
            if traducido is None:
                raise
            raise traducido from error
        except BaseException:   # cualquier otra cosa (incluso Ctrl+C): rollback y se propaga
            conexion.rollback()
            raise
        else:
            conexion.commit()
        finally:
            pool.putconn(conexion)   # siempre regresa al pool (si quedó rota, el pool la descarta)
