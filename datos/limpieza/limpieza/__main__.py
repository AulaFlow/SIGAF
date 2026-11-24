"""Uso:
    python -m limpieza --alumnos ejemplos/alumnos_sucio.csv \\
                       --calificaciones ejemplos/calificaciones_sucio.csv \\
                       --reporte reporte_limpieza.json [--cargar]

Sin --cargar solo limpia y escribe el reporte. Con --cargar además guarda
en PostgreSQL (necesita SIGAF_DSN o --dsn, PGPASSWORD y las llaves
SIGAF_LLAVE_DATOS y SIGAF_LLAVE_SEUDONIMO en variables de entorno).
"""

from __future__ import annotations

import argparse
import os
import sys

from .cargar import cargar
from .excepciones import LimpiezaError
from .limpiar import (
    COLUMNAS_ALUMNOS,
    COLUMNAS_CALIFICACIONES,
    Reporte,
    guardar_reporte,
    leer_csv,
    limpiar_alumnos,
    limpiar_calificaciones,
)


def imprimir(rep: Reporte) -> None:
    print(f"\n{rep.archivo}: {rep.filas_leidas} leídas, {rep.filas_validas} pasaron la limpieza, "
          f"{len(rep.descartes)} descartadas")
    for motivo, n in rep.correcciones.items():
        print(f"  corregido  {n:>4}  {motivo}")
    motivos: dict[str, int] = {}
    for d in rep.descartes:
        motivos[str(d["motivo"])] = motivos.get(str(d["motivo"]), 0) + 1
    for motivo, n in motivos.items():
        print(f"  descartado {n:>4}  {motivo}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m limpieza", description="Limpia y carga CSV de SIGAF.")
    p.add_argument("--alumnos", help="CSV con matricula,nombre,apellidos,carrera,semestre")
    p.add_argument("--calificaciones", help="CSV con matricula,materia,periodo,tipo,valor")
    p.add_argument("--reporte", default="reporte_limpieza.json", help="dónde guardar el reporte JSON")
    p.add_argument("--cargar", action="store_true", help="además de limpiar, guardar en la base")
    p.add_argument("--dsn", default=os.environ.get("SIGAF_DSN", "postgresql://postgres@localhost:5432/postgres"))
    args = p.parse_args(argv)
    if not args.alumnos and not args.calificaciones:
        p.error("indica --alumnos y/o --calificaciones")

    try:
        alumnos = calificaciones = None
        if args.alumnos:
            alumnos = limpiar_alumnos(leer_csv(args.alumnos, COLUMNAS_ALUMNOS), args.alumnos)
        if args.calificaciones:
            calificaciones = limpiar_calificaciones(
                leer_csv(args.calificaciones, COLUMNAS_CALIFICACIONES), args.calificaciones)
        if args.cargar:
            resultado = cargar(args.dsn, alumnos, calificaciones)
            print(f"Cargados: {resultado['alumnos']} alumnos y {resultado['calificaciones']} calificaciones")
    except LimpiezaError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    else:
        reportes = [r for _, r in (x for x in (alumnos, calificaciones) if x is not None)]
        for rep in reportes:
            imprimir(rep)
        guardar_reporte(reportes, args.reporte)
        print(f"\nReporte guardado en {args.reporte}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
