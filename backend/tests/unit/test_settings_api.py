"""Settings (stored in the library) and API keys (stored in the OS keyring, never returned)."""

import logging
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.library.service import Library, open_library
from tez.modules.settings.secrets import MemorySecretStore, SecretStoreUnavailable

SECRET = "s2-key-0123456789abcdef"


@pytest.fixture
def library(tmp_path: Path) -> Generator[Library]:
    lib = open_library(tmp_path / "TEz Library", create=True)
    yield lib
    lib.close()


@pytest.fixture
def store() -> MemorySecretStore:
    return MemorySecretStore()


@pytest.fixture
def client(library: Library, store: MemorySecretStore) -> Generator[TestClient]:
    app = create_app(token=TOKEN, settings=Settings(), library=library, secret_store=store)
    with TestClient(app) as c:
        yield c


# --- settings --------------------------------------------------------------------------


def test_defaults(client: TestClient) -> None:
    body = client.get("/settings", headers=AUTH).json()

    assert body == {"language": None, "theme": "system", "sources_email": None}


def test_changes_persist_across_restarts(tmp_path: Path, store: MemorySecretStore) -> None:
    """Task 8 acceptance, backend half: language and theme survive closing the app."""
    path = tmp_path / "TEz Library"
    first = create_app(
        token=TOKEN,
        settings=Settings(),
        library=open_library(path, create=True),
        secret_store=store,
    )
    with TestClient(first) as c:
        response = c.patch("/settings", headers=AUTH, json={"language": "en", "theme": "dark"})
        assert response.status_code == 200

    second = create_app(
        token=TOKEN, settings=Settings(), library=open_library(path), secret_store=store
    )
    with TestClient(second) as c:
        body = c.get("/settings", headers=AUTH).json()

    assert body == {"language": "en", "theme": "dark", "sources_email": None}


def test_patch_changes_only_what_is_sent(client: TestClient) -> None:
    client.patch("/settings", headers=AUTH, json={"theme": "dark", "sources_email": "a@b.org"})

    body = client.patch("/settings", headers=AUTH, json={"language": "tr"}).json()

    assert body == {"language": "tr", "theme": "dark", "sources_email": "a@b.org"}


def test_null_resets_to_the_default(client: TestClient) -> None:
    client.patch("/settings", headers=AUTH, json={"language": "en", "sources_email": "a@b.org"})

    body = client.patch("/settings", headers=AUTH, json={"language": None, "sources_email": None})

    assert body.json() == {"language": None, "theme": "system", "sources_email": None}


@pytest.mark.parametrize(
    "patch",
    [{"theme": "sepia"}, {"language": "de"}, {"sources_email": "not-an-email"}, {"unknown": 1}],
)
def test_invalid_values_are_rejected(client: TestClient, patch: dict[str, object]) -> None:
    response = client.patch("/settings", headers=AUTH, json=patch)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request.invalid"


def test_settings_need_an_open_library() -> None:
    client = TestClient(create_app(token=TOKEN, settings=Settings()))

    assert client.get("/settings", headers=AUTH).status_code == 409


# --- secrets (API keys) ------------------------------------------------------------------


def test_secrets_report_only_whether_they_are_set(client: TestClient) -> None:
    body = client.get("/secrets", headers=AUTH).json()

    assert body == [
        {"name": "semantic_scholar_api_key", "configured": False},
        {"name": "openalex_api_key", "configured": False},
    ]


def test_set_and_delete_a_secret(client: TestClient, store: MemorySecretStore) -> None:
    put = client.put(
        "/secrets/semantic_scholar_api_key", headers=AUTH, json={"value": f"  {SECRET} "}
    )

    assert put.status_code == 204
    assert store.get("semantic_scholar_api_key") == SECRET  # trimmed
    listed = client.get("/secrets", headers=AUTH).json()
    assert {"name": "semantic_scholar_api_key", "configured": True} in listed
    assert SECRET not in client.get("/secrets", headers=AUTH).text

    assert client.delete("/secrets/semantic_scholar_api_key", headers=AUTH).status_code == 204
    assert store.get("semantic_scholar_api_key") is None
    # Deleting again is fine.
    assert client.delete("/secrets/semantic_scholar_api_key", headers=AUTH).status_code == 204


def test_secret_values_never_reach_the_logs(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        client.put("/secrets/openalex_api_key", headers=AUTH, json={"value": SECRET})

    assert SECRET not in caplog.text


@pytest.mark.parametrize(
    ("name", "value", "status"),
    [
        ("github_token", SECRET, 422),
        ("openalex_api_key", "   ", 422),
        ("openalex_api_key", "x" * 600, 422),
    ],
)
def test_invalid_secrets_are_rejected(
    client: TestClient, name: str, value: str, status: int
) -> None:
    assert client.put(f"/secrets/{name}", headers=AUTH, json={"value": value}).status_code == status


def test_unavailable_keyring_is_an_error_code(library: Library) -> None:
    class Broken(MemorySecretStore):
        def get(self, name: str) -> str | None:
            raise SecretStoreUnavailable("no backend")

    app = create_app(token=TOKEN, settings=Settings(), library=library, secret_store=Broken())
    with TestClient(app) as c:
        response = c.get("/secrets", headers=AUTH)

    assert response.status_code == 503
    assert response.json() == {"error": {"code": "secrets.unavailable", "params": {}}}


def test_secrets_work_without_a_library(store: MemorySecretStore) -> None:
    # API keys live in the OS keyring, not in a library.
    client = TestClient(create_app(token=TOKEN, settings=Settings(), secret_store=store))

    assert client.get("/secrets", headers=AUTH).status_code == 200
