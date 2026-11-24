from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.dominio.excepciones import CalificacionInvalidaError
from app.dominio.reglas import validar_calificacion
from app.esquemas.calificaciones import CalificacionNueva
from app.esquemas.entregas import CalificacionDeEntrega, EntregaNueva
from app.esquemas.inscripciones import InscripcionNueva, InscripcionPorAdmin
from app.esquemas.tareas import TareaNueva

MANANA = datetime.now(UTC) + timedelta(days=1)


# ---- reglas de dominio ----------------------------------------------------
@pytest.mark.parametrize("valor", ["0", "6", "9.5", "10", "7.25"])
def test_calificaciones_validas(valor):
    assert validar_calificacion(Decimal(valor)) == Decimal(valor)


@pytest.mark.parametrize("valor", ["-0.01", "10.01", "11", "NaN", "Infinity", "8.125"])
def test_calificaciones_invalidas(valor):
    with pytest.raises(CalificacionInvalidaError):
        validar_calificacion(Decimal(valor))


# ---- entregas -------------------------------------------------------------
def test_entrega_sin_archivo_es_valida():
    assert EntregaNueva().archivo_ruta is None


def test_entrega_con_archivo():
    e = EntregaNueva(archivo_ruta="entregas/4/practica.pdf", archivo_tamano_bytes=2048,
                     archivo_tipo="application/pdf")
    assert e.archivo_tamano_bytes == 2048


def test_entrega_no_acepta_entregada_en():
    # La fecha la pone la base: si el cliente la manda, se rechaza (extra="forbid").
    with pytest.raises(ValidationError, match="entregada_en"):
        EntregaNueva(entregada_en="2020-01-01T00:00:00Z")


def test_entrega_no_acepta_inscripcion_ni_alumno():
    with pytest.raises(ValidationError):
        EntregaNueva(inscripcion_id=1)
    with pytest.raises(ValidationError):
        EntregaNueva(alumno_id=1)


@pytest.mark.parametrize("ruta", ["/etc/passwd", "../../secreto", "a/../b", "a b.pdf", "x;rm"])
def test_ruta_insegura_rechazada(ruta):
    with pytest.raises(ValidationError):
        EntregaNueva(archivo_ruta=ruta, archivo_tamano_bytes=10)


def test_ruta_y_tamano_van_juntos():
    with pytest.raises(ValidationError, match="juntos"):
        EntregaNueva(archivo_ruta="a.pdf")
    with pytest.raises(ValidationError, match="juntos"):
        EntregaNueva(archivo_tamano_bytes=10)


def test_tamano_maximo_50_mb():
    with pytest.raises(ValidationError):
        EntregaNueva(archivo_ruta="a.pdf", archivo_tamano_bytes=52_428_801)


@pytest.mark.parametrize("tipo", ["application/pdf", "image/png", "application/vnd.ms-excel"])
def test_mime_valido(tipo):
    assert EntregaNueva(archivo_tipo=tipo).archivo_tipo == tipo


def test_mime_invalido():
    with pytest.raises(ValidationError):
        EntregaNueva(archivo_tipo="<script>")


# ---- inyección NoSQL / tipos estrictos -------------------------------------
@pytest.mark.parametrize("valor", [{"$gt": 0}, "5", 0, -3, 2**63, True])
def test_ids_estrictos(valor):
    with pytest.raises(ValidationError):
        InscripcionNueva(grupo_id=valor)


def test_alumno_no_puede_mandar_alumno_id():
    with pytest.raises(ValidationError, match="alumno_id"):
        InscripcionNueva(grupo_id=3, alumno_id=9)
    assert InscripcionPorAdmin(grupo_id=3, alumno_id=9).alumno_id == 9


def test_texto_no_acepta_objetos():
    with pytest.raises(ValidationError):
        TareaNueva(titulo={"$ne": ""}, fecha_limite=MANANA)


# ---- tareas ---------------------------------------------------------------
def test_tarea_margen_opcional():
    t = TareaNueva(titulo="  Práctica 1  ", fecha_limite=MANANA)
    assert t.margen_tardia_horas is None          # la base pondrá 48 h
    assert t.titulo == "Práctica 1"               # se quitan espacios


def test_tarea_margen_cero_permitido():
    tarea = TareaNueva(titulo="P", fecha_limite=MANANA, margen_tardia_horas=0)
    assert tarea.margen_tardia_horas == 0


@pytest.mark.parametrize("margen", [-1, 8761])
def test_tarea_margen_fuera_de_rango(margen):
    with pytest.raises(ValidationError):
        TareaNueva(titulo="P", fecha_limite=MANANA, margen_tardia_horas=margen)


def test_tarea_fecha_sin_zona_horaria_rechazada():
    with pytest.raises(ValidationError):
        TareaNueva(titulo="P", fecha_limite=datetime(2026, 12, 1, 10, 0))


def test_tarea_titulo_vacio_rechazado():
    with pytest.raises(ValidationError):
        TareaNueva(titulo="   ", fecha_limite=MANANA)


# ---- calificaciones -------------------------------------------------------
def test_calificacion_valida():
    c = CalificacionNueva(inscripcion_id=1, tipo="parcial2", valor="8.5")
    assert c.valor == Decimal("8.5")


@pytest.mark.parametrize("valor", ["10.5", "-1", "8.333"])
def test_calificacion_invalida_da_error_de_validacion(valor):
    with pytest.raises(ValidationError, match="calificación"):
        CalificacionNueva(inscripcion_id=1, tipo="final", valor=valor)


def test_tipo_de_calificacion_cerrado():
    with pytest.raises(ValidationError):
        CalificacionNueva(inscripcion_id=1, tipo="extra", valor="8")


def test_calificacion_de_entrega():
    assert CalificacionDeEntrega(calificacion="9").calificacion == Decimal("9")
    with pytest.raises(ValidationError):
        CalificacionDeEntrega(calificacion="12")
