from fastapi.testclient import TestClient

from app.main import crear_app
from tests.fakes import configuracion


def test_health():
    client = TestClient(crear_app(configuracion()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
