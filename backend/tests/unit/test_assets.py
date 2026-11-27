"""Task 55: figures and tables kept from an area marked in the reader.

Acceptance (with the reader, in E2E): from a gallery item back to its place in the PDF. Here:
the area becomes an anchor, the picture is kept and served, and deleting removes the picture
but keeps the place.
"""

import base64
import struct
import zlib
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tests.pdfs import make_text_pdf
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.jobs.handlers import registry
from tez.modules.library.service import Library, open_library
from tez.modules.settings.secrets import MemorySecretStore
from tez.worker import Worker


def png(width: int = 2, height: int = 1) -> bytes:
    """A real, tiny PNG."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    rows = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


IMAGE = png()


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    opened = open_library(tmp_path / "lib", create=True)
    yield opened
    opened.close()


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(
        token=TOKEN, settings=Settings(), library=library, secret_store=MemorySecretStore()
    )
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def attachment(client: TestClient, library: Library) -> str:
    pdf = make_text_pdf([["Results", "Figure 2 shows the nests"], ["Table 1 lists sites"]])
    made = client.post("/pdfs", params={"file_name": "storks.pdf"}, content=pdf)
    assert made.status_code == 201, made.text
    worker = Worker(library.db, registry, lease=timedelta(seconds=30))
    while worker.run_once():
        pass
    return made.json()["attachment_id"]


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def add(client: TestClient, attachment: str, **body: Any) -> Any:
    return client.post(
        f"/attachments/{attachment}/assets",
        json={
            "kind": "figure",
            "label": "Şekil 2",
            "caption": "Yuvaların dağılımı",
            "page": 1,
            "rect": [72.0, 400.0, 300.0, 600.0],
            "image_base64": base64.b64encode(IMAGE).decode(),
            **body,
        },
    )


def test_an_area_is_kept_with_its_picture_and_its_place(
    client: TestClient, library: Library, attachment: str
) -> None:
    made = ok(add(client, attachment), 201)
    assert (made["kind"], made["label"], made["caption"], made["page"]) == (
        "figure",
        "Şekil 2",
        "Yuvaların dağılımı",
        1,
    )
    assert made["paper"]["title"] == "storks"
    # The place is an area anchor: the reader opens it with ?anchor=.
    anchor = ok(client.get(f"/anchors/{made['anchor_id']}"))
    assert (anchor["kind"], anchor["page"], anchor["attachment_id"]) == ("area", 1, attachment)
    assert made["anchor_status"] == anchor["status"]

    image = client.get(f"/assets/{made['id']}/image")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert image.content == IMAGE
    assert (library.path / "derived" / attachment / "assets" / f"{made['id']}.png").is_file()


def test_the_gallery_lists_newest_first_and_by_kind(client: TestClient, attachment: str) -> None:
    figure = ok(add(client, attachment), 201)
    table = ok(add(client, attachment, kind="table", label="Tablo 1", page=2), 201)
    assert [a["id"] for a in ok(client.get("/assets"))] == [table["id"], figure["id"]]
    assert [a["id"] for a in ok(client.get("/assets", params={"kind": "table"}))] == [table["id"]]


def test_label_caption_and_kind_are_edited(client: TestClient, attachment: str) -> None:
    made = ok(add(client, attachment), 201)
    edited = ok(client.patch(f"/assets/{made['id']}", json={"kind": "table", "caption": "Sites"}))
    assert (edited["kind"], edited["label"], edited["caption"]) == ("table", "Şekil 2", "Sites")


def test_deleting_removes_the_picture_and_keeps_the_place(
    client: TestClient, library: Library, attachment: str
) -> None:
    made = ok(add(client, attachment), 201)
    assert client.delete(f"/assets/{made['id']}").status_code == 204
    assert ok(client.get("/assets")) == []
    assert not (library.path / "derived" / attachment / "assets" / f"{made['id']}.png").exists()
    assert ok(client.get(f"/anchors/{made['anchor_id']}"))["id"] == made["anchor_id"]
    assert client.get(f"/assets/{made['id']}/image").json()["error"]["code"] == "asset.not_found"


def test_only_a_png_is_taken(client: TestClient, attachment: str) -> None:
    not_png = base64.b64encode(b"GIF89a....").decode()
    response = add(client, attachment, image_base64=not_png)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "asset.image_invalid"
    garbage = add(client, attachment, image_base64="***")
    assert garbage.json()["error"]["code"] == "asset.image_invalid"
    assert ok(client.get("/assets")) == []
    unknown = add(client, "nope")
    assert unknown.status_code == 404
