"""Task 31: the screening API, and the next record within 50 ms in a 2000-record review."""

import statistics
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.library.repository import LibraryRepository
from tez.modules.library.service import Library, open_library
from tez.modules.reviews.models import (
    CriterionKind,
    Decision,
    RecordOrigin,
    ReviewMethod,
    ScreeningStage,
)
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.screening import service
from tez.modules.screening.schemas import QueueFilter
from tez.modules.screening.service import Direction, ScreeningService

TA = ScreeningStage.TITLE_ABSTRACT


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    library = open_library(tmp_path / "lib", create=True)
    yield library
    library.close()


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(token=TOKEN, settings=Settings(), library=library)
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


def make_review(library: Library, papers: int) -> tuple[str, list[str], str]:
    """A review with `papers` records and one exclusion criterion; returns their ids."""
    with library.db.write_session() as session:
        repository = LibraryRepository(session)
        ids = [
            repository.add_paper(f"Paper {n}", abstract=f"Abstract {n}").id for n in range(papers)
        ]
        reviews = ReviewsRepository(session)
        review = reviews.add_review("SLR", method=ReviewMethod.PRISMA2020).id
        for paper_id in ids:
            reviews.add_record(review, paper_id, RecordOrigin.DATABASE)
        e1 = reviews.add_criterion(review, CriterionKind.EXCLUSION, "E1", "Off topic").id
    return review, ids, e1


def test_deciding_and_moving_through_the_queue(client: TestClient, library: Library) -> None:
    review, (a, b, c), e1 = make_review(library, 3)
    base = f"/reviews/{review}/screening/title_abstract"

    first = client.get(f"{base}/step", params={"filter": "undecided"}).json()
    assert (first["paper_id"], first["position"], first["total"]) == (a, 1, 3)
    assert first["abstract"] == "Abstract 0"

    made = client.post(f"{base}/decisions", json={"paper_id": a, "decision": "include"})
    assert made.status_code == 201
    skipped = client.get(f"{base}/step", params={"origin": a, "filter": "undecided"}).json()
    assert skipped["paper_id"] == b
    # Skipping b and deciding c wraps around to b, the one left undecided.
    client.post(
        f"{base}/decisions", json={"paper_id": c, "decision": "exclude", "criterion_id": e1}
    )
    wrapped = client.get(f"{base}/step", params={"origin": c, "filter": "undecided"}).json()
    assert wrapped["paper_id"] == b
    back = client.get(f"{base}/step", params={"origin": b, "direction": "previous"}).json()
    assert back["paper_id"] == a
    assert back["decision"]["decision"] == "include"

    queue = client.get(base, params={"filter": "exclude"}).json()
    assert queue["counts"] == {
        "total": 3,
        "undecided": 1,
        "include": 1,
        "exclude": 1,
        "maybe": 0,
        "not_retrieved": 0,
    }
    assert [(i["paper_id"], i["position"], i["criterion_id"]) for i in queue["items"]] == [
        (c, 3, e1)
    ]

    client.post(f"{base}/decisions", json={"paper_id": b, "decision": "maybe"})
    done = client.get(f"{base}/step", params={"origin": b, "filter": "undecided"})
    assert done.status_code == 200
    assert done.json() is None


def test_undo_and_history_over_the_api(client: TestClient, library: Library) -> None:
    review, (a,), _ = make_review(library, 1)
    base = f"/reviews/{review}/screening"

    made = client.post(
        f"{base}/title_abstract/decisions", json={"paper_id": a, "decision": "include"}
    )
    undone = client.post(f"{base}/title_abstract/undo", json={"decision_id": made.json()["id"]})

    assert undone.status_code == 201
    assert undone.json()["decision"] == "undecided"
    assert undone.json()["supersedes_id"] == made.json()["id"]
    record = client.get(f"{base}/title_abstract/records/{a}").json()
    assert record["state"] == "undecided"
    history = client.get(f"{base}/history/{a}").json()
    assert [row["decision"] for row in history] == ["include", "undecided"]
    # The review panel's counts follow: an undone record is pending again.
    stages = client.get(f"/reviews/{review}/overview").json()["stages"]
    assert stages[0]["pending"] == 1


@pytest.mark.parametrize(
    ("stage", "body", "status", "code"),
    [
        ("title_abstract", {"decision": "exclude"}, 400, "screening.reason_required"),
        ("full_text", {"decision": "include"}, 409, "screening.stage_not_reached"),
        ("title_abstract", {"decision": "not_retrieved"}, 400, "screening.invalid_decision"),
        ("title_abstract", {"decision": "undecided"}, 422, "request.invalid"),
    ],
)
def test_refusals_come_back_as_error_codes(
    client: TestClient,
    library: Library,
    stage: str,
    body: dict[str, str],
    status: int,
    code: str,
) -> None:
    review, (a,), _ = make_review(library, 1)

    response = client.post(
        f"/reviews/{review}/screening/{stage}/decisions", json={"paper_id": a, **body}
    )

    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_an_unknown_review_or_record_is_404(client: TestClient, library: Library) -> None:
    review, _, _ = make_review(library, 1)

    assert client.get("/reviews/nope/screening/title_abstract").status_code == 404
    missing = client.get(f"/reviews/{review}/screening/title_abstract/records/nope")
    assert missing.json()["error"]["code"] == "screening.record_not_found"


def test_the_next_record_comes_within_50_ms_in_a_2000_record_review(library: Library) -> None:
    review, ids, e1 = make_review(library, 2000)
    with library.db.write_session() as session:
        screening = ScreeningService(session)
        for n, paper_id in enumerate(ids[:1000]):
            if n % 2:
                screening.decide(review, paper_id, TA, Decision.EXCLUDE, criterion_id=e1)
            else:
                screening.decide(review, paper_id, TA, Decision.INCLUDE)

    timings: list[float] = []
    for origin in ids[1000:1010]:
        started = time.perf_counter()
        found = service.step(
            library.db,
            review,
            TA,
            origin=origin,
            direction=Direction.NEXT,
            wanted=QueueFilter.UNDECIDED,
        )
        timings.append(time.perf_counter() - started)
        assert found is not None

    assert statistics.median(timings) < 0.050, timings
