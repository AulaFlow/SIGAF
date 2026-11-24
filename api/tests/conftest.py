"""Fixtures compartidas. bd_real solo se usa en las pruebas de integración,
que se omiten si no hay SIGAF_PASS_API (así el CI no necesita base)."""

import os
from collections.abc import Iterator

import pytest

from app.config import Configuracion
from app.datos.postgres import BaseDeDatos, crear_pool

HAY_BASE = bool(os.environ.get("SIGAF_PASS_API"))
solo_con_base = pytest.mark.skipif(not HAY_BASE, reason="sin SIGAF_PASS_API: se omite la base real")


class Revertir(Exception):
    """Se lanza a propósito al final de una prueba para forzar el rollback."""


@pytest.fixture(scope="session")
def bd_real() -> Iterator[BaseDeDatos]:
    config = Configuracion.desde_entorno()
    pool = crear_pool(config)
    pool.open(wait=True, timeout=10)
    try:
        yield BaseDeDatos(config, pool)
    finally:
        pool.close()
