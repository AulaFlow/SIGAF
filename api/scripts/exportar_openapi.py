"""Exporta el contrato de la API a api/openapi.json (para la app de Flutter, #10).

    cd api && python scripts/exportar_openapi.py

No necesita base de datos ni .env: solo arma la app para leer sus rutas.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.config import Configuracion  # noqa: E402
from app.main import crear_app  # noqa: E402

# Valores de relleno: la app no se conecta a nada para generar el esquema.
CONFIG_VACIA = Configuracion(
    db_host="localhost", db_puerto=5432, db_nombre="postgres", db_contrasena="-" * 16,
    db_sslmode="require", db_sslrootcert=None, db_pool_max=1, llave_datos="-" * 32,
    llave_seudonimo="-" * 32, jwt_llave="-" * 32, jwt_minutos=60, mongo_uri="mongodb://localhost:27017",
    mongo_db="sigaf_analitica", origenes_cors=(),
)


def exportar(destino: Path = RAIZ / "openapi.json") -> Path:
    esquema = crear_app(CONFIG_VACIA).openapi()
    destino.write_text(json.dumps(esquema, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    return destino


if __name__ == "__main__":
    print(f"Contrato guardado en {exportar()}")
