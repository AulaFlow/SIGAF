"""Línea de comandos del reparto (issue #8).

    python -m reparto generar     llena el fragmento A con los 6 centros (generador de Ricardo)
    python -m reparto repartir    mueve CCEA, CCS y CCDC al fragmento B
    python -m reparto verificar   muestra qué centros hay en cada fragmento
    python -m reparto todo        generar + repartir + verificar

Variables de entorno (las contraseñas nunca van en el código):
    SIGAF_DSN_A, SIGAF_DSN_B      conexión a cada fragmento (por default, HAProxy con TLS)
    SIGAF_PASS_ADMIN              contraseña de sigaf_dba (si no hay PGPASSWORD)
    SIGAF_LLAVE_DATOS, SIGAF_LLAVE_SEUDONIMO   llaves del generador
    SIGAF_NODOS_A, SIGAF_NODOS_B  "primario,replica" para directorio_fragmento
    SIGAF_ALUMNOS                 tamaño de la carga (default 1000 ≈ 150 mil registros)
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
from pathlib import Path

import psycopg

from .repartidor import Nodos, Repartidor, RepartoError, por_centro, vaciar

_TLS = "dbname=postgres user=sigaf_dba sslmode=verify-ca sslrootcert=/certs/ca.crt"
DSN_A = f"host=haproxy port=5432 {_TLS}"
DSN_B = f"host=haproxy port=5434 {_TLS}"
GENERADOR = Path(__file__).resolve().parents[2] / "generador" / "generar_datos.py"


def _nodos(var: str, default: str) -> Nodos:
    primario, replica = os.environ.get(var, default).split(",")
    return Nodos(primario.strip(), replica.strip())


def _dsn(fragmento: str) -> str:
    return os.environ.get(f"SIGAF_DSN_{fragmento}", DSN_A if fragmento == "A" else DSN_B)


def conectar(fragmento: str) -> psycopg.Connection:
    # search_path=sigaf: los triggers de 03_funciones_triggers.sql usan las tablas sin "sigaf."
    return psycopg.connect(_dsn(fragmento), options="-c search_path=sigaf,public")


def generar() -> int:
    """Corre el generador de Ricardo (datos/generador) contra el fragmento A."""
    spec = importlib.util.spec_from_file_location("generar_datos", GENERADOR)
    if spec is None or spec.loader is None:
        print(f"No encontré el generador en {GENERADOR}", file=sys.stderr)
        return 1
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["generar_datos"] = modulo      # dataclasses lo necesita registrado
    spec.loader.exec_module(modulo)
    print("== Vaciando los fragmentos A y B")
    for fragmento in ("A", "B"):
        with conectar(fragmento) as conn:
            vaciar(conn)
    print("== Generando datos sintéticos en el fragmento A (los 6 centros)")
    return modulo.main(["--dsn", _dsn("A"), "--alumnos", os.environ.get("SIGAF_ALUMNOS", "1000")])


def repartir() -> int:
    inicio = time.perf_counter()
    nodos = {"A": _nodos("SIGAF_NODOS_A", "haproxy:5432,haproxy:5433"),
             "B": _nodos("SIGAF_NODOS_B", "haproxy:5434,haproxy:5435")}
    with conectar("A") as a, conectar("B") as b:
        reporte = Repartidor(a, b, nodos).repartir()
    print(f"\n{'tabla':28} {'en A antes':>11} {'quedan en A':>12} {'en B':>8}")
    for c in reporte:
        nota = "  (en los dos)" if c.replicada else ""
        print(f"{c.tabla:28} {c.antes_en_a:>11} {c.quedan_en_a:>12} {c.en_b:>8}  ✔{nota}")
    print(f"\nReparto listo en {time.perf_counter() - inicio:.1f} s: nada se perdió ni se duplicó.")
    return 0


def verificar() -> int:
    for fragmento in ("A", "B"):
        with conectar(fragmento) as conn:
            print(f"\n== Fragmento {fragmento}")
            print(f"{'centro':8} {'alumnos':>8} {'inscripciones':>14} {'calificaciones':>15}")
            for clave, _, alumnos, inscripciones, calificaciones in por_centro(conn):
                print(f"{clave:8} {alumnos:>8} {inscripciones:>14} {calificaciones:>15}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m reparto", description=__doc__.splitlines()[0])
    parser.add_argument("comando", choices=["generar", "repartir", "verificar", "todo"])
    args = parser.parse_args(argv)
    if "PGPASSWORD" not in os.environ and os.environ.get("SIGAF_PASS_ADMIN"):
        os.environ["PGPASSWORD"] = os.environ["SIGAF_PASS_ADMIN"]
    try:
        if args.comando in ("generar", "todo") and (codigo := generar()) != 0:
            return codigo
        if args.comando in ("repartir", "todo"):
            repartir()
        if args.comando in ("verificar", "todo"):
            verificar()
    except RepartoError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except psycopg.Error as e:
        print(f"Error de base de datos (se hizo rollback): {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
