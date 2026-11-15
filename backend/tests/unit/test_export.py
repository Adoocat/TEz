"""`tez export` behind the scenes: BibTeX and RIS that read back to the same papers."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.export.writers import ExportAuthor, ExportPaper, bibtex_entry
from tez.modules.importers.bibtex import parse_bibtex
from tez.modules.importers.ris import parse_ris
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.library.paper_service import PaperService
from tez.modules.library.repository import AuthorInput
from tez.modules.library.service import Library, open_library
from tez.modules.reviews.models import RecordOrigin, ReviewMethod
from tez.modules.reviews.repository import ReviewsRepository
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


def seed(library: Library) -> tuple[str, str, str]:
    """Two kept papers and a review record that was never kept."""
    with library.db.write_session() as session:
        papers = PaperService(session)
        article = papers.add(
            "LLMs & Code Review: 50% Fewer Bugs?",
            identifiers={IdentifierScheme.DOI: "10.1109/tse.2024.1"},
            authors=[
                AuthorInput("Ayşe Yılmaz", family="Yılmaz", given="Ayşe"),
                AuthorInput("Kees van der Berg", family="van der Berg", given="Kees"),
            ],
            year=2024,
            venue="IEEE Transactions on Software Engineering",
            venue_type=VenueType.JOURNAL,
            volume="50",
            issue="3",
            pages="512\N{EN DASH}530",
        )
        preprint = papers.add(
            "BERT for Review Comments",
            identifiers={IdentifierScheme.ARXIV: "2401.01234"},
            authors=[AuthorInput("IEEE Team")],
            year=2023,
            venue_type=VenueType.PREPRINT,
        )
        candidate = papers.add(
            "Only Screened",
            identifiers={},
            authors=[AuthorInput("Jo Kim", family="Kim")],
            year=2022,
        )
        papers.keep([article.id, preprint.id])
        reviews = ReviewsRepository(session)
        review = reviews.add_review("SLR", method=ReviewMethod.PRISMA2020)
        reviews.add_record(review.id, article.id, RecordOrigin.DATABASE, None)
        reviews.add_record(review.id, candidate.id, RecordOrigin.DATABASE, None)
        return review.id, article.id, candidate.id


def test_bibtex_escapes_latex_and_keeps_case_and_names() -> None:
    entry = bibtex_entry(
        ExportPaper(
            citekey="yilmaz2024llms",
            title="LLMs & Code Review: 50% Fewer Bugs?",
            authors=(
                ExportAuthor("Kees van der Berg", "van der Berg", "Kees"),
                ExportAuthor("IEEE Team", None, None),
            ),
            year=2024,
            venue="TSE",
            venue_type=VenueType.JOURNAL,
            thesis_type=None,
            volume=None,
            issue=None,
            pages="1\N{EN DASH}10",
            doi="10.1/x",
            arxiv=None,
            isbn=None,
            url=None,
            abstract=None,
            language=None,
        )
    )

    assert entry.startswith("@article{yilmaz2024llms,\n")
    assert r"title = {{LLMs \& Code Review: 50\% Fewer Bugs?}}" in entry
    assert "author = {van der Berg, Kees and {IEEE Team}}" in entry
    assert "pages = {1--10}" in entry


@pytest.mark.parametrize("fmt", ["bibtex", "ris"])
def test_the_whole_library_reads_back_the_same(
    client: TestClient, library: Library, fmt: str
) -> None:
    seed(library)

    result = client.get("/export", params={"format": fmt}).json()

    assert (result["format"], result["count"]) == (fmt, 2)
    parsed = (parse_bibtex if fmt == "bibtex" else parse_ris)(result["content"])
    assert parsed.issues == []
    by_title = {e.record.title: e.record for e in parsed.entries}
    article = by_title["LLMs & Code Review: 50% Fewer Bugs?"]
    assert [a.family for a in article.authors] == ["Yılmaz", "van der Berg"]
    assert (article.year, article.venue, article.pages) == (
        2024,
        "IEEE Transactions on Software Engineering",
        "512-530",
    )
    assert article.identifiers[IdentifierScheme.DOI] == "10.1109/tse.2024.1"
    assert by_title["BERT for Review Comments"].venue_type is VenueType.PREPRINT


def test_a_review_exports_its_records_with_keys_for_unkept_papers(
    client: TestClient, library: Library
) -> None:
    review_id, _, _ = seed(library)

    result = client.get("/export", params={"review_id": review_id}).json()

    assert result["count"] == 2
    assert "@article{yilmaz2024llms," in result["content"]
    assert "@misc{kim2022only," in result["content"]  # made for this file, not stored


def test_one_scope_at_a_time_and_unknown_reviews(client: TestClient) -> None:
    both = client.get("/export", params={"review_id": "r", "collection_id": "c"})
    missing = client.get("/export", params={"review_id": "nope"})

    assert both.json()["error"]["code"] == "export.one_scope"
    assert missing.json()["error"]["code"] == "review.not_found"
