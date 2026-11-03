from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.library.service import find_instance, open_library


def test_get_library_without_an_open_library_is_409(client: TestClient) -> None:
    response = client.get("/library", headers=AUTH)

    assert response.status_code == 409
    assert response.json() == {"error": {"code": "library.not_open", "params": {}}}


def test_get_library_returns_the_open_library(tmp_path: Path) -> None:
    path = tmp_path / "TEz Library"
    library = open_library(path, create=True)
    app = create_app(token=TOKEN, settings=Settings(), library=library)

    with TestClient(app) as client:
        response = client.get("/library", headers=AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == str(path)
    assert body["name"] == "TEz Library"
    assert body["schema_revision"]


def test_app_shutdown_closes_the_library(tmp_path: Path) -> None:
    path = tmp_path / "TEz Library"
    library = open_library(path, create=True)
    app = create_app(token=TOKEN, settings=Settings(), library=library)

    with TestClient(app):
        assert find_instance(path) is not None

    assert find_instance(path) is None
