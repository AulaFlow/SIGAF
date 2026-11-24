"""Generador de datos sintéticos para SIGAF (issue #10).

Llena el esquema ``sigaf`` con datos FICTICIOS del orden de cien mil
registros, para que la fragmentación, la replicación y el monitoreo se
puedan observar con carga real. Ningún dato corresponde a personas reales:
nombres generados con Faker y matrículas aleatorias (seudónimos).

Uso (contraseña y llaves en variables de entorno, nunca en el código):
    export PGPASSWORD=dev
    export SIGAF_LLAVE_DATOS=...        # 32+ caracteres, cifra nombre y apellidos
    export SIGAF_LLAVE_SEUDONIMO=...    # 32+ caracteres, seudonimiza matrículas
    python generar_datos.py --limpiar

Las matrículas se guardan seudonimizadas (HMAC) y los nombres cifrados,
con las mismas funciones de la base (db/05_seguridad.sql).

El script NO llena ``directorio_fragmento``: qué centro va a cada fragmento
es una decisión del equipo. Al final imprime el conteo por centro para
tomar esa decisión con datos.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import psycopg
from faker import Faker
from psycopg import sql

# Centros académicos y su peso relativo en número de alumnos (estimación
# sintética; se puede cambiar con --pesos).
CENTROS: list[tuple[str, str]] = [
    ("CCB", "Centro de Ciencias Básicas"),
    ("CCEA", "Centro de Ciencias Económicas y Administrativas"),
    ("CCA", "Centro de Ciencias Agropecuarias"),
    ("CCS", "Centro de Ciencias de la Salud"),
    ("CCSH", "Centro de Ciencias Sociales y Humanidades"),
    ("CCDC", "Centro de Ciencias del Diseño y de la Construcción"),
]
PESOS_DEFAULT = [0.26, 0.22, 0.08, 0.18, 0.15, 0.11]

CARRERAS_POR_CENTRO = 3
MATERIAS_POR_CARRERA = 12
MATERIAS_POR_ALUMNO = 5
CUPO_GRUPO = 40
TAREAS_POR_GRUPO = 6
DIAS_ASISTENCIA = 4

TABLAS = [
    "notificacion", "mensaje", "participante_conversacion", "conversacion",
    "aviso", "asistencia", "bitacora_calificacion", "calificacion",
    "respuesta", "intento_examen", "opcion", "pregunta", "examen",
    "entrega", "tarea", "inscripcion", "horario", "grupo", "profesor",
    "alumno_datos_personales", "alumno", "materia", "periodo", "carrera", "directorio_fragmento",
    "centro_academico", "usuario", "rol",
]

UTC = timezone.utc


class GeneradorError(Exception):
    """Error al generar o insertar los datos sintéticos."""


@dataclass
class Contexto:
    """Ids generados que se reutilizan entre pasos."""

    centros: list[int] = field(default_factory=list)
    carreras: dict[int, int] = field(default_factory=dict)          # carrera -> centro
    materias: dict[int, list[int]] = field(default_factory=dict)    # carrera -> materias
    profesores: dict[int, list[int]] = field(default_factory=dict)  # centro -> profesores
    profesor_usuario: dict[int, int] = field(default_factory=dict)
    alumnos: list[tuple[int, int, int]] = field(default_factory=list)  # alumno, usuario, carrera
    periodos: dict[str, int] = field(default_factory=dict)
    grupos: dict[int, list[int]] = field(default_factory=dict)      # periodo -> grupos


def hash_sintetico(texto: str) -> str:
    """Hash de relleno: las cuentas sintéticas no tienen contraseña real."""
    return "sintetico$" + hashlib.sha256(texto.encode()).hexdigest()


def matricula_unica(rng: random.Random, usadas: set[str]) -> str:
    """Matrícula seudónima de 7 dígitos que no se repite."""
    while True:
        m = f"S{rng.randint(0, 9_999_999):07d}"
        if m not in usadas:
            usadas.add(m)
            return m


def insertar_devolviendo(cur: psycopg.Cursor, sql: str, filas: list[tuple]) -> list[int]:
    """Inserta varias filas y devuelve sus ids en el mismo orden."""
    ids: list[int] = []
    for fila in filas:
        cur.execute(sql, fila)
        ids.append(cur.fetchone()[0])
    return ids


def limpiar(cur: psycopg.Cursor) -> None:
    """Vacía todas las tablas y reinicia los contadores de id."""
    cur.execute(
        "TRUNCATE " + ", ".join(f"sigaf.{t}" for t in TABLAS) + " RESTART IDENTITY CASCADE"
    )


def catalogos(cur: psycopg.Cursor, ctx: Contexto, rng: random.Random) -> None:
    """Roles, centros, carreras, periodos y materias."""
    cur.executemany("INSERT INTO rol (nombre) VALUES (%s)",
                    [("alumno",), ("profesor",), ("administrador",)])
    ctx.centros = insertar_devolviendo(
        cur,
        "INSERT INTO centro_academico (clave, nombre) VALUES (%s, %s) RETURNING centro_academico_id",
        CENTROS,
    )
    for centro_id, (clave_centro, _) in zip(ctx.centros, CENTROS):
        for n in range(1, CARRERAS_POR_CENTRO + 1):
            cur.execute(
                "INSERT INTO carrera (centro_academico_id, clave, nombre) "
                "VALUES (%s, %s, %s) RETURNING carrera_id",
                (centro_id, f"{clave_centro}-{n}", f"Carrera {n} de {clave_centro}"),
            )
            ctx.carreras[cur.fetchone()[0]] = centro_id

    for clave, ini, fin in [("2026-ENE-JUN", date(2026, 1, 12), date(2026, 6, 19)),
                            ("2026-AGO-DIC", date(2026, 8, 10), date(2026, 12, 18))]:
        cur.execute(
            "INSERT INTO periodo (clave, fecha_inicio, fecha_fin) VALUES (%s, %s, %s) RETURNING periodo_id",
            (clave, ini, fin),
        )
        ctx.periodos[clave] = cur.fetchone()[0]

    for carrera_id in ctx.carreras:
        filas = [
            (carrera_id, f"M{carrera_id:02d}-{n:02d}",
             f"Materia {n} de {carrera_id:02d}", rng.choice([6, 8, 10]), (n - 1) // 2 + 1)
            for n in range(1, MATERIAS_POR_CARRERA + 1)
        ]
        ctx.materias[carrera_id] = insertar_devolviendo(
            cur,
            "INSERT INTO materia (carrera_id, clave, nombre, creditos, semestre_sugerido) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING materia_id",
            filas,
        )


def personas(cur: psycopg.Cursor, ctx: Contexto, fake: Faker, rng: random.Random,
             n_alumnos: int, pesos: list[float]) -> None:
    """Administrador, profesores (por centro) y alumnos (por carrera)."""
    cur.execute(
        "INSERT INTO usuario (correo, hash_contrasena, rol_id) VALUES (%s, %s, 3)",
        ("admin@sigaf.test", hash_sintetico("admin")),
    )
    usadas: set[str] = set()
    carreras_por_centro: dict[int, list[int]] = defaultdict(list)
    for carrera_id, centro_id in ctx.carreras.items():
        carreras_por_centro[centro_id].append(carrera_id)

    for centro_id, peso in zip(ctx.centros, pesos):
        alumnos_centro = round(n_alumnos * peso)
        n_prof = max(8, alumnos_centro // 15)
        ctx.profesores[centro_id] = []
        for k in range(n_prof):
            correo = f"prof{centro_id}_{k}@sigaf.test"
            cur.execute(
                "INSERT INTO usuario (correo, hash_contrasena, rol_id) VALUES (%s, %s, 2) RETURNING usuario_id",
                (correo, hash_sintetico(correo)),
            )
            usuario_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO profesor (usuario_id, centro_academico_id, num_empleado, nombre, apellidos) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING profesor_id",
                (usuario_id, centro_id, f"E{centro_id}{k:04d}", fake.first_name(),
                 f"{fake.last_name()} {fake.last_name()}"),
            )
            profesor_id = cur.fetchone()[0]
            ctx.profesores[centro_id].append(profesor_id)
            ctx.profesor_usuario[profesor_id] = usuario_id

        for _ in range(alumnos_centro):
            carrera_id = rng.choice(carreras_por_centro[centro_id])
            matricula = matricula_unica(rng, usadas)
            correo = f"alumno{len(usadas):05d}@sigaf.test"   # sin la matrícula: no se filtra
            cur.execute(
                "INSERT INTO usuario (correo, hash_contrasena, rol_id) VALUES (%s, %s, 1) RETURNING usuario_id",
                (correo, hash_sintetico(correo)),
            )
            usuario_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO alumno (usuario_id, carrera_id, matricula, semestre) "
                "VALUES (%s, %s, fn_seudonimizar(%s), %s) RETURNING alumno_id",
                (usuario_id, carrera_id, matricula, rng.randint(1, 9)),
            )
            alumno_id = cur.fetchone()[0]
            # Fragmentación vertical + cifrado: el procedimiento los guarda cifrados
            cur.execute(
                "CALL sp_guardar_datos_personales(%s, %s, %s)",
                (alumno_id, fake.first_name(), f"{fake.last_name()} {fake.last_name()}"),
            )
            ctx.alumnos.append((alumno_id, usuario_id, carrera_id))


def grupos_e_inscripciones(cur: psycopg.Cursor, ctx: Contexto, rng: random.Random) -> None:
    """Cada alumno lleva MATERIAS_POR_ALUMNO materias de su carrera por periodo,
    sin repetir en el periodo actual las que ya cursó en el anterior."""
    cursadas: dict[int, set[int]] = defaultdict(set)        # alumno -> materias
    for periodo_id in ctx.periodos.values():                 # en orden: pasado, actual
        demanda: dict[int, list[int]] = defaultdict(list)   # materia -> alumnos
        for alumno_id, _, carrera_id in ctx.alumnos:
            disponibles = [m for m in ctx.materias[carrera_id] if m not in cursadas[alumno_id]]
            for materia_id in rng.sample(disponibles, MATERIAS_POR_ALUMNO):
                demanda[materia_id].append(alumno_id)
                cursadas[alumno_id].add(materia_id)

        ctx.grupos[periodo_id] = []
        inscripciones: list[tuple[int, int]] = []
        for materia_id, alumnos in demanda.items():
            carrera_id = next(c for c, ms in ctx.materias.items() if materia_id in ms)
            centro_id = ctx.carreras[carrera_id]
            for n in range(math.ceil(len(alumnos) / CUPO_GRUPO)):
                cur.execute(
                    "INSERT INTO grupo (materia_id, profesor_id, periodo_id, clave, cupo) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING grupo_id",
                    (materia_id, rng.choice(ctx.profesores[centro_id]), periodo_id,
                     f"G{n + 1}", CUPO_GRUPO),
                )
                grupo_id = cur.fetchone()[0]
                ctx.grupos[periodo_id].append(grupo_id)
                dia = rng.randint(1, 5)
                hora = rng.choice([7, 9, 11, 13, 15, 17])
                cur.executemany(
                    "INSERT INTO horario (grupo_id, dia_semana, hora_inicio, hora_fin, aula) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    [(grupo_id, d, f"{hora}:00", f"{hora + 2}:00", f"A-{rng.randint(100, 399)}")
                     for d in (dia, dia + 2 if dia <= 3 else dia - 2)],
                )
                bloque = alumnos[n * CUPO_GRUPO:(n + 1) * CUPO_GRUPO]
                inscripciones.extend((a, grupo_id) for a in bloque)

        # La API usaría sp_inscribir_alumno; aquí se insertan directo por
        # volumen (las reglas del procedimiento ya se respetan al armar los
        # grupos). centro_academico_id lo llena el trigger.
        cur.executemany(
            "INSERT INTO inscripcion (alumno_id, grupo_id) VALUES (%s, %s)", inscripciones
        )


def calificaciones(cur: psycopg.Cursor, ctx: Contexto, rng: random.Random) -> None:
    """Periodo pasado: 3 parciales y final validada. Periodo actual: 2 parciales."""
    def nota() -> float:
        return round(min(10.0, max(0.0, rng.gauss(7.8, 1.6))), 1)

    pasado, actual = ctx.periodos["2026-ENE-JUN"], ctx.periodos["2026-AGO-DIC"]
    cur.execute(
        "SELECT i.inscripcion_id, g.periodo_id FROM inscripcion i JOIN grupo g USING (grupo_id)"
    )
    filas: list[tuple] = []
    for inscripcion_id, periodo_id in cur.fetchall():
        if periodo_id == pasado:
            parciales = [nota(), nota(), nota()]
            filas += [(inscripcion_id, f"parcial{k}", v, False) for k, v in enumerate(parciales, 1)]
            filas.append((inscripcion_id, "final", round(sum(parciales) / 3, 1), True))
        elif periodo_id == actual:
            filas += [(inscripcion_id, f"parcial{k}", nota(), False) for k in (1, 2)]
    # Los triggers recalculan promedio_parciales y escriben la bitácora.
    cur.executemany(
        "INSERT INTO calificacion (inscripcion_id, tipo, valor, validada) VALUES (%s, %s, %s, %s)",
        filas,
    )


def tareas_entregas_asistencia(cur: psycopg.Cursor, ctx: Contexto, rng: random.Random) -> None:
    """Tareas del periodo actual, entregas (80 % a tiempo) y pase de lista."""
    ahora = datetime.now(UTC)
    for grupo_id in ctx.grupos[ctx.periodos["2026-AGO-DIC"]]:
        tareas: list[int] = []
        for n in range(TAREAS_POR_GRUPO):
            publicada = ahora - timedelta(days=70 - n * 13)   # la última sigue abierta
            limite = publicada + timedelta(days=7)
            cur.execute(
                "INSERT INTO tarea (grupo_id, titulo, publicada_en, fecha_limite) "
                "VALUES (%s, %s, %s, %s) RETURNING tarea_id",
                (grupo_id, f"Tarea {n + 1}", publicada, limite),
            )
            tareas.append((cur.fetchone()[0], limite))

        cur.execute(
            "SELECT inscripcion_id FROM inscripcion WHERE grupo_id = %s AND estado = 'activa'",
            (grupo_id,),
        )
        inscritos = [r[0] for r in cur.fetchall()]
        entregas: list[tuple] = []
        for tarea_id, limite in tareas:
            if limite > ahora:
                continue   # tarea todavía abierta: aparece en pendientes
            for inscripcion_id in inscritos:
                if rng.random() < 0.85:
                    a_tiempo = rng.random() < 0.8
                    cuando = limite - timedelta(hours=rng.randint(1, 90)) if a_tiempo \
                        else limite + timedelta(hours=rng.randint(1, 48))  # dentro del margen de 48 h (db/07)
                    calif = round(rng.uniform(5, 10), 1) if rng.random() < 0.7 else None
                    entregas.append((tarea_id, inscripcion_id, cuando,
                                     f"entregas/{tarea_id}/{inscripcion_id}.pdf",
                                     rng.randint(20_000, 5_000_000), "application/pdf", calif))
        cur.executemany(
            "INSERT INTO entrega (tarea_id, inscripcion_id, entregada_en, archivo_ruta, "
            "archivo_tamano_bytes, archivo_tipo, calificacion) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            entregas,
        )

        fechas = [ahora.date() - timedelta(days=7 * k) for k in range(1, DIAS_ASISTENCIA + 1)]
        estados = ["presente"] * 8 + ["falta", "retardo"]
        cur.executemany(
            "INSERT INTO asistencia (inscripcion_id, fecha, estado) VALUES (%s, %s, %s)",
            [(i, f, rng.choice(estados)) for i in inscritos for f in fechas],
        )


def comunicacion(cur: psycopg.Cursor, ctx: Contexto, rng: random.Random, fake: Faker) -> None:
    """Avisos por grupo y generales, y conversaciones directas con mensajes."""
    cur.execute("SELECT g.grupo_id, g.profesor_id FROM grupo g WHERE periodo_id = %s",
                (ctx.periodos["2026-AGO-DIC"],))
    avisos = [(ctx.profesor_usuario[p], g, f"Aviso del grupo {g}", fake.sentence())
              for g, p in cur.fetchall() if rng.random() < 0.6]
    avisos += [(1, None, f"Aviso general {k}", fake.sentence()) for k in range(1, 6)]
    cur.executemany(
        "INSERT INTO aviso (autor_usuario_id, grupo_id, titulo, cuerpo) VALUES (%s, %s, %s, %s)",
        avisos,
    )

    profesores = list(ctx.profesor_usuario.values())
    for alumno_id, usuario_alumno, _ in rng.sample(ctx.alumnos, min(300, len(ctx.alumnos))):
        cur.execute("INSERT INTO conversacion (tipo) VALUES ('directa') RETURNING conversacion_id")
        conv = cur.fetchone()[0]
        usuario_prof = rng.choice(profesores)
        cur.executemany(
            "INSERT INTO participante_conversacion (conversacion_id, usuario_id) VALUES (%s, %s)",
            [(conv, usuario_alumno), (conv, usuario_prof)],
        )
        cur.executemany(
            "INSERT INTO mensaje (conversacion_id, remitente_id, cuerpo) VALUES (%s, %s, %s)",
            [(conv, rng.choice([usuario_alumno, usuario_prof]), fake.sentence())
             for _ in range(rng.randint(2, 6))],
        )


def resumen(cur: psycopg.Cursor) -> None:
    """Imprime el total de registros por tabla y el conteo por centro."""
    total = 0
    print("\nRegistros por tabla")
    for tabla in reversed(TABLAS):
        cur.execute(sql.SQL("SELECT count(*) FROM sigaf.{}").format(sql.Identifier(tabla)))
        n = cur.fetchone()[0]
        total += n
        print(f"  {tabla:<28}{n:>9,}")
    print(f"  {'TOTAL':<28}{total:>9,}")

    print("\nConteo por centro (para decidir el reparto A/B)")
    cur.execute("""
        SELECT c.clave,
               (SELECT count(*) FROM sigaf.alumno a JOIN sigaf.carrera k USING (carrera_id)
                 WHERE k.centro_academico_id = c.centro_academico_id) AS alumnos,
               (SELECT count(*) FROM sigaf.inscripcion i
                 WHERE i.centro_academico_id = c.centro_academico_id) AS inscripciones,
               (SELECT count(*) FROM sigaf.calificacion q
                 WHERE q.centro_academico_id = c.centro_academico_id) AS calificaciones
        FROM sigaf.centro_academico c ORDER BY c.centro_academico_id
    """)
    print(f"  {'centro':<8}{'alumnos':>9}{'inscripc.':>11}{'calific.':>10}")
    for clave, alumnos, insc, calif in cur.fetchall():
        print(f"  {clave:<8}{alumnos:>9,}{insc:>11,}{calif:>10,}")


def argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Genera datos sintéticos para SIGAF.")
    p.add_argument("--dsn", default=os.environ.get("SIGAF_DSN", "postgresql://postgres@localhost:5432/postgres"),
                   help="conexión a PostgreSQL (o variable SIGAF_DSN); la contraseña va en PGPASSWORD")
    p.add_argument("--alumnos", type=int, default=1000, help="número de alumnos (default 1000)")
    p.add_argument("--semilla", type=int, default=2026, help="semilla para resultados repetibles")
    p.add_argument("--pesos", type=float, nargs=6, default=PESOS_DEFAULT,
                   metavar="P", help="peso de alumnos de cada uno de los 6 centros")
    p.add_argument("--limpiar", action="store_true", help="vacía las tablas antes de generar")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = argumentos(argv)
    if abs(sum(args.pesos) - 1) > 0.01:
        print("Los pesos deben sumar 1.", file=sys.stderr)
        return 2

    # random (no secrets) a propósito: son datos de prueba y deben poder
    # repetirse con la misma semilla; no se usan para nada de seguridad.
    rng = random.Random(args.semilla)  # nosec B311
    fake = Faker("es_MX")
    Faker.seed(args.semilla)
    ctx = Contexto()
    inicio = time.perf_counter()

    llaves = {n: os.environ.get(v, "") for n, v in
              (("llave_datos", "SIGAF_LLAVE_DATOS"), ("llave_seudonimo", "SIGAF_LLAVE_SEUDONIMO"))}
    if any(len(v) < 32 for v in llaves.values()):
        print("Faltan SIGAF_LLAVE_DATOS y SIGAF_LLAVE_SEUDONIMO (32+ caracteres cada una).",
              file=sys.stderr)
        return 2

    try:
        with psycopg.connect(args.dsn, options="-c search_path=sigaf,public") as conn, \
                conn.cursor() as cur:
            for nombre, valor in llaves.items():
                cur.execute("SELECT set_config(%s, %s, false)", (f"sigaf.{nombre}", valor))
            cur.execute("SELECT count(*) FROM centro_academico")
            if cur.fetchone()[0] and not args.limpiar:
                raise GeneradorError("La base ya tiene datos. Usa --limpiar para vaciarla.")
            if args.limpiar:
                limpiar(cur)
            pasos = [
                ("catálogos", lambda: catalogos(cur, ctx, rng)),
                ("profesores y alumnos", lambda: personas(cur, ctx, fake, rng, args.alumnos, args.pesos)),
                ("grupos e inscripciones", lambda: grupos_e_inscripciones(cur, ctx, rng)),
                ("calificaciones", lambda: calificaciones(cur, ctx, rng)),
                ("tareas, entregas y asistencia", lambda: tareas_entregas_asistencia(cur, ctx, rng)),
                ("avisos y mensajes", lambda: comunicacion(cur, ctx, rng, fake)),
            ]
            for nombre, paso in pasos:
                t = time.perf_counter()
                paso()
                print(f"[ok] {nombre} ({time.perf_counter() - t:.1f} s)")
            resumen(cur)
        # Al salir del with sin excepción, psycopg hace COMMIT.
    except GeneradorError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except psycopg.Error as e:
        # Si algo falla, psycopg hace ROLLBACK y la base queda como estaba.
        print(f"Error de base de datos (se hizo rollback): {e}", file=sys.stderr)
        return 1
    else:
        print(f"\nListo en {time.perf_counter() - inicio:.1f} s.")
        return 0
    finally:
        Faker.seed(None)


if __name__ == "__main__":
    sys.exit(main())
