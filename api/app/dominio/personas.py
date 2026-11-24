"""Personas del sistema: Persona es la base abstracta de Alumno, Profesor y
Administrador (herencia y polimorfismo, como sugirió el profe de Python).

El identificador de cada persona (alumno_id, profesor_id) sale SIEMPRE del
usuario autenticado, nunca de la petición. Por eso estas clases se crean en
la capa de seguridad y los servicios las reciben ya construidas.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum


class Rol(StrEnum):
    ALUMNO = "alumno"
    PROFESOR = "profesor"
    ADMINISTRADOR = "administrador"


def _id_positivo(valor: int, nombre: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        raise ValueError(f"{nombre} debe ser un entero positivo")
    return valor


class Persona(ABC):
    """Cualquier usuario autenticado de SIGAF."""

    def __init__(self, usuario_id: int, correo: str) -> None:
        self._usuario_id = _id_positivo(usuario_id, "usuario_id")
        if "@" not in correo:
            raise ValueError("correo inválido")
        self._correo = correo

    @property
    def usuario_id(self) -> int:
        return self._usuario_id

    @property
    def correo(self) -> str:
        return self._correo

    @property
    @abstractmethod
    def rol(self) -> Rol:
        """Rol de la persona en el sistema."""

    def variables_de_sesion(self) -> dict[str, str]:
        """Variables que la API pone en la sesión de PostgreSQL con set_config.

        Por defecto ninguna; cada subclase agrega las suyas (polimorfismo).
        """
        return {}

    def es(self, *roles: Rol) -> bool:
        return self.rol in roles

    def __repr__(self) -> str:   # sin el correo: no exponer datos en logs
        return f"{type(self).__name__}(usuario_id={self._usuario_id})"


class Alumno(Persona):
    def __init__(self, usuario_id: int, correo: str, alumno_id: int) -> None:
        super().__init__(usuario_id, correo)
        self._alumno_id = _id_positivo(alumno_id, "alumno_id")

    @property
    def alumno_id(self) -> int:
        return self._alumno_id

    @property
    def rol(self) -> Rol:
        return Rol.ALUMNO

    def variables_de_sesion(self) -> dict[str, str]:
        # fn_mis_datos() lee esta variable: el alumno solo ve SUS datos.
        return {"sigaf.alumno_sesion": str(self._alumno_id)}


class Profesor(Persona):
    def __init__(self, usuario_id: int, correo: str, profesor_id: int) -> None:
        super().__init__(usuario_id, correo)
        self._profesor_id = _id_positivo(profesor_id, "profesor_id")

    @property
    def profesor_id(self) -> int:
        return self._profesor_id

    @property
    def rol(self) -> Rol:
        return Rol.PROFESOR


class Administrador(Persona):
    @property
    def rol(self) -> Rol:
        return Rol.ADMINISTRADOR
