"""Task 14's backend: the small review form, and keeping papers a search found."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.library.models import Paper
from tez.modules.library.repository import LibraryRepository
from tez.modules.library.service import Library, open_library
from tez.modules.reviews.models import RecordOrigin
from tez.modules.reviews.repository import ReviewsRepository


@pytest.fixture
def library(tmp_path: Path) -> Library:
    return open_library(tmp_path / "lib", create=True)


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(token=TOKEN, settings=Settings(), library=library)
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


def paper(library: Library, title: str = "A paper") -> str:
    with library.db.write_session() as session:
        return LibraryRepository(session).add_paper(title).id


def new_review(client: TestClient) -> str:
    response = client.post("/reviews", json={"title": "SLR", "method": "kitchenham_slr"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_reviews_can_be_created_and_listed(client: TestClient) -> None:
    assert client.get("/reviews").json() == []

    response = client.post(
        "/reviews", json={"title": "  LLM Kod İnceleme SLR ", "method": "prisma2020"}
    )

    created = response.json()
    assert created["title"] == "LLM Kod İnceleme SLR"
    assert created["method"] == "prisma2020"
    assert created["status"] == "active"
    assert [r["id"] for r in client.get("/reviews").json()] == [created["id"]]


@pytest.mark.parametrize(
    "body",
    [
        {"title": "  ", "method": "prisma2020"},
        {"title": "x", "method": "vibes"},
        {"title": "x"},
        {"title": "x", "method": "prisma2020", "extra": 1},
    ],
)
def test_an_invalid_review_is_rejected(client: TestClient, body: dict[str, object]) -> None:
    assert client.post("/reviews", json=body).status_code == 422


def test_papers_enter_a_review_once(client: TestClient, library: Library) -> None:
    review_id = new_review(client)
    first, second = paper(library), paper(library, "Another")

    response = client.post(
        f"/reviews/{review_id}/records", json={"paper_ids": [first], "search_id": "s1"}
    )
    again = client.post(f"/reviews/{review_id}/records", json={"paper_ids": [first, second]})

    assert response.json() == {"added": 1, "already_present": 0}
    assert again.json() == {"added": 1, "already_present": 1}
    with library.db.session() as session:
        records = ReviewsRepository(session).records(review_id)
    assert len(records) == 2
    assert {r.origin for r in records} == {RecordOrigin.DATABASE}
    assert next(r for r in records if r.paper_id == first).origin_ref == "s1"


def test_an_unknown_review_or_paper_is_not_found(client: TestClient, library: Library) -> None:
    known = paper(library)
    review_id = new_review(client)

    no_review = client.post("/reviews/nope/records", json={"paper_ids": [known]})
    no_paper = client.post(f"/reviews/{review_id}/records", json={"paper_ids": ["nope"]})

    assert no_review.status_code == 404
    assert no_review.json()["error"]["code"] == "review.not_found"
    assert no_paper.status_code == 404
    assert no_paper.json()["error"]["code"] == "paper.not_found"


def test_a_new_paper_is_not_in_the_library_until_kept(client: TestClient, library: Library) -> None:
    paper_id = paper(library)
    with library.db.session() as session:
        assert session.get(Paper, paper_id).library_added_at is None  # type: ignore[union-attr]

    response = client.post("/library/papers", json={"paper_ids": [paper_id]})

    assert response.json() == {"added": 1, "already_present": 0}
    with library.db.session() as session:
        kept = session.scalars(select(Paper).where(Paper.library_added_at.is_not(None))).one()
    assert kept.id == paper_id


def test_keeping_twice_keeps_the_first_date(client: TestClient, library: Library) -> None:
    paper_id = paper(library)
    client.post("/library/papers", json={"paper_ids": [paper_id]})
    with library.db.session() as session:
        first = session.get(Paper, paper_id).library_added_at  # type: ignore[union-attr]

    again = client.post("/library/papers", json={"paper_ids": [paper_id]})

    assert again.json() == {"added": 0, "already_present": 1}
    with library.db.session() as session:
        assert session.get(Paper, paper_id).library_added_at == first  # type: ignore[union-attr]


def test_keeping_an_unknown_paper_is_not_found(client: TestClient) -> None:
    response = client.post("/library/papers", json={"paper_ids": ["nope"]})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "paper.not_found"


def test_an_empty_selection_is_rejected(client: TestClient) -> None:
    assert client.post("/library/papers", json={"paper_ids": []}).status_code == 422
