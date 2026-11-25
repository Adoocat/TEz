"""Task 47: highlights, areas and their comments through the API."""

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
    data = make_text_pdf([["One highlighted line", "another line"], ["Second page line"]])
    added = client.post("/pdfs", params={"file_name": "paper.pdf"}, content=data).json()
    worker = Worker(library.db, registry, lease=timedelta(seconds=30))
    while worker.run_once():
        pass
    return added["attachment_id"]


def mark(client: TestClient, attachment: str, **body: Any) -> dict[str, Any]:
    quote = body.pop("quote", "highlighted line")
    page = body.pop("page", 1)
    rects = body.pop("rects", [[72, 700, 200, 715]])
    anchor = {"page": page, "rects": rects, "quote": quote, "kind": body.pop("kind", "text")}
    response = client.post(
        f"/attachments/{attachment}/annotations", json={"anchor": anchor, **body}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_a_highlight_has_a_verified_anchor(client: TestClient, attachment: str) -> None:
    made = mark(client, attachment, color="green", comment=" a thought ")

    assert (made["kind"], made["color"], made["comment"]) == ("highlight", "green", "a thought")
    assert made["anchor"]["status"] == "verified"
    assert made["anchor"]["quote"] == "highlighted line"
    assert client.get(f"/attachments/{attachment}/annotations").json() == [made]


def test_marking_a_passage_again_changes_its_colour(client: TestClient, attachment: str) -> None:
    first = mark(client, attachment, comment="kept")
    second = mark(client, attachment, color="pink")

    assert second["id"] == first["id"]
    assert (second["color"], second["comment"]) == ("pink", "kept")


def test_annotations_come_in_reading_order(client: TestClient, attachment: str) -> None:
    last = mark(client, attachment, page=2, quote="Second page")
    below = mark(client, attachment, quote="another", rects=[[72, 600, 100, 615]])
    top = mark(client, attachment, quote="One highlighted")
    area = mark(client, attachment, kind="area", quote="", rects=[[10, 650, 90, 660]])

    listed = client.get(f"/attachments/{attachment}/annotations").json()

    assert [a["id"] for a in listed] == [top["id"], area["id"], below["id"], last["id"]]
    assert area["kind"] == "area"


def test_colour_and_comment_change_and_the_mark_can_go(client: TestClient, attachment: str) -> None:
    made = mark(client, attachment)

    changed = client.patch(
        f"/annotations/{made['id']}", json={"color": "blue", "comment": "see p. 2"}
    ).json()
    assert (changed["color"], changed["comment"]) == ("blue", "see p. 2")
    assert client.patch(f"/annotations/{made['id']}", json={"comment": ""}).json()["comment"] == ""

    assert client.delete(f"/annotations/{made['id']}").status_code == 204
    assert client.get(f"/attachments/{attachment}/annotations").json() == []
    # The place itself stays: a note may point at it.
    assert client.get(f"/anchors/{made['anchor']['id']}").status_code == 200
    assert client.delete(f"/annotations/{made['id']}").json()["error"]["code"] == (
        "annotation.not_found"
    )


def test_bad_marks_are_refused(client: TestClient, attachment: str) -> None:
    anchor = {"page": 1, "rects": [[1, 2, 3, 4]], "quote": "highlighted line"}
    url = f"/attachments/{attachment}/annotations"

    assert client.post(url, json={"anchor": anchor, "color": "#ff0000"}).status_code == 422
    assert client.post("/attachments/nope/annotations", json={"anchor": anchor}).status_code == 404
    assert client.get("/attachments/nope/annotations").status_code == 404
