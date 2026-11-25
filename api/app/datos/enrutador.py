"""Enrutador por centro académico (issue #6).

La base está partida en dos fragmentos por centro_academico_id (la shard key):
    A = CCB, CCSH, CCA      B = CCEA, CCS, CCDC      (reparto provisional, issue #4)

El reparto NO está escrito aquí: se lee de la tabla directorio_fragmento al
arrancar la API. Si el equipo cambia el reparto, solo se actualiza la tabla.

Reglas (decisión del equipo, CAP: CP en lo académico):
    - con centro      -> primario del fragmento de ese centro (lee y escribe)
    - sin centro      -> catálogos replicados: cualquier fragmento sirve, se usa el primero
    - "de todos"      -> en_todos(): corre la consulta en cada fragmento y junta resultados
Las réplicas no se usan para escribir; quedan como respaldo (failover en el issue #9).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any, TypeVar

import psycopg

from ..config import Configuracion
from ..dominio.personas import Persona
from .postgres import BaseDeDatos, FuenteDeConexiones

T = TypeVar("T")

SQL_DIRECTORIO = (
    "SELECT centro_academico_id, fragmento, host_primario, host_replica "
    "FROM sigaf.directorio_fragmento ORDER BY centro_academico_id"
)


class CentroDesconocidoError(LookupError):
    """El centro no aparece en directorio_fragmento: no sabemos a qué fragmento va."""

    def __init__(self, centro_academico_id: int) -> None:
        super().__init__(f"El centro {centro_academico_id} no está en directorio_fragmento")
        self.centro_academico_id = centro_academico_id


class DirectorioInvalidoError(ValueError):
    """directorio_fragmento tiene datos que no cuadran (p. ej. un fragmento con dos primarios)."""


@dataclass(frozen=True)
class Nodo:
    """Dirección de una base, como viene en directorio_fragmento: 'host:puerto'."""

    host: str
    puerto: int

    @classmethod
    def desde_texto(cls, texto: str) -> Nodo:
        host, separador, puerto = texto.strip().rpartition(":")
        if not separador or not host:
            return cls(texto.strip(), 5432)          # sin puerto: el de siempre
        if not puerto.isdigit() or not 1 <= int(puerto) <= 65535:
            raise DirectorioInvalidoError(f"Puerto inválido en '{texto}'")
        return cls(host, int(puerto))


@dataclass(frozen=True)
class Fragmento:
    nombre: str                      # 'A' o 'B'
    primario: Nodo
    replica: Nodo
    centros: tuple[int, ...]


def armar_fragmentos(filas: list[tuple[Any, ...]]) -> dict[str, Fragmento]:
    centros: dict[str, list[int]] = {}
    nodos: dict[str, tuple[str, str]] = {}
    for centro_id, fragmento, host_primario, host_replica in filas:
        nombre = str(fragmento).strip()
        par = (host_primario.strip(), host_replica.strip())
        if nodos.setdefault(nombre, par) != par:
            raise DirectorioInvalidoError(
                f"El fragmento {nombre} tiene más de un primario/réplica en el directorio"
            )
        centros.setdefault(nombre, []).append(int(centro_id))
    return {
        nombre: Fragmento(
            nombre=nombre,
            primario=Nodo.desde_texto(nodos[nombre][0]),
            replica=Nodo.desde_texto(nodos[nombre][1]),
            centros=tuple(centros[nombre]),
        )
        for nombre in sorted(centros)
    }


class Enrutador:
    """Sabe a qué fragmento va cada centro y qué pool usar para cada fragmento."""

    def __init__(
        self, fragmentos: Mapping[str, Fragmento], pools: Mapping[str, FuenteDeConexiones]
    ) -> None:
        if not fragmentos:
            raise DirectorioInvalidoError("directorio_fragmento está vacío")
        faltan = set(fragmentos) - set(pools)
        if faltan:
            raise DirectorioInvalidoError(f"Falta el pool de: {', '.join(sorted(faltan))}")
        self.fragmentos = dict(fragmentos)
        self._pools = dict(pools)
        self._centro_a_fragmento = {
            centro: f.nombre for f in self.fragmentos.values() for centro in f.centros
        }

    def fragmento_de(self, centro_academico_id: int) -> str:
        try:
            return self._centro_a_fragmento[centro_academico_id]
        except KeyError:
            raise CentroDesconocidoError(centro_academico_id) from None

    def pool_para(self, centro_academico_id: int | None = None) -> FuenteDeConexiones:
        if centro_academico_id is None:
            return self._pools[self.nombres()[0]]   # catálogos replicados: cualquiera sirve
        return self._pools[self.fragmento_de(centro_academico_id)]

    def nombres(self) -> list[str]:
        return sorted(self.fragmentos)


class BaseDistribuida(BaseDeDatos):
    """BaseDeDatos que elige el fragmento según el centro (usa el enchufe pool_para)."""

    def __init__(self, config: Configuracion, enrutador: Enrutador) -> None:
        super().__init__(config, enrutador.pool_para(None))
        self.enrutador = enrutador

    def pool_para(self, centro_academico_id: int | None = None) -> FuenteDeConexiones:
        return self.enrutador.pool_para(centro_academico_id)

    @contextmanager
    def transaccion_en_fragmento(
        self, fragmento: str, persona: Persona | None = None
    ) -> Iterator[psycopg.Cursor]:
        """Una transacción en un fragmento concreto (la usa en_todos)."""
        centro = self.enrutador.fragmentos[fragmento].centros[0]
        with self.transaccion(persona, centro_academico_id=centro) as cur:
            yield cur

    def en_todos(
        self, consulta: Callable[[psycopg.Cursor], list[T]], persona: Persona | None = None
    ) -> list[T]:
        """Corre la misma consulta en cada fragmento y junta los resultados (A y luego B).

        Cada fragmento va en su propia transacción: si uno falla, se lanza el error
        y no se regresan resultados a medias.
        """
        resultados: list[T] = []
        for nombre in self.enrutador.nombres():
            with self.transaccion_en_fragmento(nombre, persona) as cur:
                resultados.extend(consulta(cur))
        return resultados


def crear_base_distribuida(
    config: Configuracion,
    pool_inicial: FuenteDeConexiones,
    fabrica_pool: Callable[[Configuracion], Any],
    abrir: Callable[[Any], None],
) -> tuple[BaseDeDatos, list[Any]]:
    """Arma la base al arrancar la API.

    1. Con el pool inicial (SIGAF_DB_HOST) lee directorio_fragmento.
    2. Abre un pool al primario de cada fragmento.
    Si el directorio está vacío (base recién creada), se queda con un solo pool,
    así la API sigue funcionando en desarrollo.

    Regresa la base y los pools nuevos que hay que cerrar al apagar.
    """
    conexion = pool_inicial.getconn()
    try:
        with conexion.cursor() as cur:
            cur.execute(SQL_DIRECTORIO)
            filas = cur.fetchall()
        conexion.commit()
    finally:
        pool_inicial.putconn(conexion)

    if not filas:
        return BaseDeDatos(config, pool_inicial), []

    fragmentos = armar_fragmentos(filas)
    pools: dict[str, Any] = {}
    for nombre, fragmento in fragmentos.items():
        nodo = fragmento.primario
        if (nodo.host, nodo.puerto) == (config.db_host, config.db_puerto):
            pools[nombre] = pool_inicial                 # ya está abierto, se reutiliza
            continue
        pool = fabrica_pool(replace(config, db_host=nodo.host, db_puerto=nodo.puerto))
        abrir(pool)
        pools[nombre] = pool
    nuevos = [p for p in pools.values() if p is not pool_inicial]
    return BaseDistribuida(config, Enrutador(fragmentos, pools)), nuevos
