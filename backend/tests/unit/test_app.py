from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import AUTH
from tez import __version__


def test_health_with_token(client: TestClient) -> None:
    response = client.get("/health", headers=AUTH)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_every_response_has_a_request_id(client: TestClient) -> None:
    ok = client.get("/health", headers=AUTH)
    denied = client.get("/health")

    assert len(ok.headers["x-request-id"]) >= 8
    assert ok.headers["x-request-id"] != denied.headers["x-request-id"]


def test_openapi_documents_bearer_auth_and_error_shape(app: FastAPI) -> None:
    schema: dict[str, Any] = app.openapi()

    assert schema["info"] == {"title": "TEz", "version": __version__}
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    health = schema["paths"]["/health"]["get"]
    assert {"HTTPBearer": []} in health["security"]
    error_ref = health["responses"]["401"]["content"]["application/json"]["schema"]["$ref"]
    assert error_ref.endswith("/ErrorResponse")
