"""Every error leaves the API as {"error": {"code": ..., "params": {...}}}."""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import AUTH
from tez.core.errors import ErrorCode, TezError


@pytest.fixture
def failing_app(app: FastAPI) -> FastAPI:
    @app.get("/tez-error")
    def tez_error() -> None:
        raise TezError(ErrorCode.HTTP_NOT_FOUND, {"what": "paper", "id": 7}, status=404)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    @app.get("/typed")
    def typed(n: int) -> int:
        return n

    return app


def test_tez_error_becomes_code_and_params(client: TestClient, failing_app: FastAPI) -> None:
    response = client.get("/tez-error", headers=AUTH)

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "http.not_found", "params": {"what": "paper", "id": 7}}
    }


def test_validation_error_is_request_invalid(client: TestClient, failing_app: FastAPI) -> None:
    response = client.get("/typed", params={"n": "abc"}, headers=AUTH)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "request.invalid"
    (field,) = error["params"]["fields"]
    assert field["loc"] == ["query", "n"]
    assert field["type"] == "int_parsing"


def test_unknown_route_is_not_found(client: TestClient) -> None:
    response = client.get("/no-such-route", headers=AUTH)

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "http.not_found", "params": {}}}


def test_wrong_method_is_method_not_allowed(client: TestClient) -> None:
    response = client.post("/health", headers=AUTH)

    assert response.status_code == 405
    assert response.json() == {"error": {"code": "http.method_not_allowed", "params": {}}}


def test_unexpected_error_is_500_without_internals(
    client: TestClient, failing_app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        response = client.get("/boom", headers={**AUTH, "Origin": "http://tauri.localhost"})

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal.unexpected"
    assert set(body["error"]["params"]) == {"request_id"}
    assert "secret internal detail" not in response.text
    # The UI still gets a readable 500, not a CORS network error.
    assert response.headers["access-control-allow-origin"] == "http://tauri.localhost"
    # ...and the detail is in the log, under the same request id.
    (record,) = [r for r in caplog.records if r.exc_info]
    assert "secret internal detail" in str(record.exc_info[1] if record.exc_info else "")
    assert getattr(record, "request_id", None) == body["error"]["params"]["request_id"]


def test_error_codes_are_dotted_lowercase() -> None:
    for code in ErrorCode:
        area, _, name = code.value.partition(".")
        assert area and name, code
        assert code.value == code.value.lower(), code


def test_error_codes_are_unique() -> None:
    values = [code.value for code in ErrorCode]
    assert len(values) == len(set(values))
