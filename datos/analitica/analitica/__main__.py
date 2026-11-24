"""Uso:
    python -m analitica etl                 # PostgreSQL (fragmentos) -> MongoDB
    python -m analitica graficas [--periodo 2026-AGO-DIC] [--salida graficas/]

Configuración por variables de entorno (sin contraseñas en el código):
    SIGAF_FRAGMENTOS  "A=postgresql://sigaf_etl_svc@laptop1/postgres;B=postgresql://sigaf_etl_svc@laptop2/postgres"
                      (si no está, usa SIGAF_DSN como un solo fragmento)
    PGPASSWORD        contraseña de la cuenta sigaf_etl_svc
    SIGAF_MONGO_URI   default mongodb://localhost:27017
    SIGAF_MONGO_DB    default sigaf_analitica
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from .etl import ETLError, ProcesoETL
from .fuentes import FuentePostgres
from .graficas import SinDatosError, generar_todas
from .repositorio import RepositorioMongo


def fragmentos_de_entorno() -> list[tuple[str, str]]:
    texto = os.environ.get("SIGAF_FRAGMENTOS", "").strip()
    if not texto:
        return [("unico", os.environ.get("SIGAF_DSN", "postgresql://postgres@localhost:5432/postgres"))]
    return [tuple(p.split("=", 1)) for p in texto.split(";") if p.strip()]  # type: ignore[misc]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m analitica")
    sub = p.add_subparsers(dest="comando", required=True)
    sub.add_parser("etl", help="copia los indicadores de PostgreSQL a MongoDB")
    g = sub.add_parser("graficas", help="genera las 3 gráficas en PNG")
    g.add_argument("--periodo", help="p. ej. 2026-AGO-DIC (default: todos)")
    g.add_argument("--salida", default="graficas", help="carpeta de salida")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    cliente: MongoClient = MongoClient(os.environ.get("SIGAF_MONGO_URI", "mongodb://localhost:27017"),
                                       serverSelectionTimeoutMS=5000)
    try:
        repo = RepositorioMongo(cliente[os.environ.get("SIGAF_MONGO_DB", "sigaf_analitica")])
        if args.comando == "etl":
            repo.crear_indices()
            etl = ProcesoETL(repo)
            for nombre, dsn in fragmentos_de_entorno():
                with FuentePostgres(nombre, dsn) as fuente:
                    resultado = etl.ejecutar([fuente])
                print(f"Fragmento {nombre}: {resultado.por_coleccion}")
        else:
            for ruta in generar_todas(repo, args.salida, args.periodo):
                print(f"Gráfica guardada: {ruta}")
    except (ETLError, SinDatosError, PyMongoError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        cliente.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
