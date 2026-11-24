from __future__ import annotations

from typing import TYPE_CHECKING

import psycopg

if TYPE_CHECKING:
    from ..esquemas.tareas import TareaNueva

SQL_GRUPO_ES_DEL_PROFESOR = "SELECT 1 FROM grupo WHERE grupo_id = %s AND profesor_id = %s"

SQL_GRUPOS = """
    SELECT g.grupo_id, g.clave, m.clave AS materia_clave, m.nombre AS materia,
           p.clave AS periodo, g.cupo,
           count(i.inscripcion_id) FILTER (WHERE i.estado = 'activa') AS inscritos
    FROM grupo g
    JOIN materia m ON m.materia_id = g.materia_id
    JOIN periodo p ON p.periodo_id = g.periodo_id
    LEFT JOIN inscripcion i ON i.grupo_id = g.grupo_id
    WHERE g.profesor_id = %s
    GROUP BY g.grupo_id, m.clave, m.nombre, p.clave, p.fecha_inicio
    ORDER BY p.fecha_inicio DESC, m.nombre, g.clave
"""

# Nombres descifrados SOLO por la función autorizada (db/05), con el profesor del token.
SQL_ALUMNOS_DE_GRUPO = """
    SELECT alumno_id, nombre, apellidos
    FROM fn_alumnos_de_profesor(%s)
    WHERE grupo_id = %s
    ORDER BY apellidos, nombre
"""

# Sin margen: la base pone su DEFAULT (48 h). Con margen: make_interval(hours => %s).
# Son dos textos SQL fijos (no se arma SQL concatenando).
SQL_CREAR_TAREA = """
    INSERT INTO tarea (grupo_id, titulo, descripcion, fecha_limite)
    VALUES (%s, %s, %s, %s)
    RETURNING tarea_id, grupo_id, titulo, descripcion, fecha_limite,
              extract(epoch FROM margen_tardia) / 3600 AS margen_tardia_horas,
              fecha_limite + margen_tardia             AS cierre_entrega
"""
SQL_CREAR_TAREA_CON_MARGEN = """
    INSERT INTO tarea (grupo_id, titulo, descripcion, fecha_limite, margen_tardia)
    VALUES (%s, %s, %s, %s, make_interval(hours => %s))
    RETURNING tarea_id, grupo_id, titulo, descripcion, fecha_limite,
              extract(epoch FROM margen_tardia) / 3600 AS margen_tardia_horas,
              fecha_limite + margen_tardia             AS cierre_entrega
"""

# Solo si la entrega es de una tarea de un grupo del profesor.
# (UPDATE de calificación no dispara trg_estado_entrega: ese es solo OF entregada_en.)
SQL_CALIFICAR_ENTREGA = """
    UPDATE entrega e
       SET calificacion = %s, retroalimentacion = %s
      FROM tarea t
      JOIN grupo g ON g.grupo_id = t.grupo_id
     WHERE e.entrega_id = %s AND t.tarea_id = e.tarea_id AND g.profesor_id = %s
    RETURNING e.entrega_id, e.calificacion, e.retroalimentacion
"""

# Solo si la inscripción está activa y es de un grupo del profesor.
SQL_REGISTRAR_CALIFICACION = """
    INSERT INTO calificacion (inscripcion_id, tipo, valor)
    SELECT i.inscripcion_id, %s, %s
    FROM inscripcion i
    JOIN grupo g ON g.grupo_id = i.grupo_id
    WHERE i.inscripcion_id = %s AND i.estado = 'activa' AND g.profesor_id = %s
    RETURNING calificacion_id, inscripcion_id, tipo, valor, validada
"""


class RepositorioProfesor:
    def __init__(self, cur: psycopg.Cursor) -> None:
        self._cur = cur

    def grupo_es_suyo(self, grupo_id: int, profesor_id: int) -> bool:
        self._cur.execute(SQL_GRUPO_ES_DEL_PROFESOR, (grupo_id, profesor_id))
        return self._cur.fetchone() is not None

    def grupos(self, profesor_id: int) -> list[dict]:
        self._cur.execute(SQL_GRUPOS, (profesor_id,))
        return self._cur.fetchall()

    def alumnos_de_grupo(self, profesor_id: int, grupo_id: int) -> list[dict]:
        self._cur.execute(SQL_ALUMNOS_DE_GRUPO, (profesor_id, grupo_id))
        return self._cur.fetchall()

    def crear_tarea(self, grupo_id: int, datos: TareaNueva) -> dict:
        base = (grupo_id, datos.titulo, datos.descripcion, datos.fecha_limite)
        if datos.margen_tardia_horas is None:
            self._cur.execute(SQL_CREAR_TAREA, base)
        else:
            self._cur.execute(SQL_CREAR_TAREA_CON_MARGEN, (*base, datos.margen_tardia_horas))
        return self._cur.fetchone()

    def calificar_entrega(self, profesor_id: int, entrega_id: int, calificacion: object,
                          retroalimentacion: str | None) -> dict | None:
        self._cur.execute(
            SQL_CALIFICAR_ENTREGA, (calificacion, retroalimentacion, entrega_id, profesor_id)
        )
        return self._cur.fetchone()

    def registrar_calificacion(self, profesor_id: int, inscripcion_id: int, tipo: str,
                               valor: object) -> dict | None:
        self._cur.execute(SQL_REGISTRAR_CALIFICACION, (tipo, valor, inscripcion_id, profesor_id))
        return self._cur.fetchone()
