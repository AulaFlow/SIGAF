"""Configuración de la API, leída SOLO de variables de entorno.

Ninguna contraseña ni llave vive en el código (Lineamientos IV-e.2). Si falta
algo obligatorio, la API no arranca: es mejor fallar al inicio que a media
petición. Ver .env.example para la lista de variables.

La API siempre entra como sigaf_api_svc (cuenta de servicio con mínimo
privilegio) y SIEMPRE con TLS: decisión del equipo, también en desarrollo.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from psycopg.conninfo import make_conninfo

USUARIO_API = "sigaf_api_svc"
LARGO_MINIMO_LLAVE = 32
LARGO_MINIMO_CONTRASENA = 12          # el mismo mínimo que exige db/06_credenciales.sql
SSLMODES_PERMITIDOS = ("require", "verify-ca", "verify-full")   # nunca disable/allow/prefer


class ConfiguracionError(RuntimeError):
    """Falta o es inválida una variable de entorno obligatoria."""


@dataclass(frozen=True)
class Configuracion:
    db_host: str
    db_puerto: int
    db_nombre: str
    db_contrasena: str = field(repr=False)
    db_sslmode: str
    db_sslrootcert: str | None
    db_pool_max: int
    llave_datos: str = field(repr=False)
    llave_seudonimo: str = field(repr=False)
    mongo_uri: str = field(repr=False)
    mongo_db: str
    origenes_cors: tuple[str, ...]

    @property
    def dsn(self) -> str:
        """Cadena de conexión. make_conninfo pone las comillas, así una contraseña
        con espacios o comillas no puede romper ni 'comerse' el sslmode."""
        extra = {"sslrootcert": self.db_sslrootcert} if self.db_sslrootcert else {}
        return make_conninfo(
            host=self.db_host,
            port=self.db_puerto,
            dbname=self.db_nombre,
            user=USUARIO_API,
            password=self.db_contrasena,
            sslmode=self.db_sslmode,
            application_name="sigaf_api",
            **extra,
        )

    @classmethod
    def desde_entorno(cls, entorno: Mapping[str, str] | None = None) -> Configuracion:
        env = os.environ if entorno is None else entorno

        def leer(nombre: str, defecto: str = "") -> str:
            return env.get(nombre, "").strip() or defecto

        obligatorias = ("SIGAF_PASS_API", "SIGAF_LLAVE_DATOS", "SIGAF_LLAVE_SEUDONIMO")
        faltan = [nombre for nombre in obligatorias if not env.get(nombre)]
        if faltan:
            raise ConfiguracionError(f"Faltan variables de entorno: {', '.join(faltan)}")

        if len(env["SIGAF_PASS_API"]) < LARGO_MINIMO_CONTRASENA:
            raise ConfiguracionError(
                f"SIGAF_PASS_API debe tener al menos {LARGO_MINIMO_CONTRASENA} caracteres"
            )
        for nombre in ("SIGAF_LLAVE_DATOS", "SIGAF_LLAVE_SEUDONIMO"):
            if len(env[nombre]) < LARGO_MINIMO_LLAVE:
                raise ConfiguracionError(
                    f"{nombre} debe tener al menos {LARGO_MINIMO_LLAVE} caracteres"
                )

        sslmode = leer("SIGAF_DB_SSLMODE", "require")
        if sslmode not in SSLMODES_PERMITIDOS:
            raise ConfiguracionError(
                f"SIGAF_DB_SSLMODE debe ser {', '.join(SSLMODES_PERMITIDOS)} (TLS obligatorio)"
            )
        sslrootcert = leer("SIGAF_DB_SSLROOTCERT") or None
        if sslmode.startswith("verify") and sslrootcert is None:
            raise ConfiguracionError(f"sslmode={sslmode} necesita SIGAF_DB_SSLROOTCERT (ca.crt)")

        origenes = tuple(o.strip() for o in leer("SIGAF_CORS_ORIGENES").split(",") if o.strip())
        if "*" in origenes:
            raise ConfiguracionError("SIGAF_CORS_ORIGENES no puede ser '*': lista los orígenes")

        return cls(
            db_host=leer("SIGAF_DB_HOST", "localhost"),
            db_puerto=_entero(leer("SIGAF_DB_PORT", "5432"), "SIGAF_DB_PORT", 1, 65535),
            db_nombre=leer("SIGAF_DB_NOMBRE", "postgres"),
            db_contrasena=env["SIGAF_PASS_API"],
            db_sslmode=sslmode,
            db_sslrootcert=sslrootcert,
            db_pool_max=_entero(leer("SIGAF_DB_POOL_MAX", "10"), "SIGAF_DB_POOL_MAX", 1, 50),
            llave_datos=env["SIGAF_LLAVE_DATOS"],
            llave_seudonimo=env["SIGAF_LLAVE_SEUDONIMO"],
            mongo_uri=leer("SIGAF_MONGO_URI", "mongodb://localhost:27017"),
            mongo_db=leer("SIGAF_MONGO_DB", "sigaf_analitica"),
            origenes_cors=origenes,
        )


def _entero(texto: str, nombre: str, minimo: int, maximo: int) -> int:
    try:
        valor = int(texto)
    except ValueError:
        raise ConfiguracionError(f"{nombre} debe ser un número entero") from None
    if not minimo <= valor <= maximo:
        raise ConfiguracionError(f"{nombre} debe estar entre {minimo} y {maximo}")
    return valor
