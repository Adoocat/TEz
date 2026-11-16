"""Task 37: grey literature. A record by hand and an import marked as other methods are both
logged in their PRISMA box and go through deduplication.

Acceptance (with Task 34's counts): a thesis added by hand lands in the theses box of the
other-methods branch; the same record arriving from a database is a duplicate.
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
from tez.modules.reviews import service as reviews_service
from tez.modules.reviews.models import RecordOrigin, ScreeningStage
from tez.modules.screening.service import ScreeningService
from tez.modules.search import queries
from tez.modules.search.models import GREY_METHODS, RunMethod

THESIS = {
    "kind": "thesis",
    "source": "YÖK Ulusal Tez Merkezi",
    "title": "Büyük Dil Modelleriyle Kod İnceleme",
    "authors": ["Yılmaz, Ayşe"],
    "year": 2025,
    "institution": "Orta Doğu Teknik Üniversitesi",
    "thesis_type": "masters",
    "url": "https://tez.yok.gov.tr/example",
}


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


@pytest.fixture
def review(client: TestClient) -> str:
    return client.post("/reviews", json={"title": "SLR"}).json()["id"]


def add(client: TestClient, review: str, **body: Any) -> dict[str, Any]:
    response = client.post(f"/reviews/{review}/grey-literature", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def import_ris(client: TestClient, review: str, ris: str, **log: Any) -> dict[str, Any]:
    response = client.post(
        "/imports",
        json={
            "file_name": "export.ris",
            "content_base64": base64.b64encode(ris.encode()).decode(),
            "review_id": review,
            "add_to_review": True,
            "log": log,
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def runs(library: Library, review: str) -> list[queries.RunFacts]:
    return queries.runs_by_method(library.db, review, list(RunMethod))


def test_a_thesis_by_hand_is_logged_in_the_theses_box_and_enters_screening(
    client: TestClient, library: Library, review: str
) -> None:
    added = add(client, review, **THESIS)

    assert added["found_via"] == "thesis"
    assert (added["matched_existing"], added["added_to_review"]) == (False, True)
    [run] = runs(library, review)
    assert (run.method, run.source, run.paper_ids) == (
        RunMethod.THESIS,
        "YÖK Ulusal Tez Merkezi",
        (added["paper_id"],),
    )
    [record] = reviews_service.records(library.db, review)
    assert record.origin is RecordOrigin.MANUAL
    with library.db.session() as session:
        queue = ScreeningService(session).queue(review, ScreeningStage.TITLE_ABSTRACT)
    assert queue == [added["paper_id"]]
    paper = client.get(f"/papers/{added['paper_id']}").json()
    assert (paper["venue_type"], paper["venue"]) == ("thesis", "Orta Doğu Teknik Üniversitesi")


@pytest.mark.parametrize(
    ("kind", "box"),
    [("report", "organisation"), ("register_record", "register"), ("web_page", "website")],
)
def test_the_box_follows_the_kind_unless_given(
    client: TestClient, review: str, kind: str, box: str
) -> None:
    body = {"kind": kind, "source": "WHO", "title": f"A {kind}"}

    assert add(client, review, **body)["found_via"] == box
    assert add(client, review, **body, found_via="website")["found_via"] == "website"


def test_the_same_record_from_a_database_is_a_duplicate(
    client: TestClient, library: Library, review: str
) -> None:
    by_hand = add(client, review, **THESIS)
    ris = (
        "TY  - THES\nTI  - Büyük dil modelleriyle kod inceleme\nAU  - Yılmaz, Ayşe\n"
        "PY  - 2025\nER  - \n"
    )

    imported = import_ris(client, review, ris, source="Google Scholar")

    assert imported["added_to_review"] == 0
    database_run = next(r for r in runs(library, review) if r.method is RunMethod.DATABASE)
    # One paper, found twice: once by hand, once by the database search.
    assert database_run.paper_ids == (by_hand["paper_id"],)
    assert len(reviews_service.records(library.db, review)) == 1
    # Found by hand first, so it keeps that origin.
    assert reviews_service.records(library.db, review)[0].origin is RecordOrigin.MANUAL


def test_an_import_can_be_marked_as_other_methods(
    client: TestClient, library: Library, review: str
) -> None:
    ris = "TY  - RPRT\nTI  - Annual report on code review\nPY  - 2024\nER  - \n"

    import_ris(client, review, ris, source="OECD", method="organisation")

    [run] = runs(library, review)
    assert run.method is RunMethod.ORGANISATION
    assert reviews_service.records(library.db, review)[0].origin is RecordOrigin.MANUAL
    # Other methods are not database searches: the search history leaves them out.
    assert client.get("/searches", params={"review_id": review}).json() == []
    listed = client.get(f"/reviews/{review}/grey-literature").json()
    assert [(e["found_via"], e["source"], e["file_name"], e["titles"]) for e in listed] == [
        ("organisation", "OECD", "export.ris", ["Annual report on code review"])
    ]


@pytest.mark.parametrize(
    "body",
    [
        {**THESIS, "kind": "book"},
        {**THESIS, "found_via": "database"},
        {**THESIS, "title": " "},
        {**THESIS, "source": ""},
        {**THESIS, "year": 3000},
    ],
)
def test_an_invalid_entry_is_rejected(
    client: TestClient, review: str, body: dict[str, Any]
) -> None:
    assert client.post(f"/reviews/{review}/grey-literature", json=body).status_code == 422


def test_an_import_cannot_claim_a_snowballing_method(client: TestClient, review: str) -> None:
    response = client.post(
        "/imports",
        json={
            "file_name": "x.ris",
            "content_base64": base64.b64encode(b"TY  - JOUR\nTI  - X\nER  - \n").decode(),
            "review_id": review,
            "log": {"source": "X", "method": "citation_forward"},
        },
    )
    assert response.status_code == 422
    assert set(GREY_METHODS) >= {RunMethod.WEBSITE, RunMethod.THESIS}
