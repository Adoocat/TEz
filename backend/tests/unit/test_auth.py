"""Task 3 acceptance: a request without the token gets 401."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app

UI_ORIGIN = "http://tauri.localhost"


def test_request_without_token_is_401(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 401
    assert response.json() == {"error": {"code": "auth.invalid_token", "params": {}}}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "header",
    [
        "Bearer wrong-token",
        f"Bearer {TOKEN}x",
        f"Basic {TOKEN}",
        TOKEN,
        "Bearer ",
    ],
)
def test_wrong_token_is_401(client: TestClient, header: str) -> None:
    response = client.get("/health", headers={"Authorization": header})

    assert response.status_code == 401


def test_bearer_scheme_is_case_insensitive(client: TestClient) -> None:
    response = client.get("/health", headers={"Authorization": f"bearer {TOKEN}"})

    assert response.status_code == 200


def test_unknown_path_without_token_is_401_not_404(client: TestClient) -> None:
    # Auth runs before routing, so a caller without the token learns nothing about routes.
    assert client.get("/no-such-route").status_code == 401


def test_docs_need_the_token_by_default(client: TestClient) -> None:
    assert client.get("/openapi.json").status_code == 401
    assert client.get("/docs").status_code == 401


def test_dev_mode_opens_docs_but_not_the_api() -> None:
    client = TestClient(create_app(token=TOKEN, settings=Settings(), open_docs=True))

    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/health").status_code == 401


def test_cors_preflight_passes_without_token(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": UI_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == UI_ORIGIN


def test_401_carries_cors_headers(client: TestClient) -> None:
    # Without them the webview reports a network error instead of 401 (ADR 0001).
    response = client.get("/health", headers={"Origin": UI_ORIGIN})

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == UI_ORIGIN


def test_unlisted_origin_gets_no_cors_headers(client: TestClient) -> None:
    response = client.get("/health", headers={**AUTH, "Origin": "http://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_empty_token_is_rejected_at_startup() -> None:
    with pytest.raises(ValueError, match="token"):
        create_app(token="", settings=Settings())
