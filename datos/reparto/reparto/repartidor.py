"""Reparte los datos entre los fragmentos A y B (issue #8).

Punto de partida: el fragmento A tiene los 6 centros (lo llenó el generador)
y el fragmento B está vacío. Al terminar:

    A = centros 1, 3, 5 + catálogos      B = centros 2, 4, 6 + catálogos

Pasos (cada uno en su transacción; si algo falla se hace rollback):
    1. Cuenta lo que hay en A (para comparar al final).
    2. Vacía B y le COPIA los catálogos y las filas de sus centros.
    3. BORRA de A las filas que ya viven en B.
    4. Llena ``directorio_fragmento`` en los dos (lo lee el enrutador de la API).
    5. Ajusta los contadores de id para que A y B nunca repitan un id.
    6. Verifica: lo que había en A = lo que quedó en A + lo que pasó a B.

Se conecta con la cuenta ``sigaf_dba`` (rol sigaf_admin) por TLS. Los nombres
de tabla salen de plan.py (constantes) y los centros son enteros, así que el
SQL armado aquí no lleva nada que escriba un usuario.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import psycopg

from . import plan
from .plan import Regla

log = logging.getLogger(__name__)


class RepartoError(Exception):
    """El reparto no se pudo hacer o la verificación no cuadró."""


@dataclass(frozen=True)
class Nodos:
    """Dónde atiende cada fragmento (lo que va en directorio_fragmento)."""

    primario: str
    replica: str


@dataclass(frozen=True)
class Conteo:
    """Una fila del reporte final."""

    tabla: str
    replicada: bool
    antes_en_a: int      # filas de centros B que había en A (o total, si es replicada)
    quedan_en_a: int     # filas de centros B que siguen en A (debe ser 0; replicada: total)
    en_b: int            # filas que quedaron en B

    @property
    def cuadra(self) -> bool:
        if self.replicada:
            return self.antes_en_a == self.quedan_en_a == self.en_b
        return self.quedan_en_a == 0 and self.en_b == self.antes_en_a


def lista_centros(centros: Iterable[int]) -> str:
    """(2, 4, 6) -> 'ARRAY[2,4,6]::smallint[]'. int() garantiza que solo hay números."""
    return "ARRAY[" + ",".join(str(int(c)) for c in centros) + "]::smallint[]"


def _contar(conn: psycopg.Connection, regla: Regla, centros: str) -> int:
    sql = f"SELECT count(*) FROM sigaf.{regla.tabla}{regla.where(centros)}"  # nosec B608
    return conn.execute(sql).fetchone()[0]


class Repartidor:
    """Mueve los centros de ``centros_b`` desde el fragmento A al B."""

    def __init__(self, conn_a: psycopg.Connection, conn_b: psycopg.Connection,
                 nodos: dict[str, Nodos], centros_a: tuple[int, ...] = plan.CENTROS_A,
                 centros_b: tuple[int, ...] = plan.CENTROS_B,
                 avisar: Callable[[str], None] = print) -> None:
        self._a = conn_a
        self._b = conn_b
        self._nodos = nodos
        self._centros_a = centros_a
        self._centros_b = centros_b
        self._c = lista_centros(centros_b)
        self._avisar = avisar

    # -- pasos ---------------------------------------------------------------
    def contar_en_a(self) -> dict[Regla, int]:
        return {r: _contar(self._a, r, self._c) for r in plan.ORDEN_COPIA}

    def copiar_a_b(self) -> None:
        for regla in plan.ORDEN_COPIA:
            if regla.tabla == "bitacora_calificacion":
                # Al copiar calificaciones, el trigger de bitácora de B escribió
                # filas nuevas. Se quitan para dejar solo la bitácora original.
                self._b.execute("DELETE FROM sigaf.bitacora_calificacion")
            origen = f"COPY (SELECT * FROM sigaf.{regla.tabla}{regla.where(self._c)}) TO STDOUT (FORMAT BINARY)"  # nosec B608
            destino = f"COPY sigaf.{regla.tabla} FROM STDIN (FORMAT BINARY)"
            with self._a.cursor() as ca, self._b.cursor() as cb, \
                    ca.copy(origen) as leer, cb.copy(destino) as escribir:
                for bloque in leer:          # se pasa por bloques, sin cargar todo en memoria
                    escribir.write(bloque)
            self._avisar(f"  copiado  {regla.tabla}{' (replicada)' if regla.replicada else ''}")

    def borrar_de_a(self) -> None:
        for regla in plan.ORDEN_BORRADO:
            sql = f"DELETE FROM sigaf.{regla.tabla}{regla.where(self._c)}"  # nosec B608
            n = self._a.execute(sql).rowcount
            self._avisar(f"  borrado  {regla.tabla}: {n}")

    def llenar_directorio(self, conn: psycopg.Connection) -> None:
        filas = [(c, f, self._nodos[f].primario, self._nodos[f].replica)
                 for f, centros in (("A", self._centros_a), ("B", self._centros_b)) for c in centros]
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO sigaf.directorio_fragmento "
                "(centro_academico_id, fragmento, host_primario, host_replica) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (centro_academico_id) DO UPDATE SET fragmento = EXCLUDED.fragmento, "
                "host_primario = EXCLUDED.host_primario, host_replica = EXCLUDED.host_replica, "
                "actualizado_en = now()",
                filas,
            )

    def ajustar_ids(self, maximos_a: dict[str, int]) -> None:
        """A sigue desde su máximo; B arranca en INICIO_IDS_B en las tablas BIGINT.

        Los catálogos pequeños (SMALLINT/INT) siguen el mismo número en los dos."""
        for tabla, columna, secuencia, es_bigint in _secuencias(self._a):
            maximo = maximos_a.get(tabla, 0)
            self._a.execute("SELECT setval(%s, %s, %s)", (secuencia, max(maximo, 1), maximo > 0))
            if es_bigint:
                en_b = self._b.execute(f"SELECT coalesce(max({columna}), 0) FROM sigaf.{tabla}").fetchone()[0]  # nosec B608
                self._b.execute("SELECT setval(%s, %s)", (secuencia, max(en_b, plan.INICIO_IDS_B)))
            else:
                self._b.execute("SELECT setval(%s, %s, %s)", (secuencia, max(maximo, 1), maximo > 0))

    # -- todo junto ----------------------------------------------------------
    def repartir(self) -> list[Conteo]:
        antes = self.contar_en_a()
        if not any(n for r, n in antes.items() if not r.replicada):
            raise RepartoError(
                "El fragmento A no tiene datos de los centros de B. "
                "Corre primero el generador (python -m reparto generar) o ya se había repartido.")
        maximos = {t: m for t, m in _maximos(self._a)}

        self._avisar("== Copiando a B")
        try:
            vaciar(self._b)
            self.copiar_a_b()
            self.llenar_directorio(self._b)
            self._b.commit()
        except Exception:
            self._b.rollback()
            raise

        self._avisar("== Borrando de A lo que ya está en B")
        try:
            self.borrar_de_a()
            self.llenar_directorio(self._a)
            self._a.commit()
        except psycopg.Error as e:
            self._a.rollback()
            raise RepartoError(f"Se copió a B pero no se pudo borrar de A ({e}). Vuelve a generar y repartir.") from e

        self.ajustar_ids(maximos)
        self._a.commit()
        self._b.commit()
        return self.verificar(antes)

    def verificar(self, antes: dict[Regla, int]) -> list[Conteo]:
        reporte = [Conteo(r.nombre, r.replicada, n, _contar(self._a, r, self._c), _contar(self._b, r, self._c))
                   for r, n in antes.items()]
        self._a.rollback()   # solo se leyó
        self._b.rollback()
        malas = [c.tabla for c in reporte if not c.cuadra]
        if malas:
            raise RepartoError(f"No cuadran los conteos de: {', '.join(malas)}")
        return reporte


_SQL_SECUENCIAS = """
SELECT c.table_name, c.column_name, pg_get_serial_sequence('sigaf.' || c.table_name, c.column_name),
       c.data_type = 'bigint'
FROM information_schema.columns c
WHERE c.table_schema = 'sigaf' AND c.column_default LIKE 'nextval(%'
ORDER BY c.table_name
"""


def _secuencias(conn: psycopg.Connection) -> list[tuple[str, str, str, bool]]:
    """(tabla, columna id, secuencia, es BIGINT) de cada tabla con id automático."""
    return [f for f in conn.execute(_SQL_SECUENCIAS).fetchall() if f[0] in plan.tablas_cubiertas()]


def _maximos(conn: psycopg.Connection) -> list[tuple[str, int]]:
    return [(t, conn.execute(f"SELECT coalesce(max({col}), 0) FROM sigaf.{t}").fetchone()[0])  # nosec B608
            for t, col, _, _ in _secuencias(conn)]


def vaciar(conn: psycopg.Connection) -> None:
    """Deja un fragmento vacío y con los ids empezando en 1.

    Es lo que haría ``TRUNCATE ... RESTART IDENTITY``, pero eso exige ser dueño
    de las secuencias y sigaf_dba no lo es; setval sí le está permitido."""
    tablas = ", ".join(f"sigaf.{t}" for t in sorted(plan.tablas_cubiertas()))
    conn.execute(f"TRUNCATE {tablas} CASCADE")  # nosec B608
    for _, _, secuencia, _ in _secuencias(conn):
        conn.execute("SELECT setval(%s, 1, false)", (secuencia,))
    conn.commit()


SQL_POR_CENTRO = """
SELECT c.clave, c.centro_academico_id,
       (SELECT count(*) FROM sigaf.alumno a JOIN sigaf.carrera ca USING (carrera_id)
         WHERE ca.centro_academico_id = c.centro_academico_id),
       (SELECT count(*) FROM sigaf.inscripcion i WHERE i.centro_academico_id = c.centro_academico_id),
       (SELECT count(*) FROM sigaf.calificacion k WHERE k.centro_academico_id = c.centro_academico_id)
FROM sigaf.centro_academico c ORDER BY c.centro_academico_id
"""


def por_centro(conn: psycopg.Connection) -> list[tuple[str, int, int, int, int]]:
    """Alumnos, inscripciones y calificaciones de cada centro en un fragmento."""
    filas = conn.execute(SQL_POR_CENTRO).fetchall()
    conn.rollback()
    return filas
