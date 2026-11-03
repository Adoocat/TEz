from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tez.core.config import Settings
from tez.main import create_app

TOKEN = "test-token-0123456789"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def app() -> FastAPI:
    return create_app(token=TOKEN, settings=Settings())


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # Unhandled errors must come back as 500 responses, not be re-raised into the test.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
