from __future__ import annotations

from typing import TYPE_CHECKING

import psycopg

if TYPE_CHECKING:
    from ..esquemas.entregas import EntregaNueva

# La inscripción ACTIVA del alumno en el grupo de esa tarea.
SQL_INSCRIPCION_PARA_TAREA = """
    SELECT i.inscripcion_id
    FROM inscripcion i
    JOIN tarea t ON t.grupo_id = i.grupo_id
    WHERE t.tarea_id = %s AND i.alumno_id = %s AND i.estado = 'activa'
"""

# entregada_en NO va: la base pone now() y el trigger decide a_tiempo / tardia /
# rechazo SG001. centro_academico_id tampoco: lo hereda otro trigger.
SQL_REGISTRAR_ENTREGA = """
    INSERT INTO entrega (tarea_id, inscripcion_id, archivo_ruta, archivo_tamano_bytes, archivo_tipo)
    VALUES (%s, %s, %s, %s, %s)
    RETURNING entrega_id, tarea_id, entregada_en, estado
"""


class RepositorioEntregas:
    def __init__(self, cur: psycopg.Cursor) -> None:
        self._cur = cur

    def inscripcion_para_tarea(self, tarea_id: int, alumno_id: int) -> int | None:
        self._cur.execute(SQL_INSCRIPCION_PARA_TAREA, (tarea_id, alumno_id))
        fila = self._cur.fetchone()
        return None if fila is None else fila["inscripcion_id"]

    def registrar(self, tarea_id: int, inscripcion_id: int, datos: EntregaNueva) -> dict:
        self._cur.execute(
            SQL_REGISTRAR_ENTREGA,
            (tarea_id, inscripcion_id, datos.archivo_ruta, datos.archivo_tamano_bytes,
             datos.archivo_tipo),
        )
        return self._cur.fetchone()
