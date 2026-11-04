"""OpenAlex: mapping checked against a recorded real response."""

from typing import Any

import httpx2
import pytest

from tests.unit.providers.conftest import no_sleep, run_with_http
from tez.core.errors import ErrorCode, TezError
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.models import RunStatus
from tez.modules.search.providers.base import ProviderResult, SearchRequest
from tez.modules.search.providers.openalex import OpenAlexProvider, map_work
from tez.shared.http import HttpClient


def search(request: SearchRequest) -> ProviderResult:
    return run_with_http(lambda http: OpenAlexProvider(http).search(request))


def provider_offline() -> OpenAlexProvider:
    return OpenAlexProvider(HttpClient(sleep=no_sleep))


@pytest.mark.vcr
def test_search_maps_a_real_response() -> None:
    result = search(SearchRequest('"code review" AND LLM', year_from=2023, year_to=2025, limit=5))

    assert result.status is RunStatus.OK
    assert result.translated_query == '"code review" AND LLM'
    assert len(result.records) == 5
    assert result.total_reported is not None and result.total_reported >= 5
    assert result.skipped == 0
    assert len(result.raw_pages) == 1
    for record in result.records:
        assert record.title
        assert record.authors
        assert record.year is not None and 2023 <= record.year <= 2025
        assert record.identifiers[IdentifierScheme.OPENALEX].startswith("W")
    assert any(r.abstract for r in result.records)


class SmallPages(OpenAlexProvider):
    page_size = 3


@pytest.mark.vcr
def test_without_a_key_only_the_first_page_comes_and_the_run_says_why() -> None:
    """OpenAlex answers 401 to a cursor without a key, so we do not ask for the second page."""
    request = SearchRequest('"code review" AND LLM', limit=5)

    result = run_with_http(lambda http: SmallPages(http).search(request))

    assert len(result.records) == 3
    assert len(result.raw_pages) == 1
    assert result.status is RunStatus.PARTIAL
    assert result.error is not None
    assert result.error.code is ErrorCode.SOURCE_KEY_REQUIRED


def test_an_empty_query_is_not_sent() -> None:
    result = search(SearchRequest("  AND  "))

    assert result.status is RunStatus.ERROR
    assert result.error is not None
    assert result.error.code is ErrorCode.SOURCE_QUERY_UNSUPPORTED


WORK: dict[str, Any] = {
    "id": "https://openalex.org/W4394745423",
    "doi": "https://doi.org/10.1145/3597503.3639187",
    "title": "Using an LLM to Help With Code Understanding",
    "publication_year": 2024,
    "type": "article",
    "language": "en",
    "cited_by_count": 374,
    "is_retracted": False,
    "abstract_inverted_index": {"LLMs": [0], "help": [1, 3], "really": [2]},
    "authorships": [
        {
            "author": {
                "display_name": "Daye Nam",
                "orcid": "https://orcid.org/0009-0006-3846-6924",
            },
            "raw_affiliation_strings": ["Carnegie Mellon University, Pittsburgh"],
        }
    ],
    "primary_location": {
        "landing_page_url": "https://doi.org/10.1145/3597503.3639187",
        "source": {"display_name": "ICSE", "type": "conference"},
    },
    "best_oa_location": {"pdf_url": "https://dl.acm.org/doi/pdf/10.1145/3597503.3639187"},
    "biblio": {"volume": None, "issue": None, "first_page": "1", "last_page": "13"},
}


def test_map_work_fields() -> None:
    record = map_work(WORK)

    assert record.title == "Using an LLM to Help With Code Understanding"
    assert record.identifiers == {
        IdentifierScheme.OPENALEX: "W4394745423",
        IdentifierScheme.DOI: "10.1145/3597503.3639187",
    }
    assert record.abstract == "LLMs help really help"
    assert record.venue == "ICSE"
    assert record.venue_type is VenueType.CONFERENCE
    assert record.pages == "1-13"
    assert record.oa_url == "https://dl.acm.org/doi/pdf/10.1145/3597503.3639187"
    assert record.citation_count == 374
    assert record.authors[0].orcid == "0009-0006-3846-6924"
    assert record.authors[0].affiliation == "Carnegie Mellon University, Pittsburgh"


def test_map_work_survives_missing_sections() -> None:
    record = map_work({"id": "https://openalex.org/W1", "title": "Bare"})

    assert record.title == "Bare"
    assert record.authors == ()
    assert record.identifiers == {IdentifierScheme.OPENALEX: "W1"}


def test_a_work_with_no_title_is_skipped_and_the_rest_are_kept() -> None:
    mapped, failed = provider_offline().map_all([{"id": "x"}, WORK])

    assert failed == 1
    assert [r.year for r in mapped] == [2024]


def test_a_bot_check_page_is_a_source_error_not_a_crash() -> None:
    with pytest.raises(TezError) as caught:
        provider_offline().json_object(httpx2.Response(202, text="<html>not a bot?</html>"))

    assert caught.value.code is ErrorCode.SOURCE_BAD_RESPONSE
