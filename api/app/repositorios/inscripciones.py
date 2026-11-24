from __future__ import annotations

import psycopg

# El procedimiento valida cupo, carrera y duplicados (db/03) y bloquea el grupo.
SQL_INSCRIBIR = "CALL sp_inscribir_alumno(%s, %s, NULL)"


class RepositorioInscripciones:
    def __init__(self, cur: psycopg.Cursor) -> None:
        self._cur = cur

    def inscribir(self, alumno_id: int, grupo_id: int) -> int:
        self._cur.execute(SQL_INSCRIBIR, (alumno_id, grupo_id))
        return self._cur.fetchone()["p_inscripcion"]
