"""Semantic Scholar: mapping checked against a recorded real response."""

from typing import Any

import pytest

from tests.unit.providers.conftest import run_with_http
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.models import RunStatus
from tez.modules.search.providers.base import ProviderResult, SearchRequest
from tez.modules.search.providers.semantic_scholar import SemanticScholarProvider, map_paper


def search(request: SearchRequest) -> ProviderResult:
    return run_with_http(lambda http: SemanticScholarProvider(http).search(request))


@pytest.mark.vcr
def test_search_maps_a_real_response_and_cuts_at_the_limit() -> None:
    """The source ignores `limit` and sends up to 1000 records."""
    result = search(SearchRequest('"code review" AND LLM NOT survey', limit=3))

    assert result.status is RunStatus.OK
    assert result.translated_query == '"code review" LLM -survey'
    assert len(result.records) == 3
    assert result.total_reported is not None and result.total_reported >= 3
    for record in result.records:
        assert record.title
        assert record.authors
        assert IdentifierScheme.S2 in record.identifiers
    assert any(IdentifierScheme.DOI in r.identifiers for r in result.records)


PAPER: dict[str, Any] = {
    "paperId": "008f84c2d5828481504d5cce64706a4c798d2d00",
    "externalIds": {
        "ArXiv": "2507.19902",
        "DBLP": "journals/corr/abs-2507-19902",
        "DOI": "10.48550/arXiv.2507.19902",
        "CorpusId": 280323932,
    },
    "publicationVenue": {"name": "arXiv.org"},
    "url": "https://www.semanticscholar.org/paper/008f84c2",
    "title": "AgentMesh",
    "venue": "arXiv.org",
    "year": 2025,
    "citationCount": 14,
    "openAccessPdf": {"url": "", "status": None},
    "publicationTypes": ["JournalArticle", "Review"],
    "journal": {"name": "ArXiv", "volume": "abs/2507.19902"},
    "authors": [{"authorId": "2217185453", "name": "S. Khanzadeh"}],
    "abstract": "Software development…",
}


def test_map_paper_fields() -> None:
    record = map_paper(PAPER)

    assert record.identifiers == {
        IdentifierScheme.S2: "008f84c2d5828481504d5cce64706a4c798d2d00",
        IdentifierScheme.DOI: "10.48550/arXiv.2507.19902",
        IdentifierScheme.ARXIV: "2507.19902",
        IdentifierScheme.DBLP: "journals/corr/abs-2507-19902",
    }
    assert record.authors[0].display_name == "S. Khanzadeh"
    assert record.venue_type is VenueType.PREPRINT  # Not "journal", despite publicationTypes.
    assert record.oa_url is None  # The source sends an empty string.
    assert record.citation_count == 14


@pytest.mark.parametrize(
    ("kinds", "expected"),
    [
        (["Conference"], VenueType.CONFERENCE),
        (["JournalArticle"], VenueType.JOURNAL),
        (["JournalArticle", "Conference"], VenueType.CONFERENCE),
        (["BookSection"], VenueType.CHAPTER),
        (["Review"], None),
        (None, None),
    ],
)
def test_venue_types(kinds: list[str] | None, expected: VenueType | None) -> None:
    paper = {"title": "x", "venue": "ICSE", "publicationTypes": kinds}

    assert map_paper(paper).venue_type is expected


def test_map_paper_survives_missing_sections() -> None:
    record = map_paper({"paperId": "abc", "title": "Bare", "journal": None, "authors": None})

    assert record.authors == ()
    assert record.identifiers == {IdentifierScheme.S2: "abc"}
