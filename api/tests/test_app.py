from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencias import BD
from app.main import crear_app
from tests.fakes import PoolFalso, configuracion, mongo_falso

ORIGEN = "http://localhost:8080"


def _app_con_pool_falso() -> tuple[FastAPI, PoolFalso]:
    pool = PoolFalso()
    app = crear_app(configuracion(origenes_cors=(ORIGEN,)), fabrica_pool=lambda config: pool,
                    fabrica_mongo=mongo_falso)

    @app.get("/_prueba_bd")
    def prueba(bd: BD) -> dict:
        with bd.transaccion() as cur:
            cur.execute("SELECT 1")
        return {"ok": True}

    return app, pool


def test_lifespan_abre_y_cierra_el_pool():
    app, pool = _app_con_pool_falso()
    with TestClient(app) as client:
        assert pool.abierto and not pool.cerrado
        assert client.get("/_prueba_bd").json() == {"ok": True}
        assert pool.conexion.commits == 2   # 1 al leer directorio_fragmento + 1 de la ruta
    assert pool.cerrado


def test_cors_permite_solo_el_origen_configurado():
    app, _ = _app_con_pool_falso()
    with TestClient(app) as client:
        permitido = client.options("/health", headers={
            "Origin": ORIGEN, "Access-Control-Request-Method": "GET"})
        ajeno = client.options("/health", headers={
            "Origin": "https://malicioso.example", "Access-Control-Request-Method": "GET"})
    assert permitido.headers["access-control-allow-origin"] == ORIGEN
    assert "access-control-allow-origin" not in ajeno.headers


def test_openapi_disponible():
    app, _ = _app_con_pool_falso()
    with TestClient(app) as client:
        assert client.get("/openapi.json").json()["info"]["title"] == "SIGAF API"


def test_lifespan_deja_lista_la_base_analitica():
    app, _ = _app_con_pool_falso()
    with TestClient(app):
        assert app.state.mongo_db.name == "sigaf_analitica"


def test_la_app_guarda_su_configuracion():
    # seguridad.py la lee de app.state para validar los tokens (#11).
    app, _ = _app_con_pool_falso()
    assert app.state.config.jwt_llave == "j" * 32
