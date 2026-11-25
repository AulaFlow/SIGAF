"""Qué se copia a cada fragmento y en qué orden (issue #8).

Reparto del equipo (decisión 5, 2ª entrega):
    Fragmento A: CCB (1), CCA (3), CCSH (5)
    Fragmento B: CCEA (2), CCS (4), CCDC (6)

Hay dos tipos de tablas:

* **Replicadas**: catálogos que los dos fragmentos necesitan (roles, usuarios,
  centros, carreras, periodos, materias y avisos generales). Se copian completas.
* **Fragmentadas** por ``centro_academico_id`` (fragmentación horizontal
  derivada): cada fila vive SOLO en el fragmento de su centro.

La mensajería (conversacion, participante_conversacion, mensaje) quedó fuera
del alcance del proyecto, así que se queda en el fragmento A.
"""

from __future__ import annotations

from dataclasses import dataclass

CENTROS_A: tuple[int, ...] = (1, 3, 5)
CENTROS_B: tuple[int, ...] = (2, 4, 6)

# Subconsultas reutilizadas. {c} se reemplaza por la lista de centros.
# (Son constantes del programa: ningún texto viene del usuario, por eso los
# "nosec" de bandit en las líneas que arman SQL.)
_GRUPOS = "SELECT grupo_id FROM sigaf.grupo WHERE centro_academico_id = ANY({c})"
_INSCRIPCIONES = "SELECT inscripcion_id FROM sigaf.inscripcion WHERE centro_academico_id = ANY({c})"
_ALUMNOS = ("SELECT a.alumno_id FROM sigaf.alumno a JOIN sigaf.carrera ca USING (carrera_id) "
            "WHERE ca.centro_academico_id = ANY({c})")
_EXAMENES = f"SELECT examen_id FROM sigaf.examen WHERE grupo_id IN ({_GRUPOS})"  # nosec B608
_PREGUNTAS = f"SELECT pregunta_id FROM sigaf.pregunta WHERE examen_id IN ({_EXAMENES})"  # nosec B608
_INTENTOS = f"SELECT intento_id FROM sigaf.intento_examen WHERE inscripcion_id IN ({_INSCRIPCIONES})"  # nosec B608
_USUARIOS_DEL_CENTRO = (
    "SELECT a.usuario_id FROM sigaf.alumno a JOIN sigaf.carrera ca USING (carrera_id) "
    "WHERE ca.centro_academico_id = ANY({c}) "
    "UNION SELECT usuario_id FROM sigaf.profesor WHERE centro_academico_id = ANY({c})"
)


@dataclass(frozen=True)
class Regla:
    """Una tabla (o parte de ella) y el filtro que decide qué filas se mueven."""

    tabla: str
    filtro: str | None = None      # None = la tabla completa
    replicada: bool = False        # True = queda en los dos fragmentos

    @property
    def nombre(self) -> str:
        """Para el reporte: distingue los avisos generales de los de grupo."""
        return f"{self.tabla} (generales)" if self.replicada and self.filtro else self.tabla

    def where(self, centros: str) -> str:
        """Cláusula WHERE con la lista de centros ya puesta (o cadena vacía)."""
        return "" if self.filtro is None else " WHERE " + self.filtro.format(c=centros)


REPLICADAS: tuple[Regla, ...] = (
    Regla("rol", replicada=True),
    Regla("usuario", replicada=True),
    Regla("centro_academico", replicada=True),
    Regla("carrera", replicada=True),
    Regla("periodo", replicada=True),
    Regla("materia", replicada=True),
    Regla("aviso", "grupo_id IS NULL", replicada=True),     # avisos generales
)

# Orden de COPIA: primero los padres, luego los hijos (por las llaves foráneas).
# tarea va antes que inscripcion a propósito: así el trigger trg_tarea_notificar
# no inventa notificaciones nuevas en B; las originales se copian al final.
FRAGMENTADAS: tuple[Regla, ...] = (
    Regla("profesor", "centro_academico_id = ANY({c})"),
    Regla("alumno", f"alumno_id IN ({_ALUMNOS})"),
    Regla("alumno_datos_personales", f"alumno_id IN ({_ALUMNOS})"),
    Regla("grupo", "centro_academico_id = ANY({c})"),
    Regla("horario", f"grupo_id IN ({_GRUPOS})"),
    Regla("tarea", f"grupo_id IN ({_GRUPOS})"),
    Regla("examen", f"grupo_id IN ({_GRUPOS})"),
    Regla("pregunta", f"examen_id IN ({_EXAMENES})"),
    Regla("opcion", f"pregunta_id IN ({_PREGUNTAS})"),
    Regla("inscripcion", "centro_academico_id = ANY({c})"),
    Regla("intento_examen", f"inscripcion_id IN ({_INSCRIPCIONES})"),
    Regla("respuesta", f"intento_id IN ({_INTENTOS})"),
    Regla("calificacion", "centro_academico_id = ANY({c})"),
    Regla("bitacora_calificacion", f"inscripcion_id IN ({_INSCRIPCIONES})"),
    Regla("entrega", "centro_academico_id = ANY({c})"),
    Regla("asistencia", "centro_academico_id = ANY({c})"),
    Regla("aviso", f"grupo_id IN ({_GRUPOS})"),
    Regla("notificacion", f"usuario_id IN ({_USUARIOS_DEL_CENTRO})"),
)

ORDEN_COPIA: tuple[Regla, ...] = REPLICADAS + FRAGMENTADAS


def _orden_borrado() -> tuple[Regla, ...]:
    """Al borrar se va al revés (hijos primero), con una excepción:
    borrar una calificación hace que el trigger de bitácora escriba una fila
    'D'. Por eso la bitácora se borra DESPUÉS de las calificaciones (y antes
    que las inscripciones, que usa su filtro)."""
    orden = [r for r in reversed(FRAGMENTADAS) if r.tabla != "bitacora_calificacion"]
    bitacora = next(r for r in FRAGMENTADAS if r.tabla == "bitacora_calificacion")
    orden.insert(orden.index(next(r for r in orden if r.tabla == "calificacion")) + 1, bitacora)
    return tuple(orden)


ORDEN_BORRADO: tuple[Regla, ...] = _orden_borrado()

# Se quedan solo en A (módulo de Mensajería fuera del alcance).
SOLO_EN_A: tuple[str, ...] = ("conversacion", "participante_conversacion", "mensaje")

# Al crear filas nuevas, B usa ids desde aquí para no chocar con los de A
# (si chocaran, el ETL a MongoDB mezclaría registros de los dos fragmentos).
INICIO_IDS_B = 1_000_000_000


def tablas_cubiertas() -> set[str]:
    return {r.tabla for r in ORDEN_COPIA} | set(SOLO_EN_A) | {"directorio_fragmento"}
