"""Task 18 integration tests: the collection tree, tags and reading status through the API."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.library.models import Paper
from tez.modules.library.paper_service import PaperService
from tez.modules.library.service import Library, open_library
from tez.modules.settings.secrets import MemorySecretStore


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


def papers(library: Library, *titles: str, keep: bool = True) -> list[str]:
    with library.db.write_session() as session:
        service = PaperService(session)
        ids = [service.add(title, identifiers={}, authors=[]).id for title in titles]
        if keep:
            service.keep(ids)
        return ids


def collection(client: TestClient, name: str, parent_id: str | None = None) -> str:
    response = client.post("/collections", json={"name": name, "parent_id": parent_id})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def tree(client: TestClient) -> list[tuple[str, str | None, int]]:
    by_id = {c["id"]: c["name"] for c in client.get("/collections").json()}
    return [
        (c["name"], by_id.get(c["parent_id"]), c["paper_count"])
        for c in client.get("/collections").json()
    ]


# --- the collection tree --------------------------------------------------------------


def test_collections_nest_and_list_parents_first_in_turkish_order(client: TestClient) -> None:
    thesis = collection(client, "Tez")
    collection(client, "Yöntem", thesis)
    collection(client, "Arka Plan", thesis)
    collection(client, "Çalışma Grubu")

    assert tree(client) == [
        ("Çalışma Grubu", None, 0),
        ("Tez", None, 0),
        ("Arka Plan", "Tez", 0),
        ("Yöntem", "Tez", 0),
    ]


def test_a_collection_is_renamed_and_moved(client: TestClient) -> None:
    thesis = collection(client, "Tez")
    method = collection(client, "Yöntem", thesis)
    other = collection(client, "Diğer")

    renamed = client.patch(f"/collections/{method}", json={"name": "Yöntemler"})
    assert renamed.json()["name"] == "Yöntemler"
    moved = client.patch(f"/collections/{method}", json={"parent_id": other})
    assert moved.json()["parent_id"] == other
    to_top = client.patch(f"/collections/{method}", json={"parent_id": None})
    assert to_top.json()["parent_id"] is None


def test_a_collection_cannot_go_inside_itself(client: TestClient) -> None:
    thesis = collection(client, "Tez")
    method = collection(client, "Yöntem", thesis)

    response = client.patch(f"/collections/{thesis}", json={"parent_id": method})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "collection.cycle"


def test_sibling_names_are_unique_ignoring_case_and_turkish_letters(client: TestClient) -> None:
    thesis = collection(client, "Işık")
    collection(client, "Alt", thesis)

    same = client.post("/collections", json={"name": "ışık"})
    assert same.status_code == 409
    assert same.json()["error"]["code"] == "collection.name_taken"
    # The same name under another parent is fine.
    assert client.post("/collections", json={"name": "Alt"}).status_code == 201


def test_deleting_a_collection_deletes_its_children_but_not_papers(
    client: TestClient, library: Library
) -> None:
    thesis = collection(client, "Tez")
    method = collection(client, "Yöntem", thesis)
    (paper,) = papers(library, "A paper")
    client.post(f"/collections/{method}/papers", json={"paper_ids": [paper]})

    assert client.delete(f"/collections/{thesis}").status_code == 204

    assert client.get("/collections").json() == []
    assert [p["id"] for p in client.get("/papers").json()] == [paper]


def test_the_inbox_cannot_be_renamed_moved_or_deleted(client: TestClient, library: Library) -> None:
    with library.db.write_session() as session:
        inbox = PaperService(session).inbox_id()

    assert client.patch(f"/collections/{inbox}", json={"name": "x"}).status_code == 409
    response = client.delete(f"/collections/{inbox}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "collection.system"
    assert client.get("/collections").json()[0]["is_system"] is True


def test_unknown_collections_are_404(client: TestClient) -> None:
    assert client.patch("/collections/nope", json={"name": "x"}).status_code == 404
    assert client.post("/collections", json={"name": "x", "parent_id": "nope"}).status_code == 404
    response = client.post("/collections/nope/papers", json={"paper_ids": ["p"]})
    assert response.json()["error"]["code"] == "collection.not_found"


# --- papers in collections ------------------------------------------------------------


def test_a_paper_can_be_in_several_collections(client: TestClient, library: Library) -> None:
    first, second = collection(client, "Birinci"), collection(client, "İkinci")
    one, two = papers(library, "One", "Two")

    added = client.post(f"/collections/{first}/papers", json={"paper_ids": [one, two]}).json()
    again = client.post(f"/collections/{first}/papers", json={"paper_ids": [one]}).json()
    client.post(f"/collections/{second}/papers", json={"paper_ids": [one]})

    assert added == {"changed": 2, "unchanged": 0}
    assert again == {"changed": 0, "unchanged": 1}
    assert sorted(
        next(p for p in client.get("/papers").json() if p["id"] == one)["collection_ids"]
    ) == sorted([first, second])
    assert {p["id"] for p in client.get("/papers", params={"collection_id": first}).json()} == {
        one,
        two,
    }
    assert [c["paper_count"] for c in client.get("/collections").json()] == [2, 1]

    removed = client.post(f"/collections/{first}/papers/remove", json={"paper_ids": [two, two]})
    assert removed.json() == {"changed": 1, "unchanged": 0}
    assert [p["id"] for p in client.get("/papers", params={"collection_id": first}).json()] == [one]


def test_filing_a_search_candidate_keeps_it_in_the_library(
    client: TestClient, library: Library
) -> None:
    target = collection(client, "Tez")
    (candidate,) = papers(library, "Only found by a search", keep=False)
    assert client.get("/papers").json() == []

    client.post(f"/collections/{target}/papers", json={"paper_ids": [candidate]})

    assert [p["id"] for p in client.get("/papers").json()] == [candidate]


def test_trashed_papers_are_not_listed_or_counted(client: TestClient, library: Library) -> None:
    target = collection(client, "Tez")
    kept, trashed = papers(library, "Kept", "Trashed")
    client.post(f"/collections/{target}/papers", json={"paper_ids": [kept, trashed]})
    with library.db.write_session() as session:
        paper = session.get(Paper, trashed)
        assert paper is not None
        paper.deleted_at = paper.created_at

    assert [p["id"] for p in client.get("/papers").json()] == [kept]
    assert client.get("/collections").json()[0]["paper_count"] == 1


# --- tags -----------------------------------------------------------------------------


def test_tags_are_created_listed_and_counted(client: TestClient, library: Library) -> None:
    one, two = papers(library, "One", "Two")
    survey = client.post("/tags", json={"name": "anket", "color": "orange"}).json()
    empirical = client.post("/tags", json={"name": "ampirik-çalışma", "color": "#16a34a"}).json()

    client.post(f"/tags/{survey['id']}/papers", json={"paper_ids": [one, two]})
    client.post(f"/tags/{empirical['id']}/papers", json={"paper_ids": [one]})

    assert [(t["name"], t["color"], t["paper_count"]) for t in client.get("/tags").json()] == [
        ("ampirik-çalışma", "#16a34a", 1),
        ("anket", "orange", 2),
    ]
    row = next(p for p in client.get("/papers").json() if p["id"] == one)
    assert sorted(row["tag_ids"]) == sorted([survey["id"], empirical["id"]])
    tagged = client.get("/papers", params={"tag_id": empirical["id"]}).json()
    assert [p["id"] for p in tagged] == [one]

    untagged = client.post(f"/tags/{survey['id']}/papers/remove", json={"paper_ids": [one]})
    assert untagged.json() == {"changed": 1, "unchanged": 0}


def test_a_tag_is_renamed_recoloured_and_deleted(client: TestClient, library: Library) -> None:
    (paper,) = papers(library, "One")
    tag = client.post("/tags", json={"name": "benchmark"}).json()
    client.post(f"/tags/{tag['id']}/papers", json={"paper_ids": [paper]})

    updated = client.patch(f"/tags/{tag['id']}", json={"name": "kıyaslama", "color": "blue"})
    assert (updated.json()["name"], updated.json()["color"]) == ("kıyaslama", "blue")
    cleared = client.patch(f"/tags/{tag['id']}", json={"color": None})
    assert cleared.json()["color"] is None

    assert client.delete(f"/tags/{tag['id']}").status_code == 204
    assert client.get("/tags").json() == []
    assert client.get("/papers").json()[0]["tag_ids"] == []


def test_tag_names_are_unique_and_colours_checked(client: TestClient) -> None:
    client.post("/tags", json={"name": "Önemli"})

    taken = client.post("/tags", json={"name": "önemli"})
    assert taken.status_code == 409
    assert taken.json()["error"]["code"] == "tag.name_taken"
    assert client.post("/tags", json={"name": "x", "color": "red; drop"}).status_code == 422


# --- reading status -------------------------------------------------------------------


def test_reading_status_changes_for_many_papers_at_once(
    client: TestClient, library: Library
) -> None:
    one, two = papers(library, "One", "Two")

    response = client.patch(
        "/papers/reading-status", json={"paper_ids": [one, two], "reading_status": "reading"}
    )
    again = client.patch(
        "/papers/reading-status", json={"paper_ids": [one], "reading_status": "reading"}
    )

    assert response.json() == {"changed": 2, "unchanged": 0}
    assert again.json() == {"changed": 0, "unchanged": 1}
    assert {p["reading_status"] for p in client.get("/papers").json()} == {"reading"}
    bad = client.patch("/papers/reading-status", json={"paper_ids": [one], "reading_status": "x"})
    assert bad.status_code == 422
    missing = client.patch(
        "/papers/reading-status", json={"paper_ids": ["nope"], "reading_status": "read"}
    )
    assert missing.json()["error"]["code"] == "paper.not_found"
