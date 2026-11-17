"""What the export screen (Task 40) asks of the backend: BibTeX/RIS of a review's included
studies or of chosen papers, the citation keys for the key-format preview, and the search
strategy table with one row per search run."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.library.paper_service import PaperService
from tez.modules.library.repository import AuthorInput
from tez.modules.library.service import Library, open_library
from tez.modules.reviews.models import Decision, RecordOrigin, ReviewMethod, ScreeningStage
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.screening.service import ScreeningService
from tez.modules.search.models import InitiatedVia, MatchMethod, RunMethod, RunStatus
from tez.modules.search.repository import ResultInput, SearchRepository
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


def _seed(library: Library) -> tuple[str, list[str]]:
    """A review with three papers, found by an API search, an imported file and a backward
    snowballing step; the first is included at full text."""
    with library.db.write_session() as session:
        papers = PaperService(session)
        added = [
            papers.add(
                title,
                identifiers={IdentifierScheme.DOI: f"10.1/{family.lower()}"},
                authors=[AuthorInput(f"Ayşe {family}", family=family, given="Ayşe")],
                year=2020,
                venue="Eğitim ve Bilim",
                venue_type=VenueType.JOURNAL,
            )
            for title, family in (("Birinci", "Akın"), ("İkinci", "Bal"), ("Üçüncü", "Can"))
        ]
        papers.keep([paper.id for paper in added])
        reviews = ReviewsRepository(session)
        review = reviews.add_review("SLR", method=ReviewMethod.PRISMA2020)
        for paper in added:
            reviews.add_record(review.id, paper.id, RecordOrigin.DATABASE, None)
        search = SearchRepository(session)

        def found(*indexes: int) -> list[ResultInput]:
            return [ResultInput(added[i].id, MatchMethod.NEW) for i in indexes]

        search.add_run(
            review.id,
            source="openalex",
            executed_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
            initiated_via=InitiatedVia.GUI,
            status=RunStatus.OK,
            results=found(0, 1),
            search_id="s1",
            translated_query='title_and_abstract.search:("öğretmen" AND "tükenmişlik")',
            total_reported=128,
        )
        search.add_run(
            review.id,
            source="Scopus",
            executed_at=datetime(2026, 3, 2, 10, 0, tzinfo=UTC),
            initiated_via=InitiatedVia.GUI,
            status=RunStatus.OK,
            results=found(1, 2),
            search_id="s2",
            translated_query='TITLE-ABS-KEY("teacher burnout")',
            file_name="scopus.ris",
        )
        search.add_run(
            review.id,
            source="openalex",
            executed_at=datetime(2026, 3, 5, 11, 0, tzinfo=UTC),
            initiated_via=InitiatedVia.GUI,
            status=RunStatus.OK,
            results=found(2),
            method=RunMethod.CITATION_BACKWARD,
            snowball_round=1,
            seed_paper_id=added[0].id,
        )
        screening = ScreeningService(session)
        for paper in added:
            screening.decide(review.id, paper.id, ScreeningStage.TITLE_ABSTRACT, Decision.INCLUDE)
        screening.decide(review.id, added[0].id, ScreeningStage.FULL_TEXT, Decision.INCLUDE)
        return review.id, [paper.id for paper in added]


def test_the_strategy_table_has_every_search_run(client: TestClient, library: Library) -> None:
    review_id, _ = _seed(library)

    rows = client.get("/export/search-strategy", params={"review_id": review_id}).json()["rows"]

    assert [
        (r["source"], r["method"], r["executed_at"][:10], r["total_reported"], r["retrieved"])
        for r in rows
    ] == [
        ("openalex", "database", "2026-03-01", 128, 2),
        ("Scopus", "database", "2026-03-02", None, 2),
        ("openalex", "citation_backward", "2026-03-05", None, 1),
    ]
    assert rows[0]["query"] == 'title_and_abstract.search:("öğretmen" AND "tükenmişlik")'
    assert (rows[1]["file_name"], rows[2]["snowball_round"]) == ("scopus.ris", 1)


def test_the_strategy_of_an_unknown_review(client: TestClient) -> None:
    missing = client.get("/export/search-strategy", params={"review_id": "nope"})

    assert missing.json()["error"]["code"] == "review.not_found"


def test_bibtex_of_the_included_studies_and_of_chosen_papers(
    client: TestClient, library: Library
) -> None:
    review_id, ids = _seed(library)

    every = client.get("/export", params={"review_id": review_id}).json()
    included = client.get("/export", params={"review_id": review_id, "included": True}).json()
    chosen = client.post(
        "/export/references", json={"format": "ris", "paper_ids": [ids[2], ids[1]]}
    ).json()

    assert every["citekeys"] == ["akin2020birinci", "bal2020ikinci", "can2020ucuncu"]
    assert (included["count"], included["citekeys"]) == (1, ["akin2020birinci"])
    assert chosen["citekeys"] == ["bal2020ikinci", "can2020ucuncu"]
    assert chosen["content"].startswith("TY  - JOUR\nID  - bal2020ikinci\n")
