"""Las 3 gráficas que eligió el equipo, con datos de MongoDB y Matplotlib.

Cada gráfica es una subclase de ``Grafica`` (polimorfismo): define su
consulta a MongoDB (``pipeline``) y cómo dibujar el resultado (``dibujar``);
la clase base se encarga de pedir los datos, armar la figura y guardarla.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")   # sin ventana: genera archivos PNG
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from .repositorio import RepositorioAnalitico

# Paleta validada (contraste y daltonismo) para fondo claro
FONDO = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
REJILLA = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]   # azul, naranja, aqua
APROBATORIA = 6.0


class SinDatosError(Exception):
    """MongoDB no tiene datos para la gráfica (¿ya corrió el ETL?)."""


class Grafica(ABC):
    """Plantilla común de las gráficas."""

    titulo: str
    coleccion: str
    archivo: str

    def __init__(self, repositorio: RepositorioAnalitico, periodo: str | None = None) -> None:
        self._repo = repositorio
        self._periodo = periodo

    def _filtro_periodo(self) -> list[dict[str, Any]]:
        return [{"$match": {"periodo": self._periodo}}] if self._periodo else []

    @abstractmethod
    def pipeline(self) -> list[dict[str, Any]]:
        """Consulta de agregación en MongoDB."""

    @abstractmethod
    def dibujar(self, ax: Axes, datos: list[dict[str, Any]]) -> None:
        """Dibuja los datos en los ejes."""

    def generar(self) -> Figure:
        datos = self._repo.agregar(self.coleccion, self.pipeline())
        if not datos:
            raise SinDatosError(f"No hay datos en {self.coleccion} para '{self.titulo}'")
        fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150, facecolor=FONDO)
        ax.set_facecolor(FONDO)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        for lado in ("left", "bottom"):
            ax.spines[lado].set_color(REJILLA)
        ax.tick_params(colors=TEXTO_2, labelsize=9)
        ax.set_axisbelow(True)
        self.dibujar(ax, datos)
        sub = f" · periodo {self._periodo}" if self._periodo else ""
        ax.set_title(self.titulo + sub, loc="left", fontsize=13, color=TEXTO, pad=14)
        fig.tight_layout()
        return fig

    def guardar(self, carpeta: str | Path) -> Path:
        ruta = Path(carpeta) / self.archivo
        ruta.parent.mkdir(parents=True, exist_ok=True)
        fig = self.generar()
        try:
            fig.savefig(ruta, facecolor=FONDO)
        finally:
            plt.close(fig)   # libera memoria aunque falle el guardado
        return ruta


class DistribucionCalificaciones(Grafica):
    """Histograma de calificaciones de 0 a 10 con la línea de aprobación."""

    titulo = "Distribución de calificaciones"
    coleccion = "historico_calificaciones"
    archivo = "1_distribucion_calificaciones.png"

    def pipeline(self) -> list[dict[str, Any]]:
        return [*self._filtro_periodo(), {"$project": {"_id": 0, "valor": 1}}]

    def dibujar(self, ax: Axes, datos: list[dict[str, Any]]) -> None:
        valores = [d["valor"] for d in datos]
        ax.hist(valores, bins=[i / 2 for i in range(21)], color=SERIES[0],
                edgecolor=FONDO, linewidth=2)
        ax.axvline(APROBATORIA, color=TEXTO_2, linestyle="--", linewidth=1.2)
        reprobadas = sum(v < APROBATORIA for v in valores) / len(valores) * 100
        ax.annotate(f"Aprobatoria 6.0 · {reprobadas:.1f} % por debajo", xy=(APROBATORIA, 1),
                    xycoords=("data", "axes fraction"), xytext=(6, -14), textcoords="offset points",
                    color=TEXTO_2, fontsize=9)
        ax.set_xlim(0, 10)
        ax.set_xticks(range(11))
        ax.set_xlabel("Calificación", color=TEXTO_2)
        ax.set_ylabel(f"Calificaciones registradas (total {len(valores):,})", color=TEXTO_2)
        ax.grid(axis="y", color=REJILLA, linewidth=0.8)


class PromedioPorMateria(Grafica):
    """Barras horizontales: las materias con el promedio más bajo."""

    titulo = "Materias con el promedio más bajo"
    coleccion = "resumen_grupo"
    archivo = "2_promedio_por_materia.png"

    def __init__(self, repositorio: RepositorioAnalitico, periodo: str | None = None,
                 cuantas: int = 12) -> None:
        super().__init__(repositorio, periodo)
        self._cuantas = cuantas

    def pipeline(self) -> list[dict[str, Any]]:
        return [
            *self._filtro_periodo(),
            {"$match": {"promedio": {"$ne": None}}},
            {"$group": {"_id": "$materia_clave", "materia": {"$first": "$materia"},
                        "promedio": {"$avg": "$promedio"}, "alumnos": {"$sum": "$alumnos"}}},
            {"$sort": {"promedio": 1}},
            {"$limit": self._cuantas},
        ]

    def dibujar(self, ax: Axes, datos: list[dict[str, Any]]) -> None:
        datos = list(reversed(datos))          # la más baja queda arriba
        etiquetas = [f"{d['_id']} · {d['materia']}"[:42] for d in datos]
        promedios = [d["promedio"] for d in datos]
        barras = ax.barh(etiquetas, promedios, color=SERIES[0], height=0.6)
        for barra, d in zip(barras, datos):
            ax.text(barra.get_width() + 0.08, barra.get_y() + barra.get_height() / 2,
                    f"{d['promedio']:.2f}  ({d['alumnos']} alumnos)", va="center", fontsize=8, color=TEXTO_2)
        ax.axvline(APROBATORIA, color=TEXTO_2, linestyle="--", linewidth=1.2)
        ax.set_xlim(0, 10)
        ax.set_xlabel("Promedio de parciales", color=TEXTO_2)
        ax.grid(axis="x", color=REJILLA, linewidth=0.8)


class EntregasPorCentro(Grafica):
    """Barras apiladas: entregas a tiempo, tardías y no entregadas por centro."""

    titulo = "Entregas a tiempo vs tardías por centro académico"
    coleccion = "actividad_alumno"
    archivo = "3_entregas_a_tiempo_vs_tardias.png"
    CATEGORIAS = (("a_tiempo", "A tiempo"), ("tardias", "Tardías"), ("no_entregadas", "No entregadas"))

    def pipeline(self) -> list[dict[str, Any]]:
        return [
            *self._filtro_periodo(),
            {"$group": {"_id": "$centro",
                        "a_tiempo": {"$sum": "$entregas_a_tiempo"},
                        "tardias": {"$sum": "$entregas_tardias"},
                        "no_entregadas": {"$sum": "$no_entregadas"}}},
            {"$sort": {"_id": 1}},
        ]

    def dibujar(self, ax: Axes, datos: list[dict[str, Any]]) -> None:
        centros = [d["_id"] for d in datos]
        totales = [sum(d[c] for c, _ in self.CATEGORIAS) or 1 for d in datos]
        base = [0.0] * len(datos)
        for (clave, nombre), color in zip(self.CATEGORIAS, SERIES):
            pct = [d[clave] / t * 100 for d, t in zip(datos, totales)]
            ax.bar(centros, pct, bottom=base, color=color, label=nombre, width=0.6,
                   edgecolor=FONDO, linewidth=2)
            if clave == "a_tiempo":
                for x, p in enumerate(pct):
                    ax.text(x, p / 2, f"{p:.0f} %", ha="center", va="center", fontsize=9, color="white")
            base = [b + p for b, p in zip(base, pct)]
        ax.set_ylim(0, 100)
        ax.set_ylabel("% de las tareas vencidas", color=TEXTO_2)
        ax.grid(axis="y", color=REJILLA, linewidth=0.8)
        ax.legend(frameon=False, ncols=3, loc="upper left", bbox_to_anchor=(0, -0.08), fontsize=9,
                  labelcolor=TEXTO)


GRAFICAS: tuple[type[Grafica], ...] = (DistribucionCalificaciones, PromedioPorMateria, EntregasPorCentro)


def generar_todas(repo: RepositorioAnalitico, carpeta: str | Path, periodo: str | None = None) -> list[Path]:
    return [cls(repo, periodo).guardar(carpeta) for cls in GRAFICAS]
