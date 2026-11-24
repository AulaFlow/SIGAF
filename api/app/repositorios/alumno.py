from __future__ import annotations

import psycopg

SQL_MIS_DATOS = "SELECT alumno_id, nombre, apellidos FROM fn_mis_datos()"

SQL_BOLETA = """
    SELECT inscripcion_id, materia_clave, materia, parcial1, parcial2, parcial3,
           promedio_parciales, final
    FROM v_boleta
    WHERE alumno_id = %s
    ORDER BY materia
"""

# Pendiente = se puede entregar todavía (antes de fecha_limite + margen, db/07).
SQL_PENDIENTES = """
    SELECT tarea_id, titulo, materia, fecha_limite, cierre_entrega,
           extract(epoch FROM margen_tardia) / 3600 AS margen_tardia_horas,
           fecha_limite < now()                     AS solo_tardia
    FROM v_pendientes_alumno
    WHERE alumno_id = %s AND cierre_entrega > now()
    ORDER BY cierre_entrega
"""

SQL_SITUACION = """
    SELECT materias_aprobadas, materias_reprobadas, creditos_aprobados, promedio_general
    FROM v_situacion_academica
    WHERE alumno_id = %s
"""


class RepositorioAlumno:
    def __init__(self, cur: psycopg.Cursor) -> None:
        self._cur = cur

    def mis_datos(self) -> dict | None:
        # Sin parámetro: fn_mis_datos() usa sigaf.alumno_sesion de la transacción.
        self._cur.execute(SQL_MIS_DATOS)
        return self._cur.fetchone()

    def boleta(self, alumno_id: int) -> list[dict]:
        self._cur.execute(SQL_BOLETA, (alumno_id,))
        return self._cur.fetchall()

    def pendientes(self, alumno_id: int) -> list[dict]:
        self._cur.execute(SQL_PENDIENTES, (alumno_id,))
        return self._cur.fetchall()

    def situacion(self, alumno_id: int) -> dict | None:
        self._cur.execute(SQL_SITUACION, (alumno_id,))
        return self._cur.fetchone()
