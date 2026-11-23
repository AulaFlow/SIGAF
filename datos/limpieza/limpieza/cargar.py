"""Carga de los datos limpios a PostgreSQL con DB-API (psycopg).

Toda la carga va en UNA transacción: si algo falla, se hace rollback y la
base queda como estaba. La matrícula se guarda seudonimizada y el nombre
cifrado, con las funciones de la base (db/05_seguridad.sql).
"""

from __future__ import annotations

import os

import pandas as pd
import psycopg

from .excepciones import CargaError
from .limpiar import Reporte

VARIABLES_LLAVES = (("llave_datos", "SIGAF_LLAVE_DATOS"), ("llave_seudonimo", "SIGAF_LLAVE_SEUDONIMO"))


def llaves_de_entorno() -> dict[str, str]:
    """Lee las llaves de las variables de entorno (nunca del código)."""
    llaves = {nombre: os.environ.get(variable, "") for nombre, variable in VARIABLES_LLAVES}
    if any(len(v) < 32 for v in llaves.values()):
        raise CargaError("Faltan SIGAF_LLAVE_DATOS y SIGAF_LLAVE_SEUDONIMO (32+ caracteres cada una)")
    return llaves


def preparar_sesion(cur: psycopg.Cursor, llaves: dict[str, str]) -> None:
    cur.execute("SET search_path TO sigaf, public")
    for nombre, valor in llaves.items():
        cur.execute("SELECT set_config(%s, %s, false)", (f"sigaf.{nombre}", valor))


def cargar_alumnos(cur: psycopg.Cursor, df: pd.DataFrame, rep: Reporte) -> int:
    """Da de alta (o actualiza) alumnos. Devuelve cuántos se guardaron."""
    guardados = 0
    for fila, r in df.iterrows():
        cur.execute("SELECT carrera_id FROM carrera WHERE clave = %s", (r["carrera"],))
        carrera = cur.fetchone()
        if carrera is None:
            rep.descartar(fila, "la carrera no existe en la base")
            continue

        cur.execute("SELECT alumno_id FROM alumno WHERE matricula = fn_seudonimizar(%s)", (r["matricula"],))
        existente = cur.fetchone()
        if existente:
            alumno_id = existente[0]
            cur.execute("UPDATE alumno SET carrera_id = %s, semestre = %s WHERE alumno_id = %s",
                        (carrera[0], int(r["semestre"]), alumno_id))
        else:
            # Cuenta nueva con una contraseña aleatoria que nadie conoce (hash
            # bcrypt): el alumno la activa después con "recuperar contraseña".
            cur.execute(
                """INSERT INTO usuario (correo, hash_contrasena, rol_id)
                   SELECT 'alumno_' || left(fn_seudonimizar(%s), 12) || '@sigaf.test',
                          crypt(gen_random_uuid()::text, gen_salt('bf')), rol_id
                   FROM rol WHERE nombre = 'alumno'
                   RETURNING usuario_id""",
                (r["matricula"],),
            )
            usuario_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO alumno (usuario_id, carrera_id, matricula, semestre)
                   VALUES (%s, %s, fn_seudonimizar(%s), %s) RETURNING alumno_id""",
                (usuario_id, carrera[0], r["matricula"], int(r["semestre"])),
            )
            alumno_id = cur.fetchone()[0]
        cur.execute("CALL sp_guardar_datos_personales(%s, %s, %s)", (alumno_id, r["nombre"], r["apellidos"]))
        guardados += 1
    return guardados


def cargar_calificaciones(cur: psycopg.Cursor, df: pd.DataFrame, rep: Reporte) -> int:
    """Registra o corrige calificaciones. Las finales quedan sin validar."""
    guardadas = 0
    for fila, r in df.iterrows():
        cur.execute(
            """SELECT i.inscripcion_id
               FROM inscripcion i
               JOIN alumno a  ON a.alumno_id = i.alumno_id
               JOIN grupo g   ON g.grupo_id = i.grupo_id
               JOIN materia m ON m.materia_id = g.materia_id
               JOIN periodo p ON p.periodo_id = g.periodo_id
               WHERE a.matricula = fn_seudonimizar(%s) AND m.clave = %s AND p.clave = %s
                 AND i.estado = 'activa'""",
            (r["matricula"], r["materia"], r["periodo"]),
        )
        inscripcion = cur.fetchone()
        if inscripcion is None:
            rep.descartar(fila, "el alumno no está inscrito en esa materia y periodo")
            continue
        # Los triggers recalculan el promedio y dejan rastro en la bitácora.
        cur.execute(
            """INSERT INTO calificacion (inscripcion_id, tipo, valor)
               VALUES (%s, %s, %s)
               ON CONFLICT (inscripcion_id, tipo) DO UPDATE SET valor = EXCLUDED.valor""",
            (inscripcion[0], r["tipo"], float(r["valor"])),
        )
        guardadas += 1
    return guardadas


def cargar(dsn: str, alumnos: tuple[pd.DataFrame, Reporte] | None,
           calificaciones: tuple[pd.DataFrame, Reporte] | None) -> dict[str, int]:
    """Carga todo en una sola transacción: COMMIT si todo sale bien, ROLLBACK si no."""
    llaves = llaves_de_entorno()
    resultado = {"alumnos": 0, "calificaciones": 0}
    conn = psycopg.connect(dsn, autocommit=False)
    try:
        with conn.cursor() as cur:
            preparar_sesion(cur, llaves)
            if alumnos is not None:
                resultado["alumnos"] = cargar_alumnos(cur, *alumnos)
            if calificaciones is not None:
                resultado["calificaciones"] = cargar_calificaciones(cur, *calificaciones)
        conn.commit()
    except psycopg.Error as e:
        conn.rollback()
        raise CargaError(f"Error de base de datos; se hizo rollback: {e}") from e
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return resultado
