"""Task 24: creating a review (PRISMA 2020 by default) and the review panel's derived counts."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.library.repository import LibraryRepository
from tez.modules.library.service import Library, open_library
from tez.modules.reviews import service
from tez.modules.reviews.models import (
    Decision,
    RecordOrigin,
    ReviewMethod,
    ScreeningStage,
)
from tez.modules.reviews.repository import ReviewsRepository

TA = ScreeningStage.TITLE_ABSTRACT
FT = ScreeningStage.FULL_TEXT


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    opened = open_library(tmp_path / "lib", create=True)
    yield opened
    opened.close()


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(token=TOKEN, settings=Settings(), library=library)
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


def test_a_new_review_is_prisma_2020_unless_told_otherwise(client: TestClient) -> None:
    default = client.post("/reviews", json={"title": "Default"})
    chosen = client.post("/reviews", json={"title": "Chosen", "method": "kitchenham_slr"})

    assert default.status_code == 201, default.text
    assert default.json()["method"] == "prisma2020"
    assert chosen.json()["method"] == "kitchenham_slr"


def test_existing_reviews_keep_their_method(client: TestClient, library: Library) -> None:
    # A review written before Task 24, when the form's default was Kitchenham.
    with library.db.write_session() as session:
        old = ReviewsRepository(session).add_review("Old", method=ReviewMethod.KITCHENHAM_SLR).id

    client.post("/reviews", json={"title": "New"})

    methods = {r["title"]: r["method"] for r in client.get("/reviews").json()}
    assert methods == {"Old": "kitchenham_slr", "New": "prisma2020"}
    assert client.get(f"/reviews/{old}").json()["method"] == "kitchenham_slr"


def test_research_questions_and_protocol_come_back(client: TestClient) -> None:
    created = client.post(
        "/reviews",
        json={
            "title": "LLM Kod İnceleme",
            "research_questions": [
                "  Hangi LLM teknikleri kullanılıyor? ",
                "",
                "Nasıl\ndeğerlendiriliyor?",
            ],
            "protocol": "  Kayıt: OSF, 2026.  ",
        },
    ).json()

    fetched = client.get(f"/reviews/{created['id']}").json()

    assert fetched["research_questions"] == [
        "Hangi LLM teknikleri kullanılıyor?",
        "Nasıl değerlendiriliyor?",
    ]
    assert fetched["protocol"] == "Kayıt: OSF, 2026."
    assert client.get("/reviews").json()[0]["research_questions"] == fetched["research_questions"]


def test_a_review_without_questions_or_protocol(client: TestClient) -> None:
    created = client.post("/reviews", json={"title": "Bare", "protocol": "   "}).json()

    assert created["research_questions"] == []
    assert created["protocol"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"title": "x", "research_questions": ["q"] * 21},
        {"title": "x", "research_questions": ["q" * 1001]},
        {"title": "x", "protocol": "p" * 20_001},
    ],
)
def test_oversized_questions_or_protocol_are_rejected(
    client: TestClient, body: dict[str, object]
) -> None:
    assert client.post("/reviews", json=body).status_code == 422


def test_an_unknown_review_is_not_found(client: TestClient) -> None:
    for path in ("/reviews/nope", "/reviews/nope/overview"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "review.not_found"


def _review_with_papers(library: Library, count: int) -> tuple[str, list[str]]:
    with library.db.write_session() as session:
        reviews = ReviewsRepository(session)
        review_id = reviews.add_review("SLR", method=ReviewMethod.PRISMA2020).id
        papers = [LibraryRepository(session).add_paper(f"P{i}").id for i in range(count)]
        for paper_id in papers:
            reviews.add_record(review_id, paper_id, RecordOrigin.DATABASE)
    return review_id, papers


def _decide(
    library: Library,
    review_id: str,
    paper_id: str,
    stage: ScreeningStage,
    decision: Decision,
    supersedes_id: str | None = None,
) -> str:
    with library.db.write_session() as session:
        return (
            ReviewsRepository(session)
            .decide(review_id, paper_id, stage, decision, supersedes_id=supersedes_id)
            .id
        )


def _stages(library: Library, review_id: str) -> dict[str, dict[str, int]]:
    overview = service.overview(library.db, review_id)
    return {progress.stage: progress.model_dump(exclude={"stage"}) for progress in overview.stages}


def test_panel_counts_are_derived_from_records_and_decisions(library: Library) -> None:
    review_id, (p1, p2, p3, p4, p5) = _review_with_papers(library, 5)
    _decide(library, review_id, p1, TA, Decision.INCLUDE)
    _decide(library, review_id, p2, TA, Decision.EXCLUDE)
    maybe = _decide(library, review_id, p3, TA, Decision.MAYBE)
    _decide(library, review_id, p4, TA, Decision.INCLUDE)
    _decide(library, review_id, p1, FT, Decision.EXCLUDE)

    assert service.overview(library.db, review_id).records == 5
    assert _stages(library, review_id) == {
        "title_abstract": {
            "eligible": 5,
            "decided": 4,
            "pending": 1,
            "included": 2,
            "excluded": 1,
            "maybe": 1,
        },
        # Included and "maybe" at title-abstract go on to full text.
        "full_text": {
            "eligible": 3,
            "decided": 1,
            "pending": 2,
            "included": 0,
            "excluded": 1,
            "maybe": 0,
        },
    }

    # A correction is a new row; the counts follow it with nothing stored to update.
    _decide(library, review_id, p3, TA, Decision.EXCLUDE, supersedes_id=maybe)
    _decide(library, review_id, p5, TA, Decision.MAYBE)

    stages = _stages(library, review_id)
    assert stages["title_abstract"] == {
        "eligible": 5,
        "decided": 5,
        "pending": 0,
        "included": 2,
        "excluded": 2,
        "maybe": 1,
    }
    assert stages["full_text"]["eligible"] == 3  # p1, p4, p5
    assert stages["full_text"]["pending"] == 2


def test_a_full_text_decision_counts_only_while_the_paper_is_eligible(library: Library) -> None:
    review_id, (p1,) = _review_with_papers(library, 1)
    include = _decide(library, review_id, p1, TA, Decision.INCLUDE)
    _decide(library, review_id, p1, FT, Decision.INCLUDE)

    _decide(library, review_id, p1, TA, Decision.EXCLUDE, supersedes_id=include)

    assert _stages(library, review_id)["full_text"] == {
        "eligible": 0,
        "decided": 0,
        "pending": 0,
        "included": 0,
        "excluded": 0,
        "maybe": 0,
    }


def test_the_overview_through_the_api(client: TestClient, library: Library) -> None:
    review_id, _ = _review_with_papers(library, 2)

    body = client.get(f"/reviews/{review_id}/overview").json()

    assert body["review_id"] == review_id
    assert body["records"] == 2
    assert [s["stage"] for s in body["stages"]] == ["title_abstract", "full_text"]
    assert body["stages"][0]["pending"] == 2
