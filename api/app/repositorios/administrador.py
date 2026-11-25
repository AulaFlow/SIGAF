from __future__ import annotations

import psycopg

# Para saber en qué fragmento vive un grupo o un alumno (el admin no tiene centro).
# Regresan listas para poder usarse con BaseDistribuida.en_todos().
SQL_CENTRO_DEL_GRUPO = "SELECT centro_academico_id FROM grupo WHERE grupo_id = %s"

# alumno no tiene centro_academico_id: lo toma de su carrera (catálogo replicado).
SQL_CENTRO_DEL_ALUMNO = """
    SELECT c.centro_academico_id
    FROM alumno a JOIN carrera c ON c.carrera_id = a.carrera_id
    WHERE a.alumno_id = %s
"""

# SECURITY DEFINER (db/05): descifra nombre y apellidos con la llave de la sesión.
SQL_DATOS_ALUMNO = "SELECT alumno_id, matricula, nombre, apellidos FROM fn_datos_alumno(%s)"


class RepositorioAdministrador:
    def __init__(self, cur: psycopg.Cursor) -> None:
        self._cur = cur

    def centros_del_grupo(self, grupo_id: int) -> list[int]:
        self._cur.execute(SQL_CENTRO_DEL_GRUPO, (grupo_id,))
        return [f["centro_academico_id"] for f in self._cur.fetchall()]

    def centros_del_alumno(self, alumno_id: int) -> list[int]:
        self._cur.execute(SQL_CENTRO_DEL_ALUMNO, (alumno_id,))
        return [f["centro_academico_id"] for f in self._cur.fetchall()]

    def datos_alumno(self, alumno_id: int) -> dict | None:
        self._cur.execute(SQL_DATOS_ALUMNO, (alumno_id,))
        return self._cur.fetchone()
