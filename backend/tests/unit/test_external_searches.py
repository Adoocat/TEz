"""Task 27 acceptance: a saved external search (database + query) is re-imported over time.

Importing the same file twice gives 0 new records; a file with one more record gives 1 new;
each import is its own `search_run`, linked to the saved search, so PRISMA sees both.
"""

import base64
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.library.service import Library, open_library
from tez.modules.reviews.models import ReviewMethod
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.search.models import SearchQuery, SearchRun
from tez.modules.search.repository import SearchRepository
from tez.modules.settings.secrets import MemorySecretStore

QUERY = 'TITLE-ABS-KEY("öğretmen eğitimi" AND "uzaktan")'

ENTRIES = [
    "@article{a, title={Uzaktan Eğitimde Öğretmen Algıları}, author={Kaya, Ali},"
    " year={2023}, doi={10.1000/a}}",
    "@article{b, title={Teacher Education Online}, author={Smith, Jo}, year={2022},"
    " doi={10.1000/b}}",
    "@article{c, title={İlköğretimde Çevrimiçi Dersler}, author={Işık, Ece}, year={2021}}",
]
EXTRA = (
    "@article{d, title={A Fourth Study of Distance Teaching}, author={Doe, Ann}, year={2024},"
    " doi={10.1000/d}}"
)


def bib(*entries: str) -> bytes:
    return "\n\n".join(entries).encode()


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
def review_id(library: Library) -> str:
    with library.db.write_session() as session:
        return ReviewsRepository(session).add_review("SLR", method=ReviewMethod.PRISMA2020).id


def file_body(data: bytes, name: str = "scopus.bib") -> dict[str, Any]:
    return {"file_name": name, "content_base64": base64.b64encode(data).decode()}


def save(client: TestClient, review_id: str, **extra: Any) -> dict[str, Any]:
    body = {"review_id": review_id, "source": "Scopus", "query": QUERY, **extra}
    response = client.post("/searches/external", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def import_into(
    client: TestClient, review_id: str, saved_id: str, data: bytes, searched_at: str
) -> dict[str, Any]:
    body = {
        **file_body(data),
        "review_id": review_id,
        "log": {"saved_search_id": saved_id, "searched_at": searched_at},
        "add_to_review": True,
    }
    response = client.post("/imports", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_a_saved_external_search_keeps_its_database_and_query(
    client: TestClient, review_id: str
) -> None:
    saved = save(client, review_id, name="Scopus ana sorgu")

    assert saved["source"] == "Scopus"
    assert saved["query"] == QUERY
    assert saved["name"] == "Scopus ana sorgu"
    assert (saved["imports"], saved["last_searched_at"]) == (0, None)
    listed = client.get("/searches/external", params={"review_id": review_id}).json()
    assert [s["id"] for s in listed] == [saved["id"]]


def test_saving_the_same_external_search_twice_keeps_one(
    client: TestClient, review_id: str
) -> None:
    first = save(client, review_id)
    second = save(client, review_id)

    assert second["id"] == first["id"]
    assert second["name"] == QUERY  # Unnamed: the query names it.


def test_a_saved_search_needs_an_existing_review(client: TestClient) -> None:
    body = {"review_id": "missing", "source": "Scopus", "query": QUERY}

    response = client.post("/searches/external", json=body)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "review.not_found"


def test_api_searches_are_not_listed_as_external(
    client: TestClient, library: Library, review_id: str
) -> None:
    with library.db.write_session() as session:
        session.add(SearchQuery(review_id=review_id, name="q", query_text=QUERY))

    listed = client.get("/searches/external", params={"review_id": review_id}).json()

    assert listed == []


def test_reimporting_the_same_file_finds_nothing_new(
    client: TestClient, library: Library, review_id: str
) -> None:
    saved = save(client, review_id)
    data = bib(*ENTRIES)

    first = import_into(client, review_id, saved["id"], data, "2026-10-12")
    second = import_into(client, review_id, saved["id"], data, "2026-11-14")

    # The first import has nothing to compare with.
    assert first["since_last"] is None
    assert first["added_to_review"] == 3
    assert second["since_last"]["new"] == 0
    assert second["since_last"]["last_searched_at"].startswith("2026-10-12")
    assert second["added_to_review"] == 0
    # Each import is its own run of the saved search: PRISMA counts both.
    with library.db.session() as session:
        runs = session.query(SearchRun).order_by(SearchRun.executed_at).all()
        assert [(r.query_id, r.source, r.translated_query) for r in runs] == [
            (saved["id"], "Scopus", QUERY),
            (saved["id"], "Scopus", QUERY),
        ]
        assert first["search_id"] != second["search_id"]


def test_a_file_with_one_more_record_finds_one_new(client: TestClient, review_id: str) -> None:
    saved = save(client, review_id)
    import_into(client, review_id, saved["id"], bib(*ENTRIES), "2026-10-12")

    later = import_into(client, review_id, saved["id"], bib(*ENTRIES, EXTRA), "2026-11-14")

    assert later["since_last"]["new"] == 1
    # Only the new record enters the review, and so the screening queue.
    assert later["added_to_review"] == 1
    listed = client.get("/searches/external", params={"review_id": review_id}).json()
    assert listed[0]["imports"] == 2
    assert listed[0]["last_searched_at"].startswith("2026-11-14")
    assert listed[0]["last_retrieved"] == 4


def test_the_preview_says_how_many_are_new_since_the_last_import(
    client: TestClient, review_id: str
) -> None:
    saved = save(client, review_id)
    import_into(client, review_id, saved["id"], bib(*ENTRIES), "2026-10-12")
    body = {**file_body(bib(*ENTRIES, EXTRA, EXTRA)), "saved_search_id": saved["id"]}

    preview = client.post("/imports/preview", json=body).json()

    # The extra record appears twice in the file: still one new record.
    assert preview["since_last"]["new"] == 1
    assert preview["since_last"]["last_searched_at"].startswith("2026-10-12")


def test_the_preview_of_a_first_import_has_no_comparison(
    client: TestClient, review_id: str
) -> None:
    saved = save(client, review_id)
    body = {**file_body(bib(*ENTRIES)), "saved_search_id": saved["id"]}

    preview = client.post("/imports/preview", json=body).json()

    assert preview["since_last"] is None


def test_a_saved_search_of_another_review_cannot_log_an_import(
    client: TestClient, library: Library, review_id: str
) -> None:
    with library.db.write_session() as session:
        other = ReviewsRepository(session).add_review("Other", method=ReviewMethod.PRISMA2020).id
    saved = save(client, other)
    body = {
        **file_body(bib(*ENTRIES)),
        "review_id": review_id,
        "log": {"saved_search_id": saved["id"]},
    }

    response = client.post("/imports", json=body)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "external_search.not_found"


def test_a_saved_search_import_takes_no_separate_source_or_query(
    client: TestClient, review_id: str
) -> None:
    saved = save(client, review_id)
    body = {
        **file_body(bib(*ENTRIES)),
        "review_id": review_id,
        "log": {"saved_search_id": saved["id"], "source": "JSTOR"},
    }

    response = client.post("/imports", json=body)

    assert response.status_code == 422


def test_an_unsaved_import_still_needs_a_source(client: TestClient, review_id: str) -> None:
    body = {**file_body(bib(*ENTRIES)), "review_id": review_id, "log": {}}

    response = client.post("/imports", json=body)

    assert response.status_code == 422


def test_api_searches_do_not_reuse_an_external_query(
    client: TestClient, library: Library, review_id: str
) -> None:
    with library.db.write_session() as session:
        repository = SearchRepository(session)
        external = repository.add_query(review_id, QUERY, QUERY, external_source="Scopus")
        api_query = repository.find_or_add_query(review_id, QUERY, None)

    assert api_query.id != external.id
    assert api_query.external_source is None
