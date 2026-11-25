"""Conexiones falsas para probar el reparto sin PostgreSQL."""

from __future__ import annotations


class Resultado:
    def __init__(self, filas=None, rowcount=0):
        self._filas = filas or []
        self.rowcount = rowcount

    def fetchone(self):
        return self._filas[0] if self._filas else None

    def fetchall(self):
        return self._filas


class CopiaFalsa:
    def __init__(self, conn, sql):
        self._conn, self._sql = conn, sql

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):                       # COPY ... TO STDOUT
        return iter([b"bloque-1", b"bloque-2"])

    def write(self, datos):                   # COPY ... FROM STDIN
        self._conn.escrito.append((self._sql, datos))


class CursorFalso:
    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def copy(self, sql):
        self._conn.sql.append(sql)
        return CopiaFalsa(self._conn, sql)

    def executemany(self, sql, filas):
        self._conn.sql.append(sql)
        self._conn.filas_directorio = list(filas)


class ConexionFalsa:
    """Guarda el SQL que recibe. ``secuencias`` imita lo que responde information_schema."""

    def __init__(self, nombre, falla_en=None):
        self.nombre = nombre
        self.sql: list[str] = []
        self.escrito: list[tuple[str, bytes]] = []
        self.commits = self.rollbacks = 0
        self.filas_directorio: list[tuple] = []
        self._falla_en = falla_en

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if self._falla_en and self._falla_en in sql:
            import psycopg
            raise psycopg.errors.ForeignKeyViolation("falla simulada")
        if "information_schema.columns" in sql:
            return Resultado([("calificacion", "calificacion_id", "sigaf.calificacion_calificacion_id_seq", True),
                              ("rol", "rol_id", "sigaf.rol_rol_id_seq", False)])
        if "coalesce(max(" in sql:
            return Resultado([(7,)])
        if "FROM sigaf.centro_academico c" in sql:
            return Resultado([("CCB", 1, 260, 2600, 7800)])
        return Resultado(rowcount=4)

    def cursor(self):
        return CursorFalso(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1
