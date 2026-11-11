"""Task 20: the reader streams a PDF from the backend with HTTP Range requests."""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tests.pdfs import make_pdf
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.files.models import Attachment
from tez.modules.library.service import Library, open_library
from tez.modules.settings.secrets import MemorySecretStore

PDF = make_pdf(5)


@pytest.fixture
def library(tmp_path: Path) -> Library:
    return open_library(tmp_path / "lib", create=True)


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(
        token=TOKEN, settings=Settings(), library=library, secret_store=MemorySecretStore()
    )
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def attachment_id(client: TestClient) -> str:
    response = client.post(
        "/pdfs",
        params={"file_name": "Kim 2024.pdf"},
        content=PDF,
        headers={"Content-Type": "application/pdf"},
    )
    return response.json()["attachment_id"]


def test_the_whole_file_comes_with_range_support_announced(
    client: TestClient, attachment_id: str
) -> None:
    response = client.get(f"/attachments/{attachment_id}/file")

    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-disposition"].startswith("inline")


def test_a_byte_range_is_served_alone(client: TestClient, attachment_id: str) -> None:
    response = client.get(f"/attachments/{attachment_id}/file", headers={"Range": "bytes=10-99"})

    assert response.status_code == 206
    assert response.content == PDF[10:100]
    assert response.headers["content-range"] == f"bytes 10-99/{len(PDF)}"


def test_the_file_needs_the_token(client: TestClient, attachment_id: str) -> None:
    response = client.get(
        f"/attachments/{attachment_id}/file", headers={"Authorization": "Bearer wrong"}
    )

    assert response.status_code == 401


def test_a_missing_file_or_attachment_is_404(
    client: TestClient, library: Library, attachment_id: str
) -> None:
    with library.db.session() as session:
        attachment = session.get(Attachment, attachment_id)
        assert attachment is not None
        (library.path / attachment.rel_path).unlink()

    missing = client.get(f"/attachments/{attachment_id}/file")
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "pdf.missing")
    unknown = client.get("/attachments/nope/file")
    assert unknown.json()["error"]["code"] == "attachment.not_found"


def test_range_reads_are_logged_at_debug_only(
    client: TestClient, attachment_id: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="tez.request"):
        client.get(f"/attachments/{attachment_id}/file", headers={"Range": "bytes=0-9"})
        client.get("/health")

    paths = [getattr(record, "path", None) for record in caplog.records]
    assert "/health" in paths
    assert f"/attachments/{attachment_id}/file" not in paths
