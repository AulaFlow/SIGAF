"""ETL: lee los fragmentos de PostgreSQL y llena MongoDB por lotes.

Consistencia EVENTUAL (decisión CAP del equipo): MongoDB es una copia para
análisis que se actualiza cada vez que corre el ETL; nunca es la fuente de
verdad de las calificaciones.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from itertools import islice

from .fuentes import FuenteAcademica
from .modelos import Documento
from .repositorio import RepositorioAnalitico

log = logging.getLogger(__name__)


class ETLError(Exception):
    """Falló la lectura de un fragmento o la escritura en MongoDB."""


def en_lotes(datos: Iterable[Documento], tam: int) -> Iterator[list[Documento]]:
    it = iter(datos)
    while lote := list(islice(it, tam)):
        yield lote


@dataclass
class ResultadoETL:
    por_coleccion: dict[str, int] = field(default_factory=dict)
    fragmentos: list[str] = field(default_factory=list)

    def sumar(self, coleccion: str, n: int) -> None:
        self.por_coleccion[coleccion] = self.por_coleccion.get(coleccion, 0) + n


class ProcesoETL:
    """Corre el ETL sobre una o varias fuentes (fragmentos A y B)."""

    def __init__(self, repositorio: RepositorioAnalitico, tam_lote: int = 500) -> None:
        self._repo = repositorio
        self._tam_lote = tam_lote

    def _cargar(self, coleccion: str, extraer: Callable[[], Iterable[Documento]],
                resultado: ResultadoETL) -> None:
        for lote in en_lotes(extraer(), self._tam_lote):
            resultado.sumar(coleccion, self._repo.guardar_lote(lote))

    def ejecutar(self, fuentes: Iterable[FuenteAcademica]) -> ResultadoETL:
        resultado = ResultadoETL()
        for fuente in fuentes:
            try:
                self._cargar("resumen_grupo", fuente.resumen_grupos, resultado)
                self._cargar("actividad_alumno", fuente.actividad_alumnos, resultado)
                self._cargar("historico_calificaciones", fuente.calificaciones, resultado)
            except Exception as e:  # cualquier error de la fuente o de Mongo
                raise ETLError(f"Falló el fragmento {fuente.nombre}: {e}") from e
            else:
                resultado.fragmentos.append(fuente.nombre)
                log.info("Fragmento %s cargado", fuente.nombre)
        return resultado
