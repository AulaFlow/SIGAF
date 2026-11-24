"""Excepciones propias del proceso de limpieza y carga."""


class LimpiezaError(Exception):
    """Error base del proceso de limpieza."""


class ArchivoInvalidoError(LimpiezaError):
    """El archivo no existe, está vacío o le faltan columnas obligatorias."""

    def __init__(self, ruta: str, motivo: str) -> None:
        super().__init__(f"{ruta}: {motivo}")
        self.ruta = ruta
        self.motivo = motivo


class CalificacionInvalidaError(LimpiezaError):
    """Una calificación no se puede interpretar como un número de 0 a 10."""

    def __init__(self, valor: object) -> None:
        super().__init__(f"Calificación inválida: {valor!r}")
        self.valor = valor


class CargaError(LimpiezaError):
    """La carga a la base falló; la transacción se revirtió completa."""
