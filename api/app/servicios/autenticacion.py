"""Inicio de sesión (issue #11): correo + contraseña -> token JWT.

Pasos de iniciar_sesion():
    1. Busca al usuario por correo (transacción corta).
    2. Compara la contraseña con bcrypt FUERA de la transacción: tarda ~200 ms a
       propósito y no queremos tener una conexión del pool ocupada mientras tanto.
    3. Si todo cuadra, busca su alumno_id o profesor_id y su centro (en A o en B).
    4. Anota el intento en bitacora_acceso, salga bien o mal.
    5. Regresa el token, o lanza CredencialesInvalidasError (siempre la misma).

Dos cuidados de seguridad:
    - Mismo error para todo: correo inexistente, contraseña mala, cuenta inactiva o
      hash dañado responden igual. El motivo real solo va a la bitácora.
    - Mismo tiempo para todo: si no hay hash bcrypt contra el cual comparar (correo
      inexistente, cuentas sintéticas 'sintetico$...'), se compara contra HASH_FALSO.
      Si no, responder más rápido delataría qué correos existen.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import bcrypt
import psycopg

from ..config import Configuracion
from ..datos.postgres import BaseDeDatos
from ..dominio.excepciones import CredencialesInvalidasError
from ..dominio.personas import Administrador, Alumno, Persona, Profesor, Rol
from ..repositorios.usuarios import RepositorioUsuarios
from ..seguridad import crear_token

MENSAJE = "Correo o contraseña incorrectos"

# Formato de un hash bcrypt: $2b$12$ + 53 caracteres (22 de sal y 31 del hash).
# Lo que no lo cumpla (p. ej. 'sintetico$...' del generador) NO se le pasa a
# bcrypt.checkpw, que lanzaría ValueError y la API respondería 500.
PATRON_BCRYPT = re.compile(r"\$2[aby]\$(0[4-9]|[12][0-9]|3[01])\$[./A-Za-z0-9]{53}")

# bcrypt solo usa los primeros 72 bytes y la versión 5 lanza ValueError si hay más.
MAX_BYTES_CONTRASENA = 72

# Hash de una contraseña aleatoria que nadie conoce, con el mismo costo (12) que los
# reales. Solo sirve para gastar el mismo tiempo cuando no hay hash real.
HASH_FALSO = b"$2b$12$kdbS2UMGlsz9rYeBhkRw2O9Hc5cnNDndChV0slR7sbKHTBNUWLx3S"


class Motivo(StrEnum):
    """Los mismos valores que el CHECK de bitacora_acceso.motivo (db/09)."""

    OK = "ok"
    SIN_USUARIO = "sin_usuario"
    CONTRASENA = "contrasena"
    INACTIVO = "inactivo"
    HASH_INVALIDO = "hash_invalido"


@dataclass(frozen=True)
class Sesion:
    token: str
    expira_en: int          # segundos
    persona: Persona


def es_hash_bcrypt(texto: str | None) -> bool:
    return texto is not None and PATRON_BCRYPT.fullmatch(texto) is not None


def comparar(contrasena: str, hash_guardado: str | None) -> Motivo:
    """Compara con bcrypt y dice qué pasó. Siempre gasta un checkpw; nunca lanza."""
    clave = contrasena.encode()
    hash_real = es_hash_bcrypt(hash_guardado)
    objetivo = hash_guardado.encode() if hash_real else HASH_FALSO   # type: ignore[union-attr]
    try:
        coincide = bcrypt.checkpw(clave[:MAX_BYTES_CONTRASENA], objetivo)
    except ValueError:      # pasó el patrón pero bcrypt no lo acepta: hash dañado
        return Motivo.HASH_INVALIDO
    if hash_guardado is None:
        return Motivo.SIN_USUARIO
    if not hash_real:
        return Motivo.HASH_INVALIDO
    # Más de 72 bytes: se comparó lo mismo que con 72 (mismo tiempo) pero se rechaza,
    # para que dos contraseñas distintas no cuenten como la misma.
    if not coincide or len(clave) > MAX_BYTES_CONTRASENA:
        return Motivo.CONTRASENA
    return Motivo.OK


def ip_valida(ip: str | None) -> str | None:
    """La columna es INET: algo que no sea IP (p. ej. 'testclient') se guarda como NULL."""
    if ip is None:
        return None
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None


class ServicioAutenticacion:
    def __init__(self, bd: BaseDeDatos, config: Configuracion) -> None:
        self._bd = bd
        self._config = config

    def iniciar_sesion(self, correo: str, contrasena: str, ip: str | None = None) -> Sesion:
        with self._bd.transaccion() as cur:      # usuario está replicado: cualquier fragmento
            usuario = RepositorioUsuarios(cur).por_correo(correo)

        motivo = comparar(contrasena, usuario["hash_contrasena"] if usuario else None)
        if motivo is Motivo.OK and not usuario["activo"]:   # type: ignore[index]
            motivo = Motivo.INACTIVO
        persona = self._persona(usuario) if motivo is Motivo.OK else None

        # La bitácora va antes de responder: sin rastro no hay sesión. Si no se puede
        # escribir, el error se propaga (500) y nadie entra sin quedar registrado.
        self._registrar(usuario["usuario_id"] if usuario else None, motivo, ip)

        if persona is None:
            raise CredencialesInvalidasError(MENSAJE)
        minutos = self._config.jwt_minutos
        return Sesion(crear_token(persona, self._config.jwt_llave, minutos), minutos * 60,
                      persona)

    def _persona(self, usuario: dict) -> Persona:
        """Arma la Persona con datos de la base. El rol sale de la base, nunca del cliente."""
        usuario_id, correo = usuario["usuario_id"], usuario["correo"]
        match Rol(usuario["rol"]):
            case Rol.ADMINISTRADOR:
                return Administrador(usuario_id, correo)
            case Rol.ALUMNO:
                fila = self._unico(lambda cur: RepositorioUsuarios(cur).alumno_de(usuario_id),
                                   usuario_id)
                return Alumno(usuario_id, correo, fila["alumno_id"], fila["centro_academico_id"])
            case Rol.PROFESOR:
                fila = self._unico(lambda cur: RepositorioUsuarios(cur).profesor_de(usuario_id),
                                   usuario_id)
                return Profesor(usuario_id, correo, fila["profesor_id"],
                                fila["centro_academico_id"])

    def _unico(self, consulta: Callable[[psycopg.Cursor], list[dict]], usuario_id: int) -> dict:
        """alumno/profesor están fragmentados: se pregunta en A y en B (o en la única base)."""
        filas = self._bd.en_todos(consulta)
        if len(filas) != 1:
            # Rol alumno sin renglón en alumno (o en dos fragmentos): error de datos,
            # no de credenciales. Que sea un 500 visible en el log, no un 401 confuso.
            raise RuntimeError(
                f"El usuario {usuario_id} tiene {len(filas)} perfiles para su rol"
            )
        return filas[0]

    def _registrar(self, usuario_id: int | None, motivo: Motivo, ip: str | None) -> None:
        with self._bd.transaccion() as cur:
            RepositorioUsuarios(cur).registrar_acceso(
                usuario_id, motivo is Motivo.OK, motivo.value, ip_valida(ip)
            )
