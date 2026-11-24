"""Lectura y limpieza con pandas de los CSV de alumnos y calificaciones.

Cada función de limpieza devuelve el DataFrame limpio y un ``Reporte`` con
lo que se corrigió y lo que se descartó (y por qué), para dejar evidencia.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from .excepciones import ArchivoInvalidoError, CalificacionInvalidaError

COLUMNAS_ALUMNOS = ["matricula", "nombre", "apellidos", "carrera", "semestre"]
COLUMNAS_CALIFICACIONES = ["matricula", "materia", "periodo", "tipo", "valor"]

PATRON_MATRICULA = re.compile(r"^[A-Z]?\d{6,7}$")   # p. ej. 479329 o A000001

# Formas en que llega el tipo de calificación -> valor que acepta la base
TIPOS = {
    "parcial1": "parcial1", "parcial 1": "parcial1", "p1": "parcial1", "1er parcial": "parcial1",
    "parcial2": "parcial2", "parcial 2": "parcial2", "p2": "parcial2", "2do parcial": "parcial2",
    "parcial3": "parcial3", "parcial 3": "parcial3", "p3": "parcial3", "3er parcial": "parcial3",
    "final": "final", "ordinario": "final", "f": "final",
}


@dataclass
class Reporte:
    """Resumen de lo que hizo la limpieza de un archivo."""

    archivo: str
    filas_leidas: int = 0
    filas_validas: int = 0
    correcciones: dict[str, int] = field(default_factory=dict)
    descartes: list[dict[str, object]] = field(default_factory=list)

    def corregir(self, motivo: str, cuantas: int = 1) -> None:
        if cuantas:
            self.correcciones[motivo] = self.correcciones.get(motivo, 0) + int(cuantas)

    def descartar(self, fila: int, motivo: str) -> None:
        # Solo se guarda el número de fila y el motivo: el reporte no debe
        # contener datos personales.
        self.descartes.append({"fila": int(fila), "motivo": motivo})

    def a_dict(self) -> dict[str, object]:
        return asdict(self)


def leer_csv(ruta: str | Path, columnas: list[str]) -> pd.DataFrame:
    """Lee un CSV como texto y valida que traiga las columnas obligatorias."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ArchivoInvalidoError(str(ruta), "no existe")
    try:
        with ruta.open(encoding="utf-8-sig", newline="") as archivo:
            df = pd.read_csv(archivo, dtype=str, keep_default_na=False, skipinitialspace=True)
    except pd.errors.EmptyDataError as e:
        raise ArchivoInvalidoError(str(ruta), "está vacío") from e
    except UnicodeDecodeError as e:
        raise ArchivoInvalidoError(str(ruta), "no está en UTF-8") from e

    df.columns = [normalizar_texto(c).replace(" ", "_") for c in df.columns]
    faltan = [c for c in columnas if c not in df.columns]
    if faltan:
        raise ArchivoInvalidoError(str(ruta), f"faltan columnas {faltan}")
    df = df[columnas].copy()
    df.index = df.index + 2   # número de fila como se ve en Excel (fila 1 = encabezado)
    return df


def normalizar_texto(texto: str) -> str:
    """Minúsculas, sin acentos y sin espacios repetidos (para comparar)."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()


def normalizar_matricula(valor: str) -> str:
    """Quita espacios y guiones, y pasa a mayúsculas: ' a-000001 ' -> 'A000001'."""
    return re.sub(r"[\s\-_.]", "", str(valor)).upper()


def nombre_propio(valor: str) -> str:
    """'  pérez   LUNA ' -> 'Pérez Luna' (conserva acentos y partículas en minúscula)."""
    palabras = re.sub(r"\s+", " ", str(valor)).strip().split(" ")
    particulas = {"de", "del", "la", "las", "los", "y"}
    return " ".join(
        p.lower() if i and p.lower() in particulas else p[:1].upper() + p[1:].lower()
        for i, p in enumerate(palabras) if p
    )


def convertir_calificacion(valor: object) -> tuple[float, bool]:
    """Convierte una calificación a escala 0-10.

    Acepta coma decimal ('8,5') y escala 0-100 cuando el valor es un ENTERO
    de 11 a 100 ('85' -> 8.5). Un decimal mayor a 10 ('11.5') se considera
    error de captura y se rechaza. Devuelve el valor y si hubo que convertir
    la escala. Lanza CalificacionInvalidaError si no es número o está fuera
    de rango.
    """
    texto = str(valor).strip().replace(",", ".")
    try:
        numero = float(texto)
    except ValueError as e:
        raise CalificacionInvalidaError(valor) from e
    if math.isnan(numero):
        raise CalificacionInvalidaError(valor)
    escala_100 = 10 < numero <= 100 and numero.is_integer()
    if escala_100:
        numero /= 10
    if not 0 <= numero <= 10:
        raise CalificacionInvalidaError(valor)
    return round(numero, 2), escala_100


def limpiar_alumnos(df: pd.DataFrame, archivo: str = "alumnos") -> tuple[pd.DataFrame, Reporte]:
    """Limpia la lista de alumnos.

    - Matrícula: sin espacios ni guiones y en mayúsculas; se descarta si el
      formato no es válido.
    - Nombre y apellidos: espacios y mayúsculas corregidos; se descarta si faltan.
    - Carrera: clave en mayúsculas.
    - Semestre: número de 1 a 12.
    - Duplicados por matrícula: se queda la última aparición.
    """
    rep = Reporte(archivo=archivo, filas_leidas=len(df))
    df = df.copy()

    original = df["matricula"]
    df["matricula"] = original.map(normalizar_matricula)
    rep.corregir("matrícula con espacios, guiones o minúsculas", int((original != df["matricula"]).sum()))

    for col in ("nombre", "apellidos"):
        antes = df[col]
        df[col] = antes.map(nombre_propio)
        rep.corregir(f"{col} con espacios o mayúsculas incorrectas", int((antes != df[col]).sum()))

    antes = df["carrera"]
    df["carrera"] = antes.str.strip().str.upper()
    rep.corregir("carrera en minúsculas o con espacios", int((antes != df["carrera"]).sum()))

    df["semestre"] = pd.to_numeric(df["semestre"].str.strip(), errors="coerce")

    validas = []
    for fila, r in df.iterrows():
        if not PATRON_MATRICULA.match(r["matricula"]):
            rep.descartar(fila, "matrícula con formato inválido")
        elif not r["nombre"] or not r["apellidos"]:
            rep.descartar(fila, "falta nombre o apellidos")
        elif not r["carrera"]:
            rep.descartar(fila, "falta la carrera")
        elif pd.isna(r["semestre"]) or not 1 <= r["semestre"] <= 12 or r["semestre"] % 1:
            rep.descartar(fila, "semestre fuera de 1 a 12")
        else:
            validas.append(fila)
    df = df.loc[validas]

    duplicadas = df.duplicated(subset="matricula", keep="last")
    for fila in df.index[duplicadas]:
        rep.descartar(fila, "matrícula duplicada (se conserva la última)")
    df = df[~duplicadas].astype({"semestre": int})

    rep.filas_validas = len(df)
    return df, rep


def limpiar_calificaciones(df: pd.DataFrame, archivo: str = "calificaciones") -> tuple[pd.DataFrame, Reporte]:
    """Limpia las calificaciones.

    - Matrícula normalizada igual que en alumnos.
    - Materia y periodo: claves en mayúsculas sin espacios.
    - Tipo: 'Parcial 1', 'P1', '1er parcial' -> 'parcial1'; 'Ordinario' -> 'final'.
    - Valor: coma decimal y escala 0-100 se convierten; lo demás se descarta.
    - Duplicados (misma matrícula, materia, periodo y tipo): se queda la última.
    """
    rep = Reporte(archivo=archivo, filas_leidas=len(df))
    df = df.copy()

    original = df["matricula"]
    df["matricula"] = original.map(normalizar_matricula)
    rep.corregir("matrícula con espacios, guiones o minúsculas", int((original != df["matricula"]).sum()))
    for col in ("materia", "periodo"):
        antes = df[col]
        df[col] = antes.str.replace(r"\s+", "", regex=True).str.upper()
        rep.corregir(f"{col} con espacios o minúsculas", int((antes != df[col]).sum()))

    tipos, valores, validas = [], [], []
    for fila, r in df.iterrows():
        tipo = TIPOS.get(normalizar_texto(r["tipo"]))
        if not PATRON_MATRICULA.match(r["matricula"]):
            rep.descartar(fila, "matrícula con formato inválido")
            continue
        if not r["materia"] or not r["periodo"]:
            rep.descartar(fila, "falta materia o periodo")
            continue
        if tipo is None:
            rep.descartar(fila, "tipo de calificación desconocido")
            continue
        try:
            valor, escala_100 = convertir_calificacion(r["valor"])
        except CalificacionInvalidaError:
            rep.descartar(fila, "calificación no numérica o fuera de rango")
            continue
        else:
            if tipo != r["tipo"]:
                rep.corregir("tipo escrito de otra forma")
            if escala_100:
                rep.corregir("calificación en escala 0-100 convertida a 0-10")
            elif "," in str(r["valor"]):
                rep.corregir("calificación con coma decimal")
        tipos.append(tipo)
        valores.append(valor)
        validas.append(fila)

    df = df.loc[validas].copy()
    df["tipo"] = tipos
    df["valor"] = valores

    llave = ["matricula", "materia", "periodo", "tipo"]
    duplicadas = df.duplicated(subset=llave, keep="last")
    for fila in df.index[duplicadas]:
        rep.descartar(fila, "calificación repetida (se conserva la última)")
    df = df[~duplicadas]

    rep.filas_validas = len(df)
    return df, rep


def guardar_reporte(reportes: list[Reporte], ruta: str | Path) -> None:
    """Escribe los reportes en JSON (evidencia de la limpieza)."""
    with Path(ruta).open("w", encoding="utf-8") as archivo:
        json.dump([r.a_dict() for r in reportes], archivo, ensure_ascii=False, indent=2)
