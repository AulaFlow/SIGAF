"""Consultas del inicio de sesión (issue #11).

Dónde vive cada cosa (datos/reparto/README.md):
    usuario, rol, carrera  -> replicadas: están completas en cualquier fragmento
    alumno, profesor       -> fragmentadas: solo en el fragmento de su centro

Por eso el login va en dos tiempos:
    1. por_correo() en cualquier fragmento: quién es, su hash y su rol.
    2. alumno_de() / profesor_de() con en_todos(): su id y su centro, vivan en A o en B.
       Regresan listas porque en los fragmentos donde no vive regresan [].
"""

from __future__ import annotations

import psycopg

# Igualdad exacta: usa el índice UNIQUE de usuario.correo.
SQL_USUARIO_POR_CORREO = """
    SELECT u.usuario_id, u.correo, u.hash_contrasena, u.activo, r.nombre AS rol
    FROM usuario u
    JOIN rol r ON r.rol_id = u.rol_id
    WHERE u.correo = %s
"""

# alumno no tiene centro_academico_id: lo toma de su carrera (catálogo replicado).
SQL_ALUMNO_DE_USUARIO = """
    SELECT a.alumno_id, c.centro_academico_id
    FROM alumno a
    JOIN carrera c ON c.carrera_id = a.carrera_id
    WHERE a.usuario_id = %s
"""

SQL_PROFESOR_DE_USUARIO = """
    SELECT p.profesor_id, p.centro_academico_id
    FROM profesor p
    WHERE p.usuario_id = %s
"""

# sigaf_api solo tiene INSERT en esta tabla (db/08): nada de RETURNING, que pide SELECT.
SQL_REGISTRAR_ACCESO = """
    INSERT INTO bitacora_acceso (usuario_id, exito, motivo, ip)
    VALUES (%s, %s, %s, %s)
"""


class RepositorioUsuarios:
    def __init__(self, cur: psycopg.Cursor) -> None:
        self._cur = cur

    def por_correo(self, correo: str) -> dict | None:
        self._cur.execute(SQL_USUARIO_POR_CORREO, (correo,))
        return self._cur.fetchone()

    def alumno_de(self, usuario_id: int) -> list[dict]:
        self._cur.execute(SQL_ALUMNO_DE_USUARIO, (usuario_id,))
        return self._cur.fetchall()

    def profesor_de(self, usuario_id: int) -> list[dict]:
        self._cur.execute(SQL_PROFESOR_DE_USUARIO, (usuario_id,))
        return self._cur.fetchall()

    def registrar_acceso(self, usuario_id: int | None, exito: bool, motivo: str,
                         ip: str | None) -> None:
        self._cur.execute(SQL_REGISTRAR_ACCESO, (usuario_id, exito, motivo, ip))
