"""Task 28: books, chapters and theses (master's / doctoral) from every source and back out."""

import base64
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.export.writers import ExportPaper, bibtex_entry, ris_entry
from tez.modules.importers.bibtex import parse_bibtex
from tez.modules.importers.ris import parse_ris
from tez.modules.library.models import ThesisType, VenueType
from tez.modules.library.service import Library, open_library
from tez.modules.library.thesis import thesis_type_from_text
from tez.modules.search.providers import arxiv, crossref, openalex, semantic_scholar
from tez.modules.search.providers.base import SearchRequest

MASTERS = ThesisType.MASTERS
DOCTORAL = ThesisType.DOCTORAL


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Master's thesis", MASTERS),
        ("MSc thesis", MASTERS),
        ("mathesis", MASTERS),
        ("Yüksek Lisans Tezi", MASTERS),
        ("YÜKSEK LİSANS", MASTERS),
        ("Doctoral thesis", DOCTORAL),
        ("PhD dissertation", DOCTORAL),
        ("Ph.D. thesis", DOCTORAL),
        ("phdthesis", DOCTORAL),
        ("Doktora Tezi", DOCTORAL),
        ("Sanatta Yeterlik Tezi", DOCTORAL),
        ("Dissertation", None),
        ("", None),
        (None, None),
    ],
)
def test_the_degree_is_read_from_free_text(text: str | None, expected: ThesisType | None) -> None:
    assert thesis_type_from_text(text) is expected


def _bib(entry_type: str, extra: str = "") -> str:
    return f"@{entry_type}{{k,\n  title = {{T}},\n  year = {{2024}},{extra}\n}}\n"


@pytest.mark.parametrize(
    ("entry", "venue_type", "thesis_type"),
    [
        (_bib("mastersthesis", " school = {ODTÜ},"), VenueType.THESIS, MASTERS),
        (_bib("phdthesis", " school = {Boğaziçi},"), VenueType.THESIS, DOCTORAL),
        (_bib("thesis", " type = {mathesis},"), VenueType.THESIS, MASTERS),
        (_bib("thesis", " type = {Doktora Tezi},"), VenueType.THESIS, DOCTORAL),
        (_bib("thesis"), VenueType.THESIS, None),
        (_bib("book", " publisher = {Pegem},"), VenueType.BOOK, None),
        (_bib("incollection", " booktitle = {Handbook},"), VenueType.CHAPTER, None),
        (_bib("inbook"), VenueType.CHAPTER, None),
        (_bib("article", " journal = {J},"), VenueType.JOURNAL, None),
    ],
)
def test_bibtex_types(entry: str, venue_type: VenueType, thesis_type: ThesisType | None) -> None:
    (record,) = parse_bibtex(entry).records
    assert (record.venue_type, record.thesis_type) == (venue_type, thesis_type)


def _ris(kind: str, *lines: str) -> str:
    return "\n".join([f"TY  - {kind}", "TI  - T", *lines, "ER  - ", ""])


@pytest.mark.parametrize(
    ("entry", "venue_type", "thesis_type"),
    [
        (_ris("THES", "M3  - Master's thesis"), VenueType.THESIS, MASTERS),
        (_ris("THES", "M3  - Doktora Tezi"), VenueType.THESIS, DOCTORAL),
        (_ris("THES"), VenueType.THESIS, None),
        (_ris("BOOK"), VenueType.BOOK, None),
        (_ris("CHAP"), VenueType.CHAPTER, None),
        (_ris("JOUR", "M3  - Master's thesis"), VenueType.JOURNAL, None),
    ],
)
def test_ris_types(entry: str, venue_type: VenueType, thesis_type: ThesisType | None) -> None:
    (record,) = parse_ris(entry).records
    assert (record.venue_type, record.thesis_type) == (venue_type, thesis_type)


@pytest.mark.parametrize(
    ("work_type", "source_type", "expected"),
    [
        ("dissertation", "repository", VenueType.THESIS),
        ("book", None, VenueType.BOOK),
        ("book-chapter", "book series", VenueType.CHAPTER),
        ("article", "journal", VenueType.JOURNAL),
        ("article", "conference", VenueType.CONFERENCE),
        ("preprint", "repository", VenueType.PREPRINT),
        ("report", None, VenueType.REPORT),
        ("article", None, None),
    ],
)
def test_openalex_types(work_type: str, source_type: str | None, expected: VenueType) -> None:
    work: dict[str, Any] = {"title": "T", "type": work_type}
    if source_type:
        work["primary_location"] = {"source": {"type": source_type, "display_name": "S"}}
    record = openalex.map_work(work)
    # OpenAlex does not say which degree a dissertation is for.
    assert (record.venue_type, record.thesis_type) == (expected, None)


@pytest.mark.parametrize(
    ("item_type", "expected"),
    [
        ("dissertation", VenueType.THESIS),
        ("book", VenueType.BOOK),
        ("monograph", VenueType.BOOK),
        ("book-chapter", VenueType.CHAPTER),
        ("journal-article", VenueType.JOURNAL),
        ("proceedings-article", VenueType.CONFERENCE),
        ("report", VenueType.REPORT),
        ("dataset", None),
    ],
)
def test_crossref_types(item_type: str, expected: VenueType | None) -> None:
    record = crossref.map_work({"title": ["T"], "type": item_type})
    assert (record.venue_type, record.thesis_type) == (expected, None)


@pytest.mark.parametrize(
    ("kinds", "expected"),
    [
        (["Book"], VenueType.BOOK),
        (["BookSection"], VenueType.CHAPTER),
        (["JournalArticle"], VenueType.JOURNAL),
        (["Conference"], VenueType.CONFERENCE),
        (["Review"], None),
    ],
)
def test_semantic_scholar_types(kinds: list[str], expected: VenueType | None) -> None:
    record = semantic_scholar.map_paper({"title": "T", "publicationTypes": kinds})
    assert (record.venue_type, record.thesis_type) == (expected, None)


def test_arxiv_entries_are_preprints() -> None:
    atom = "http://www.w3.org/2005/Atom"
    entry = ET.fromstring(
        f'<entry xmlns="{atom}"><id>http://arxiv.org/abs/2401.00001v1</id><title>T</title></entry>'
    )
    record = arxiv.map_entry(entry)
    assert (record.venue_type, record.thesis_type) == (VenueType.PREPRINT, None)


def _paper(venue_type: VenueType, thesis_type: ThesisType | None) -> ExportPaper:
    return ExportPaper(
        citekey="yilmaz2024",
        title="Öğretmen adaylarının dijital okuryazarlığı",
        authors=(),
        year=2024,
        venue="Hacettepe Üniversitesi",
        venue_type=venue_type,
        thesis_type=thesis_type,
        volume=None,
        issue=None,
        pages=None,
        doi=None,
        arxiv=None,
        isbn=None,
        url=None,
        abstract=None,
        language=None,
    )


ROUND_TRIP = [
    (VenueType.THESIS, MASTERS),
    (VenueType.THESIS, DOCTORAL),
    (VenueType.THESIS, None),
    (VenueType.BOOK, None),
    (VenueType.CHAPTER, None),
]


@pytest.mark.parametrize(("venue_type", "thesis_type"), ROUND_TRIP)
def test_bibtex_round_trip_keeps_the_type(
    venue_type: VenueType, thesis_type: ThesisType | None
) -> None:
    (record,) = parse_bibtex(bibtex_entry(_paper(venue_type, thesis_type))).records
    assert (record.venue_type, record.thesis_type, record.venue) == (
        venue_type,
        thesis_type,
        "Hacettepe Üniversitesi",
    )


@pytest.mark.parametrize(("venue_type", "thesis_type"), ROUND_TRIP)
def test_ris_round_trip_keeps_the_type(
    venue_type: VenueType, thesis_type: ThesisType | None
) -> None:
    (record,) = parse_ris(ris_entry(_paper(venue_type, thesis_type))).records
    assert (record.venue_type, record.thesis_type, record.venue) == (
        venue_type,
        thesis_type,
        "Hacettepe Üniversitesi",
    )


def test_the_bibtex_entry_types_of_theses() -> None:
    assert bibtex_entry(_paper(VenueType.THESIS, MASTERS)).startswith("@mastersthesis{")
    assert bibtex_entry(_paper(VenueType.THESIS, DOCTORAL)).startswith("@phdthesis{")
    assert bibtex_entry(_paper(VenueType.THESIS, None)).startswith("@thesis{")
    assert "M3  - Master's thesis" in ris_entry(_paper(VenueType.THESIS, MASTERS))


@pytest.mark.parametrize(
    ("request_", "expected"),
    [
        (SearchRequest(query="q", theses_only=True), "type:dissertation"),
        (
            SearchRequest(query="q", year_from=2020, year_to=2024, theses_only=True),
            "publication_year:2020-2024,type:dissertation",
        ),
        (SearchRequest(query="q", year_from=2020, year_to=2024), "publication_year:2020-2024"),
        (SearchRequest(query="q"), None),
    ],
)
def test_openalex_filters_dissertations(request_: SearchRequest, expected: str | None) -> None:
    assert openalex.work_filter(request_) == expected


def test_crossref_filters_dissertations() -> None:
    request = SearchRequest(query="q", year_from=2020, theses_only=True)
    assert crossref.work_filter(request) == "from-pub-date:2020,type:dissertation"


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


def test_a_theses_only_search_needs_sources_that_can_filter(client: TestClient) -> None:
    review_id = client.post("/reviews", json={"title": "SLR"}).json()["id"]

    response = client.post(
        "/searches",
        json={
            "review_id": review_id,
            "query": "öğretmen",
            "sources": ["openalex", "semantic_scholar", "arxiv"],
            "theses_only": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "search.filter_unsupported",
        "params": {"sources": ["semantic_scholar", "arxiv"]},
    }


def test_an_imported_thesis_keeps_its_degree(client: TestClient) -> None:
    data = _bib("mastersthesis", " school = {ODTÜ},").encode()
    imported = client.post(
        "/imports",
        json={
            "file_name": "t.bib",
            "content_base64": base64.b64encode(data).decode(),
            "add_to_library": True,
        },
    )
    assert imported.status_code == 201, imported.text

    (row,) = client.get("/papers").json()
    detail = client.get(f"/papers/{row['id']}").json()

    assert (row["venue_type"], row["thesis_type"]) == ("thesis", "masters")
    assert detail["thesis_type"] == "masters"
