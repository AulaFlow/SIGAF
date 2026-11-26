"""SIGAF · gráficas del monitoreo de la base distribuida (issue #26).

Lee ``historial.csv`` (lo llena ``estado.sh``) y dibuja con Matplotlib:

1. ``1_tamano_fragmentos.png``  crecimiento del almacenamiento de A y B (MB).
2. ``2_conexiones_nodos.png``   conexiones activas de cada nodo.
3. ``3_roles_nodos.png``        quién fue primario, réplica o estuvo caído
                                (ahí se ve un failover).
4. ``4_lag_replicas.png``       atraso de las réplicas (MB).

Uso (desde ``db/``)::

    pip install -r monitoreo/requirements.txt
    python monitoreo/graficas.py                       # lee monitoreo/historial.csv
    python monitoreo/graficas.py --csv otro.csv --salida carpeta/
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin ventana: solo guarda PNG (sirve en Docker y en CI)

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

AQUI = Path(__file__).resolve().parent
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"
MB = 1024 * 1024

# (fecha, valor): un punto de una línea de la gráfica
Serie = list[tuple[datetime, float]]

# Colores fijos para que A y B se vean igual en todas las gráficas
COLOR_FRAGMENTO = {"A": "#1f77b4", "B": "#ff7f0e"}
COLOR_ROL = {"Primario": "#2ca02c", "Réplica": "#1f77b4", "Caído": "#d62728"}


@dataclass(frozen=True)
class Medicion:
    """Una fila del historial: cómo estaba un nodo en un momento."""

    fecha: datetime
    fragmento: str
    nodo: str
    rol: str
    estado: str
    lag_mb: float | None
    conexiones: int | None
    tamano_bytes: int | None

    @property
    def rol_simple(self) -> str:
        """Primario, Réplica o Caído (Patroni usa más nombres)."""
        if self.estado not in ("running", "streaming"):
            return "Caído"
        return "Primario" if self.rol == "Leader" else "Réplica"


def _entero(valor: str) -> int | None:
    return int(valor) if valor.strip() else None


def _decimal(valor: str) -> float | None:
    return float(valor) if valor.strip() else None


def leer_historial(ruta: Path) -> list[Medicion]:
    """Lee el CSV; ignora filas rotas (por ejemplo si se cortó a la mitad)."""
    mediciones: list[Medicion] = []
    with ruta.open(newline="", encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            try:
                mediciones.append(
                    Medicion(
                        fecha=datetime.strptime(fila["fecha"], FORMATO_FECHA),
                        fragmento=fila["fragmento"],
                        nodo=fila["nodo"],
                        rol=fila["rol"],
                        estado=fila["estado"],
                        lag_mb=_decimal(fila["lag_mb"]),
                        conexiones=_entero(fila["conexiones"]),
                        tamano_bytes=_entero(fila["tamano_bytes"]),
                    )
                )
            except (KeyError, ValueError, TypeError, AttributeError):
                continue
    return sorted(mediciones, key=lambda m: m.fecha)


def tamano_por_fragmento(mediciones: list[Medicion]) -> dict[str, Serie]:
    """Tamaño (MB) de cada fragmento en cada foto, medido en su primario.

    La réplica tiene los mismos datos, así que contar las dos sería el doble.
    """
    series: dict[str, Serie] = defaultdict(list)
    for m in mediciones:
        if m.rol_simple == "Primario" and m.tamano_bytes is not None:
            series[m.fragmento].append((m.fecha, m.tamano_bytes / MB))
    return dict(series)


def serie_por_nodo(mediciones: list[Medicion], campo: str) -> dict[str, Serie]:
    """Serie de tiempo de ``conexiones`` o ``lag_mb`` por nodo (sin huecos vacíos)."""
    series: dict[str, Serie] = defaultdict(list)
    for m in mediciones:
        valor = getattr(m, campo)
        if valor is not None:
            series[m.nodo].append((m.fecha, float(valor)))
    return dict(series)


def _formato_eje_tiempo(ax) -> None:
    # ConciseDateFormatter elige solo el formato según el rango (segundos, horas o días)
    localizador = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(localizador)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(localizador))
    ax.set_xlabel("Fecha y hora")
    ax.grid(True, alpha=0.3)


def _lineas(series: dict[str, Serie], titulo: str, eje_y: str,
            colores: dict[str, str] | None = None) -> Figure:
    fig, ax = plt.subplots(figsize=(10, 5))
    for nombre in sorted(series):
        fechas, valores = zip(*series[nombre], strict=True)
        ax.plot(fechas, valores, marker="o", markersize=3, label=nombre,
                color=(colores or {}).get(nombre))
    ax.set_title(titulo)
    ax.set_ylabel(eje_y)
    if series:
        ax.legend(title="")
    else:
        ax.text(0.5, 0.5, "Sin datos todavía", ha="center", va="center", transform=ax.transAxes)
    _formato_eje_tiempo(ax)
    fig.tight_layout()
    return fig


def grafica_tamano(mediciones: list[Medicion]) -> Figure:
    series = tamano_por_fragmento(mediciones)
    fig = _lineas(series, "Crecimiento del almacenamiento por fragmento", "Tamaño (MB)",
                  COLOR_FRAGMENTO)
    ax = fig.axes[0]
    # El eje empieza en 0: si no, Matplotlib hace zoom y 0.01 MB parece un crecimiento enorme
    tope = max((mb for serie in series.values() for _, mb in serie), default=1)
    ax.set_ylim(bottom=0, top=tope * 1.2)
    # Último valor de cada fragmento, uno arriba del otro para que no se encimen
    for i, nombre in enumerate(sorted(series)):
        fecha, mb = series[nombre][-1]
        ax.annotate(f"{nombre}: {mb:.1f} MB", (fecha, mb), textcoords="offset points",
                    xytext=(-5, 8 + 16 * i), ha="right", color=COLOR_FRAGMENTO.get(nombre))
    return fig


def _por_nodo(series: dict[str, Serie], titulo: str, eje_y: str) -> Figure:
    """Una gráfica chiquita por nodo (2 x 2). Si van todas juntas, las líneas iguales se enciman."""
    nodos = sorted(series) or ["sin datos"]
    columnas = 2
    filas = (len(nodos) + columnas - 1) // columnas
    fig, ejes = plt.subplots(filas, columnas, figsize=(10, 2.6 * filas + 0.8),
                             sharex=True, sharey=True, squeeze=False)
    tope = max((v for serie in series.values() for _, v in serie), default=1)
    for ax, nodo in zip(ejes.flat, nodos, strict=False):
        color = COLOR_FRAGMENTO.get(nodo[3:4].upper())       # pg-a1 -> A
        if nodo in series:
            fechas, valores = zip(*series[nodo], strict=True)
            ax.plot(fechas, valores, marker="o", markersize=3, color=color)
        else:
            ax.text(0.5, 0.5, "Sin datos todavía", ha="center", va="center",
                    transform=ax.transAxes)
        ax.set_title(nodo, fontsize=10)
        ax.set_ylim(bottom=0, top=max(tope, 1) * 1.25)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        _formato_eje_tiempo(ax)
        ax.set_xlabel("")
    for ax in list(ejes.flat)[len(nodos):]:
        ax.set_visible(False)
    fig.suptitle(titulo)
    fig.supylabel(eje_y)
    fig.supxlabel("Fecha y hora")
    fig.tight_layout()
    return fig


def grafica_conexiones(mediciones: list[Medicion]) -> Figure:
    return _por_nodo(serie_por_nodo(mediciones, "conexiones"),
                     "Conexiones activas por nodo", "Conexiones")


def grafica_lag(mediciones: list[Medicion]) -> Figure:
    return _por_nodo(serie_por_nodo(mediciones, "lag_mb"),
                     "Atraso de las réplicas (0 = al día; el primario no tiene lag)",
                     "Lag (MB)")


def grafica_roles(mediciones: list[Medicion]) -> Figure:
    """Un renglón por nodo y un cuadrito por foto: verde primario, azul réplica, rojo caído."""
    nodos = sorted({m.nodo for m in mediciones})
    renglon = {nodo: i for i, nodo in enumerate(nodos)}
    fig, ax = plt.subplots(figsize=(10, 1.2 + 0.6 * max(len(nodos), 1)))
    for rol, color in COLOR_ROL.items():
        puntos = [m for m in mediciones if m.rol_simple == rol]
        if puntos:
            ax.scatter([m.fecha for m in puntos], [renglon[m.nodo] for m in puntos],
                       color=color, label=rol, marker="s", s=40)
    ax.set_yticks(range(len(nodos)), nodos)
    ax.set_ylim(-0.7, max(len(nodos), 1) - 0.3)
    ax.set_title("Rol de cada nodo en el tiempo (un cambio de color = failover)")
    if mediciones:
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))
    else:
        ax.text(0.5, 0.5, "Sin datos todavía", ha="center", va="center", transform=ax.transAxes)
    _formato_eje_tiempo(ax)
    fig.tight_layout()
    return fig


GRAFICAS = {
    "1_tamano_fragmentos.png": grafica_tamano,
    "2_conexiones_nodos.png": grafica_conexiones,
    "3_roles_nodos.png": grafica_roles,
    "4_lag_replicas.png": grafica_lag,
}


def generar(ruta_csv: Path, salida: Path) -> list[Path]:
    """Dibuja las 4 gráficas y regresa las rutas de los PNG."""
    mediciones = leer_historial(ruta_csv)
    salida.mkdir(parents=True, exist_ok=True)
    archivos = []
    for nombre, dibujar in GRAFICAS.items():
        fig = dibujar(mediciones)
        destino = salida / nombre
        fig.savefig(destino, dpi=120)
        plt.close(fig)  # libera memoria: si no, Matplotlib las acumula
        archivos.append(destino)
    return archivos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gráficas del monitoreo de SIGAF")
    parser.add_argument("--csv", type=Path, default=AQUI / "historial.csv")
    parser.add_argument("--salida", type=Path, default=AQUI / "salida")
    args = parser.parse_args(argv)
    if not args.csv.exists():
        print(f"No existe {args.csv}. Corre antes: bash monitoreo/estado.sh")
        return 1
    for archivo in generar(args.csv, args.salida):
        print(f"Guardada: {archivo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
