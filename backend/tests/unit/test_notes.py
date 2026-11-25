"""Task 48 acceptance: links are brought up to date at every save; a link whose target is gone is
marked broken."""

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
from tez.modules.library.models import Paper
from tez.modules.library.paper_service import PaperService
from tez.modules.library.repository import AuthorInput
from tez.modules.library.service import Library, open_library
from tez.modules.notes.links import links_in, plain_text
from tez.modules.notes.models import LinkTarget
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


def note(client: TestClient, title: str, body: str = "", **more: object) -> dict[str, Any]:
    response = client.post("/notes", json={"title": title, "body": body, **more})
    assert response.status_code == 201, response.text
    return response.json()


def save(client: TestClient, note_id: str, **changes: object) -> dict[str, Any]:
    response = client.patch(f"/notes/{note_id}", json=changes)
    assert response.status_code == 200, response.text
    return response.json()


def get(client: TestClient, note_id: str) -> dict[str, Any]:
    return client.get(f"/notes/{note_id}").json()


def backlinks(client: TestClient, note_id: str) -> list[str]:
    return [b["title"] for b in client.get(f"/notes/{note_id}/backlinks").json()]


def paper(library: Library, title: str = "Grounded theory in schools") -> str:
    with library.db.write_session() as session:
        service = PaperService(session)
        author = AuthorInput(display_name="Işıl Kim", family="Kim", given="Işıl")
        made = service.add(title, identifiers={}, authors=[author], year=2024)
        service.keep([made.id])
        return made.id


def anchored(client: TestClient, library: Library) -> tuple[str, str, str]:
    """(paper, attachment, anchor)"""
    data = make_text_pdf([["We interviewed forty-two participants in twelve schools"]])
    added = client.post("/pdfs", params={"file_name": "kim.pdf"}, content=data).json()
    worker = Worker(library.db, registry, lease=timedelta(seconds=30))
    while worker.run_once():
        pass
    anchor = client.post(
        f"/attachments/{added['attachment_id']}/anchors",
        json={"page": 1, "rects": [[1, 2, 3, 4]], "quote": "interviewed forty-two participants"},
    ).json()
    return added["paper_id"], added["attachment_id"], anchor["id"]


def test_links_follow_the_text_at_every_save(client: TestClient, library: Library) -> None:
    first, second = note(client, "First"), note(client, "Second")
    source = note(client, "Source", f"See [First](tez:note/{first['id']}).")
    assert [(k["target_id"], k["status"], k["title"]) for k in source["links"]] == [
        (first["id"], "ok", "First")
    ]
    assert backlinks(client, first["id"]) == ["Source"]

    changed = save(client, source["id"], body="Now [[Second]] and [[Nothing yet]].")

    assert [(k["label"], k["target_id"], k["status"]) for k in changed["links"]] == [
        ("Second", second["id"], "ok"),
        ("Nothing yet", None, "broken"),
    ]
    assert backlinks(client, first["id"]) == []
    assert backlinks(client, second["id"]) == ["Source"]


def test_a_name_written_before_its_note_finds_it(client: TestClient) -> None:
    source = note(client, "Source", "Later: [[Işık Hızı]]")

    made = note(client, "ışık hızı")

    assert get(client, source["id"])["links"][0]["target_id"] == made["id"]
    assert backlinks(client, made["id"]) == ["Source"]


def test_renaming_a_note_keeps_every_link(client: TestClient) -> None:
    target = note(client, "Old name")
    source = note(client, "Source", f"[[Old name]] and [Old name](tez:note/{target['id']})")

    save(client, target["id"], title="New [name]")

    after = get(client, source["id"])
    assert after["body"] == (
        f"[New (name)](tez:note/{target['id']}) and [Old name](tez:note/{target['id']})"
    )
    assert [k["status"] for k in after["links"]] == ["ok", "ok"]
    assert {k["title"] for k in after["links"]} == {"New [name]"}
    assert backlinks(client, target["id"]) == ["Source"]


def test_links_to_what_is_gone_are_broken_until_it_is_back(
    client: TestClient, library: Library
) -> None:
    target = note(client, "Target")
    paper_id = paper(library)
    source = note(
        client,
        "Source",
        f"[[Target]] [Kim](tez:paper/{paper_id}) [gone](tez:anchor/0000) [x](tez:note/nope)",
    )
    statuses = lambda: [k["status"] for k in get(client, source["id"])["links"]]  # noqa: E731
    assert statuses() == ["ok", "ok", "broken", "broken"]

    client.delete(f"/notes/{target['id']}")
    with library.db.write_session() as session:
        trashed = session.get(Paper, paper_id)
        assert trashed is not None
        trashed.deleted_at = trashed.created_at
    assert statuses() == ["broken", "broken", "broken", "broken"]

    client.post(f"/notes/{target['id']}/restore")
    assert statuses()[0] == "ok"
    assert backlinks(client, target["id"]) == ["Source"]


def test_a_link_to_a_place_breaks_when_the_place_is_lost(
    client: TestClient, library: Library
) -> None:
    _, attachment, anchor = anchored(client, library)
    source = note(client, "Source", f"> quote\n>\n> [Kim 2024, p. 1](tez:anchor/{anchor})")
    link = source["links"][0]
    assert (link["status"], link["anchor"]["page"], link["anchor"]["attachment_id"]) == (
        "ok",
        1,
        attachment,
    )

    client.put(
        f"/attachments/{attachment}/file",
        params={"file_name": "v2.pdf"},
        content=make_text_pdf([["Something else"]]),
    )
    worker = Worker(library.db, registry, lease=timedelta(seconds=30))
    while worker.run_once():
        pass

    assert get(client, source["id"])["links"][0]["status"] == "broken"


def test_citation_keys_and_paper_titles_are_names(client: TestClient, library: Library) -> None:
    paper_id = paper(library)
    with library.db.session() as session:
        found = session.get(Paper, paper_id)
        assert found is not None and found.citekey
        key = found.citekey
    source = note(client, "Source", f"[[{key}]] [[grounded THEORY in schools]]")

    assert [(k["target_type"], k["target_id"]) for k in source["links"]] == [
        ("paper", paper_id),
        ("paper", paper_id),
    ]


def test_notes_about_a_paper(client: TestClient, library: Library) -> None:
    paper_id, _, anchor = anchored(client, library)
    note(client, "Attached", paper_id=paper_id)
    note(client, "Links to it", f"As in [Kim](tez:paper/{paper_id}), schools differ.")
    note(client, "Quotes it", f"They [say](tez:anchor/{anchor}) so.")
    note(client, "Unrelated")

    found = client.get(f"/papers/{paper_id}/notes").json()

    assert sorted(b["title"] for b in found) == ["Attached", "Links to it", "Quotes it"]
    passages = {b["title"]: b["passage"] for b in found}
    assert passages["Links to it"] == "As in Kim, schools differ."
    assert passages["Attached"] == ""
    assert client.get("/papers/nope/notes").status_code == 404


def test_a_save_based_on_an_older_text_is_refused(client: TestClient) -> None:
    made = note(client, "Note", "one")
    save(client, made["id"], body="two", base_version=1)

    response = client.patch(f"/notes/{made['id']}", json={"body": "mine", "base_version": 1})

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "note.conflict",
        "params": {"note_id": made["id"], "version": 2},
    }
    assert get(client, made["id"])["body"] == "two"
    # Saying so overwrites.
    assert save(client, made["id"], body="mine")["version"] == 3


def test_the_tree_moves_without_cycles_and_survives_deletion(client: TestClient) -> None:
    top = note(client, "Top")
    middle = note(client, "Middle", parent_id=top["id"])
    leaf = note(client, "Leaf", parent_id=middle["id"])

    cycle = client.patch(f"/notes/{top['id']}", json={"parent_id": leaf["id"]})
    assert cycle.json()["error"]["code"] == "note.cycle"
    client.delete(f"/notes/{middle['id']}")

    parents = {n["title"]: n["parent_id"] for n in client.get("/notes").json()}
    assert parents == {"Top": None, "Leaf": top["id"]}
    client.delete(f"/notes/{top['id']}")
    assert client.post(f"/notes/{middle['id']}/restore").json()["parent_id"] is None
    assert save(client, leaf["id"], parent_id=middle["id"])["parent_id"] == middle["id"]
    assert save(client, leaf["id"], parent_id=None)["parent_id"] is None
    assert save(client, leaf["id"], title="Leaf 2")["parent_id"] is None


def test_search_finds_titles_and_words_folded_and_follows_changes(client: TestClient) -> None:
    title_hit = note(client, "Işık kirliliği", "short")
    body_hit = note(client, "Other", "Uzun bir metinde ışık geçiyor, [Kim](tez:paper/abc) ile.")
    gone = note(client, "ışık silinecek")
    client.delete(f"/notes/{gone['id']}")

    found = client.get("/notes/search", params={"q": "ISIK"}).json()
    assert [h["note_id"] for h in found] == [title_hit["id"], body_hit["id"]]
    assert "".join(p["text"] for p in found[1]["passage"]) == (
        "Uzun bir metinde ışık geçiyor, Kim ile."
    )
    assert [p["text"] for p in found[1]["passage"] if p["hit"]] == ["ışık"]
    # Addresses of links are not words of the note.
    assert client.get("/notes/search", params={"q": "tez abc"}).json() == []
    save(client, body_hit["id"], body="nothing")
    assert len(client.get("/notes/search", params={"q": "ışık"}).json()) == 1
    client.post(f"/notes/{gone['id']}/restore")
    assert len(client.get("/notes/search", params={"q": "ışık"}).json()) == 2


def test_suggestions_are_notes_and_papers(client: TestClient, library: Library) -> None:
    paper_id = paper(library)
    note(client, "Theory of schools")
    note(client, "Grounded")

    found = client.get("/notes/suggest", params={"q": "theory school"}).json()
    assert [(s["target_type"], s["title"]) for s in found] == [
        ("note", "Theory of schools"),
        ("paper", "Grounded theory in schools"),
    ]
    by_author = client.get("/notes/suggest", params={"q": "kim 2024"}).json()
    assert [(s["target_id"], s["detail"]) for s in by_author] == [(paper_id, "Kim 2024")]
    assert len(client.get("/notes/suggest").json()) == 3


def test_appending_adds_a_paragraph_and_reads_its_links(
    client: TestClient, library: Library
) -> None:
    _, _, anchor = anchored(client, library)
    made = note(client, "Note", "Start.\n")

    after = client.post(
        f"/notes/{made['id']}/append", json={"text": f"> quote [p. 1](tez:anchor/{anchor})\n"}
    ).json()

    assert after["body"] == f"Start.\n\n> quote [p. 1](tez:anchor/{anchor})\n"
    assert (after["version"], after["links"][0]["status"]) == (2, "ok")


def test_bad_requests(client: TestClient) -> None:
    assert client.get("/notes/nope").json()["error"]["code"] == "note.not_found"
    assert client.post("/notes", json={"title": "  "}).status_code == 422
    assert client.post("/notes", json={"title": "x", "paper_id": "nope"}).status_code == 404
    assert client.post("/notes", json={"title": "x", "review_id": "nope"}).status_code == 404
    assert client.post("/notes", json={"title": "x", "parent_id": "nope"}).status_code == 404
    assert client.get("/notes").json() == []


def test_links_in_code_are_text() -> None:
    body = "`[[a]]` [[b]]\n```\n[[c]] [x](tez:note/1)\n```\n[y](tez:paper/2) [z](https://e.org)"

    assert [(k.label, k.target_type) for k in links_in(body)] == [
        ("b", None),
        ("y", LinkTarget.PAPER),
    ]
    assert plain_text("[[b]] and [y](tez:paper/2)") == "b and y"
