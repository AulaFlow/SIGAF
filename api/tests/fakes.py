"""Dobles de prueba: conexión, cursor y errores de PostgreSQL falsos.

Así las pruebas unitarias corren sin base de datos (también en el CI).
"""

from __future__ import annotations

from types import SimpleNamespace

import psycopg

from app.config import Configuracion
from app.datos.postgres import BaseDeDatos

LLAVE = "x" * 32


def configuracion(**cambios: object) -> Configuracion:
    datos = {
        "db_host": "localhost",
        "db_puerto": 5432,
        "db_nombre": "postgres",
        "db_contrasena": "contrasena-de-prueba",
        "db_sslmode": "require",
        "db_sslrootcert": None,
        "db_pool_max": 2,
        "llave_datos": LLAVE,
        "llave_seudonimo": "y" * 32,
        "jwt_llave": "j" * 32,
        "jwt_minutos": 60,
        "mongo_uri": "mongodb://localhost:27017",
        "mongo_db": "sigaf_analitica",
        "origenes_cors": (),
    }
    datos.update(cambios)
    return Configuracion(**datos)


class ErrorBD(psycopg.DatabaseError):
    """Imita un error del servidor. Como pasa con SG001 en psycopg 3.3, e.sqlstate
    viene vacío y el código solo está en e.diag.sqlstate."""

    def __init__(self, sqlstate: str | None, mensaje: str | None = None,
                 restriccion: str | None = None, tabla: str | None = None) -> None:
        super().__init__(mensaje or "error de prueba")
        self._diag_falso = SimpleNamespace(sqlstate=sqlstate, message_primary=mensaje,
                                           constraint_name=restriccion, table_name=tabla)

    @property
    def sqlstate(self) -> str | None:   # type: ignore[override]
        return None

    @property
    def diag(self) -> SimpleNamespace:  # type: ignore[override]
        return self._diag_falso


class CursorFalso:
    """Guarda lo ejecutado y devuelve datos preparados.

    - filas: lo que devuelve fetchall() siempre (lo usa el enrutador de alex, #6).
    - responder(...): respuestas en orden para fetchone()/fetchall() (servicios);
      si hay respuestas preparadas, tienen prioridad sobre filas.
    """

    def __init__(self, filas: list[tuple] | None = None) -> None:
        self.ejecutadas: list[tuple[str, tuple]] = []
        self.filas = filas or []
        self.respuestas: list[object] = []

    def responder(self, *respuestas: object) -> CursorFalso:
        self.respuestas.extend(respuestas)
        return self

    def execute(self, sql: str, parametros: tuple = ()) -> None:
        self.ejecutadas.append((sql, parametros))

    def fetchone(self) -> object:
        return self.respuestas.pop(0)

    def fetchall(self) -> object:
        if self.respuestas:
            return self.respuestas.pop(0)
        return list(self.filas)

    def sql_de_negocio(self) -> list[tuple[str, tuple]]:
        """Lo ejecutado sin los set_config del inicio de la transacción."""
        return [(sql, p) for sql, p in self.ejecutadas if "set_config" not in sql]

    def __enter__(self) -> CursorFalso:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class ConexionFalsa:
    def __init__(self, filas: list[tuple] | None = None) -> None:
        self.cursor_falso = CursorFalso(filas)
        self.commits = 0
        self.rollbacks = 0
        self.cerrada = False

    def cursor(self, row_factory: object = None) -> CursorFalso:
        self.row_factory = row_factory
        return self.cursor_falso

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.cerrada = True


class PoolFalso:
    """Imita psycopg_pool.ConnectionPool: presta y recibe conexiones."""

    def __init__(self, conexion: ConexionFalsa | None = None) -> None:
        self.conexion = conexion or ConexionFalsa()
        self.prestadas = 0
        self.devueltas = 0
        self.abierto = False
        self.cerrado = False

    def getconn(self) -> ConexionFalsa:
        self.prestadas += 1
        return self.conexion

    def putconn(self, conexion: ConexionFalsa) -> None:
        assert conexion is self.conexion
        self.devueltas += 1

    def open(self, wait: bool = False, timeout: float = 0) -> None:
        self.abierto = True

    def close(self) -> None:
        self.cerrado = True


def bd_falsa(*respuestas: object) -> tuple[BaseDeDatos, CursorFalso]:
    """BaseDeDatos con pool falso; el cursor devolverá las respuestas en orden."""
    pool = PoolFalso()
    pool.conexion.cursor_falso.responder(*respuestas)
    return BaseDeDatos(configuracion(), pool), pool.conexion.cursor_falso


def mongo_falso(config: Configuracion | None = None) -> object:
    """Cliente de MongoDB en memoria (mongomock) para las pruebas de la app."""
    import mongomock

    return mongomock.MongoClient()
