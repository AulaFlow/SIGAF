"""Modelos de los documentos que se guardan en MongoDB.

Cada clase sabe convertirse a documento (``a_documento``) y reconstruirse
desde uno (``desde_documento``). El ``_id`` es estable, así el ETL puede
volver a correr sin duplicar (reemplaza el documento existente).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from typing import Any, ClassVar, Self


@dataclass(frozen=True)
class Documento(ABC):
    """Base de todos los documentos analíticos."""

    coleccion: ClassVar[str]

    @property
    @abstractmethod
    def id(self) -> str:
        """Identificador estable del documento."""

    def a_documento(self) -> dict[str, Any]:
        doc = asdict(self)
        doc["_id"] = self.id
        doc["actualizado_en"] = datetime.now(timezone.utc)
        return doc

    @classmethod
    def desde_documento(cls, doc: dict[str, Any]) -> Self:
        nombres = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in doc.items() if k in nombres})


@dataclass(frozen=True)
class ResumenGrupo(Documento):
    """Indicadores de un grupo en un periodo."""

    coleccion: ClassVar[str] = "resumen_grupo"

    grupo_id: int
    periodo: str
    centro_academico_id: int
    materia_clave: str
    materia: str
    alumnos: int
    promedio: float | None
    pct_aprobados: float | None
    pct_asistencia: float | None

    @property
    def id(self) -> str:
        return f"{self.periodo}:{self.grupo_id}"


@dataclass(frozen=True)
class ActividadAlumno(Documento):
    """Entregas y faltas de un alumno en un periodo (sin datos personales)."""

    coleccion: ClassVar[str] = "actividad_alumno"

    alumno_id: int
    periodo: str
    centro_academico_id: int
    centro: str
    entregas_a_tiempo: int
    entregas_tardias: int
    no_entregadas: int
    faltas: int

    @property
    def id(self) -> str:
        return f"{self.periodo}:{self.alumno_id}"


@dataclass(frozen=True)
class RegistroCalificacion(Documento):
    """Una calificación, para el histórico y la distribución."""

    coleccion: ClassVar[str] = "historico_calificaciones"

    calificacion_id: int
    alumno_id: int
    periodo: str
    centro_academico_id: int
    materia_clave: str
    tipo: str
    valor: float

    @property
    def id(self) -> str:
        return str(self.calificacion_id)


MODELOS: tuple[type[Documento], ...] = (ResumenGrupo, ActividadAlumno, RegistroCalificacion)
