from __future__ import annotations

from datetime import datetime

from .base import Salida


class MisDatos(Salida):
    alumno_id: int
    nombre: str
    apellidos: str


class MateriaBoleta(Salida):
    inscripcion_id: int
    materia_clave: str
    materia: str
    parcial1: float | None
    parcial2: float | None
    parcial3: float | None
    promedio_parciales: float | None
    final: float | None


class Pendiente(Salida):
    tarea_id: int
    titulo: str
    materia: str
    fecha_limite: datetime
    margen_tardia_horas: float
    cierre_entrega: datetime        # fecha_limite + margen_tardia: después ya no se acepta
    solo_tardia: bool               # True: ya pasó la fecha límite, solo se acepta como tardía


class SituacionAcademica(Salida):
    materias_aprobadas: int
    materias_reprobadas: int
    creditos_aprobados: int
    promedio_general: float | None
