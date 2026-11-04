"""arXiv: mapping checked against a recorded real response."""

import asyncio
import xml.etree.ElementTree as ET

import httpx2
import pytest

from tests.unit.providers.conftest import no_sleep, run_with_http
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.models import RunStatus
from tez.modules.search.providers.arxiv import ArxivProvider, map_entry
from tez.modules.search.providers.base import ProviderResult, SearchRequest
from tez.shared.http import HttpClient


class SmallPages(ArxivProvider):
    page_size = 2


def search(request: SearchRequest, provider: type[ArxivProvider] = ArxivProvider) -> ProviderResult:
    return run_with_http(lambda http: provider(http).search(request))


@pytest.mark.vcr
def test_search_maps_a_real_response() -> None:
    result = search(SearchRequest('"code review" AND LLM', limit=3))

    assert result.status is RunStatus.OK
    assert result.translated_query == 'all:"code review" AND all:LLM'
    assert len(result.records) == 3
    assert result.total_reported is not None and result.total_reported >= 3
    for record in result.records:
        assert record.title
        assert record.abstract
        assert record.authors
        assert record.year is not None
        assert record.venue_type is VenueType.PREPRINT
        assert IdentifierScheme.ARXIV in record.identifiers
        assert record.oa_url is not None and "/pdf/" in record.oa_url


@pytest.mark.vcr
def test_paging_moves_the_start_index() -> None:
    result = search(SearchRequest('"code review" AND LLM', limit=3), SmallPages)

    assert len(result.records) == 3
    assert len(result.raw_pages) == 2
    assert len({r.identifiers[IdentifierScheme.ARXIV] for r in result.records}) == 3


@pytest.mark.parametrize(
    ("year_from", "year_to", "expected"),
    [
        (2020, 2024, "(all:llm) AND submittedDate:[202001010000 TO 202412312359]"),
        (2020, None, "(all:llm) AND submittedDate:[202001010000 TO 299912312359]"),
        (None, 2024, "(all:llm) AND submittedDate:[190001010000 TO 202412312359]"),
        (None, None, "all:llm"),
    ],
)
def test_years_become_part_of_the_query(
    year_from: int | None, year_to: int | None, expected: str
) -> None:
    provider = ArxivProvider(HttpClient(sleep=no_sleep))

    assert provider.translate(SearchRequest("llm", year_from, year_to)) == expected


ENTRY = """
<entry xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <id>http://arxiv.org/abs/1803.05689v1</id>
  <title>Using StackOverflow
    content</title>
  <published>2018-03-15T10:58:22Z</published>
  <summary>  An important
    goal. </summary>
  <author><name>Ali Veli</name><arxiv:affiliation>METU</arxiv:affiliation></author>
  <arxiv:doi>10.1000/xyz</arxiv:doi>
  <link href="https://arxiv.org/abs/1803.05689v1" rel="alternate" type="text/html"/>
  <link href="https://arxiv.org/pdf/1803.05689v1" rel="related" title="pdf"/>
</entry>
"""


def test_map_entry_fields() -> None:
    record = map_entry(ET.fromstring(ENTRY))

    assert record.title == "Using StackOverflow content"
    assert record.identifiers == {
        IdentifierScheme.ARXIV: "1803.05689v1",
        IdentifierScheme.DOI: "10.1000/xyz",
    }
    assert record.year == 2018
    assert record.abstract == "An important goal."
    assert record.authors[0].display_name == "Ali Veli"
    assert record.authors[0].affiliation == "METU"
    assert record.url == "https://arxiv.org/abs/1803.05689v1"
    assert record.oa_url == "https://arxiv.org/pdf/1803.05689v1"


def _serve_body(body: str) -> ProviderResult:
    """Run one search whose HTTP call returns `body`, with no network."""

    class Canned:
        async def get(self, *_: object, **__: object) -> httpx2.Response:
            return httpx2.Response(200, text=body)

    provider = ArxivProvider(HttpClient(sleep=no_sleep))
    provider._http = Canned()  # type: ignore[assignment]  # pyright: ignore[reportPrivateUsage, reportAttributeAccessIssue]
    return asyncio.run(provider.search(SearchRequest("llm")))


def test_broken_xml_is_a_source_error() -> None:
    result = _serve_body("<feed><oops")

    assert result.status is RunStatus.ERROR
    assert result.error is not None
    assert result.error.params["reason"] == "not_xml"


def test_an_error_entry_is_a_rejection() -> None:
    body = """<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><id>http://arxiv.org/api/errors#bad_query</id><title>Error</title></entry>
    </feed>"""

    result = _serve_body(body)

    assert result.status is RunStatus.ERROR
    assert result.error is not None
    assert result.error.code.value == "source.rejected"
