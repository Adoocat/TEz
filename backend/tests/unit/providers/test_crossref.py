"""Crossref: mapping checked against a recorded real response."""

from typing import Any

import pytest

from tests.unit.providers.conftest import run_with_http
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.models import RunStatus
from tez.modules.search.providers.base import ProviderResult, SearchRequest
from tez.modules.search.providers.crossref import CrossrefProvider, crossref_policy, map_work


class SmallPages(CrossrefProvider):
    page_size = 2


def search(
    request: SearchRequest, provider: type[CrossrefProvider] = CrossrefProvider
) -> ProviderResult:
    return run_with_http(lambda http: provider(http).search(request))


@pytest.mark.vcr
def test_search_maps_a_real_response() -> None:
    result = search(
        SearchRequest('"code review" AND LLM NOT survey', year_from=2023, year_to=2025, limit=3)
    )

    assert result.status is RunStatus.OK
    assert result.translated_query == "code review LLM"  # Crossref has no boolean logic.
    assert len(result.records) == 3
    assert result.total_reported is not None and result.total_reported >= 3
    for record in result.records:
        assert record.title
        assert IdentifierScheme.DOI in record.identifiers
        assert record.year is not None and 2023 <= record.year <= 2025


@pytest.mark.vcr
def test_paging_follows_the_cursor() -> None:
    result = search(SearchRequest("code review llm", limit=3), SmallPages)

    assert len(result.records) == 3
    assert len(result.raw_pages) == 2
    assert len({r.identifiers[IdentifierScheme.DOI] for r in result.records}) == 3


def test_an_email_opens_the_polite_pool() -> None:
    assert crossref_policy(polite=True).requests_per_second == 3
    assert crossref_policy().requests_per_second == 1


WORK: dict[str, Any] = {
    "DOI": "10.1145/1234.5678",
    "title": ["Kod &amp; <i>Inceleme</i>"],
    "author": [
        {
            "given": "Ayşe",
            "family": "Yılmaz",
            "ORCID": "https://orcid.org/0000-0002-1825-0097",
            "affiliation": [{"name": "ODTÜ"}],
        },
        {"name": "The TEz Consortium", "affiliation": []},
    ],
    "issued": {"date-parts": [[2024, 5, 1]]},
    "container-title": ["Empirical Software Engineering"],
    "type": "journal-article",
    "volume": "29",
    "issue": "3",
    "page": "1-20",
    "URL": "https://doi.org/10.1145/1234.5678",
    "abstract": "<jats:title>Abstract</jats:title><jats:p>We study\n  reviews.</jats:p>",
    "is-referenced-by-count": 7,
}


def test_map_work_fields() -> None:
    record = map_work(WORK)

    assert record.title == "Kod & Inceleme"
    assert record.identifiers == {IdentifierScheme.DOI: "10.1145/1234.5678"}
    assert record.year == 2024
    assert record.venue == "Empirical Software Engineering"
    assert record.venue_type is VenueType.JOURNAL
    assert record.abstract == "Abstract We study reviews."
    assert record.pages == "1-20"
    assert record.citation_count == 7
    first, second = record.authors
    assert first.display_name == "Ayşe Yılmaz"
    assert first.orcid == "0000-0002-1825-0097"
    assert first.affiliation == "ODTÜ"
    assert second.display_name == "The TEz Consortium"
    assert second.affiliation is None


def test_a_retraction_notice_marks_the_paper() -> None:
    retracted = {"title": ["x"], "updated-by": [{"type": "retraction"}]}
    corrected = {"title": ["x"], "updated-by": [{"type": "correction"}]}

    assert map_work(retracted).is_retracted is True
    assert map_work(corrected).is_retracted is False


@pytest.mark.parametrize(
    "issued", [None, {}, {"date-parts": []}, {"date-parts": [[]]}, {"date-parts": [[None]]}]
)
def test_a_missing_date_means_an_unknown_year(issued: Any) -> None:
    assert map_work({"title": ["x"], "issued": issued}).year is None
