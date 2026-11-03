from fastapi.testclient import TestClient

from tez import __version__
from tez.main import create_app


def test_app_exposes_openapi_with_version() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    info = response.json()["info"]
    assert info == {"title": "TEz", "version": __version__}
