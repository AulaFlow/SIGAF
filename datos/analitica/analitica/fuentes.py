"""Lectura de los fragmentos de PostgreSQL con DB-API (psycopg).

Se conecta con la cuenta ``sigaf_etl``, que SOLO puede leer datos
académicos: no ve usuarios, datos personales ni mensajes (db/05_seguridad.sql).
"""

from __future__ import annotations

from collections.abc import Iterator
from types import TracebackType
from typing import Protocol, Self

import psycopg

from .modelos import ActividadAlumno, RegistroCalificacion, ResumenGrupo

TAM_LOTE = 1000

SQL_RESUMEN = """
SELECT g.grupo_id, p.clave, g.centro_academico_id, m.clave, m.nombre,
       count(i.inscripcion_id),
       round(avg(i.promedio_parciales), 2),
       round(100.0 * count(*) FILTER (WHERE i.promedio_parciales >= 6)
             / nullif(count(i.promedio_parciales), 0), 1),
       (SELECT round(100.0 * count(*) FILTER (WHERE s.estado <> 'falta') / nullif(count(*), 0), 1)
          FROM sigaf.asistencia s JOIN sigaf.inscripcion i2 USING (inscripcion_id)
         WHERE i2.grupo_id = g.grupo_id)
FROM sigaf.grupo g
JOIN sigaf.materia m ON m.materia_id = g.materia_id
JOIN sigaf.periodo p ON p.periodo_id = g.periodo_id
LEFT JOIN sigaf.inscripcion i ON i.grupo_id = g.grupo_id AND i.estado = 'activa'
GROUP BY g.grupo_id, p.clave, g.centro_academico_id, m.clave, m.nombre
"""

SQL_ACTIVIDAD = """
SELECT i.alumno_id, p.clave, i.centro_academico_id, ca.clave,
       count(e.entrega_id) FILTER (WHERE e.estado = 'a_tiempo'),
       count(e.entrega_id) FILTER (WHERE e.estado = 'tardia'),
       count(t.tarea_id)   FILTER (WHERE e.entrega_id IS NULL AND t.fecha_limite + t.margen_tardia < now()),
       (SELECT count(*) FROM sigaf.asistencia s
          JOIN sigaf.inscripcion i3 USING (inscripcion_id)
          JOIN sigaf.grupo g3 ON g3.grupo_id = i3.grupo_id
         WHERE i3.alumno_id = i.alumno_id AND g3.periodo_id = p.periodo_id AND s.estado = 'falta')
FROM sigaf.inscripcion i
JOIN sigaf.grupo g   ON g.grupo_id = i.grupo_id
JOIN sigaf.periodo p ON p.periodo_id = g.periodo_id
JOIN sigaf.centro_academico ca ON ca.centro_academico_id = i.centro_academico_id
LEFT JOIN sigaf.tarea t   ON t.grupo_id = g.grupo_id
LEFT JOIN sigaf.entrega e ON e.tarea_id = t.tarea_id AND e.inscripcion_id = i.inscripcion_id
WHERE i.estado = 'activa'
GROUP BY i.alumno_id, p.clave, p.periodo_id, i.centro_academico_id, ca.clave
"""

SQL_CALIFICACIONES = """
SELECT c.calificacion_id, i.alumno_id, p.clave, c.centro_academico_id, m.clave, c.tipo, c.valor
FROM sigaf.calificacion c
JOIN sigaf.inscripcion i ON i.inscripcion_id = c.inscripcion_id
JOIN sigaf.grupo g       ON g.grupo_id = i.grupo_id
JOIN sigaf.materia m     ON m.materia_id = g.materia_id
JOIN sigaf.periodo p     ON p.periodo_id = g.periodo_id
"""


def _num(valor: object) -> float | None:
    return None if valor is None else float(valor)  # Decimal -> float para MongoDB


class FuenteAcademica(Protocol):
    """Lo que el ETL necesita de una fuente (permite usar fuentes falsas en pruebas)."""

    nombre: str

    def resumen_grupos(self) -> Iterator[ResumenGrupo]: ...
    def actividad_alumnos(self) -> Iterator[ActividadAlumno]: ...
    def calificaciones(self) -> Iterator[RegistroCalificacion]: ...


class FuentePostgres:
    """Un fragmento de PostgreSQL. Se usa como administrador de contexto:

        with FuentePostgres("A", dsn) as fuente:
            for resumen in fuente.resumen_grupos(): ...
    """

    def __init__(self, nombre: str, dsn: str) -> None:
        self.nombre = nombre
        self._dsn = dsn
        self._conn: psycopg.Connection | None = None

    def __enter__(self) -> Self:
        # Solo lectura: aunque la cuenta tuviera permisos de más, aquí no se escribe.
        self._conn = psycopg.connect(self._dsn, autocommit=False)
        self._conn.read_only = True
        return self

    def __exit__(self, tipo: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        if self._conn is not None:
            self._conn.rollback()   # no hay nada que confirmar: es solo lectura
            self._conn.close()
            self._conn = None

    def _filas(self, sql: str) -> Iterator[tuple]:
        if self._conn is None:
            raise RuntimeError("Usa la fuente dentro de un bloque with")
        # Cursor con nombre: el servidor manda las filas por lotes, no todas de golpe
        with self._conn.cursor(name=f"etl_{id(sql)}") as cur:
            cur.itersize = TAM_LOTE
            cur.execute(sql)
            yield from cur

    def resumen_grupos(self) -> Iterator[ResumenGrupo]:
        for f in self._filas(SQL_RESUMEN):
            yield ResumenGrupo(f[0], f[1], f[2], f[3], f[4], f[5], _num(f[6]), _num(f[7]), _num(f[8]))

    def actividad_alumnos(self) -> Iterator[ActividadAlumno]:
        for f in self._filas(SQL_ACTIVIDAD):
            yield ActividadAlumno(f[0], f[1], f[2], f[3], f[4], f[5], f[6], f[7])

    def calificaciones(self) -> Iterator[RegistroCalificacion]:
        for f in self._filas(SQL_CALIFICACIONES):
            yield RegistroCalificacion(f[0], f[1], f[2], f[3], f[4], f[5], float(f[6]))
