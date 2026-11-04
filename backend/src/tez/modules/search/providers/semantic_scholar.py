"""Semantic Scholar bulk search (https://api.semanticscholar.org/api-docs/graph).

Bulk search is the only one with boolean syntax and full-corpus paging, so it fits systematic
searches. It ignores `limit` and returns up to 1000 records per page. Without a key all users
share one pool, so 429 is common; the key goes in the `x-api-key` header, which `HttpClient`
adds below its cache (ADR 0007).
"""

from typing import Any, ClassVar

from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.providers.base import (
    OnWait,
    Page,
    PagedProvider,
    SearchRequest,
    as_dict,
    as_list,
)
from tez.modules.search.providers.query import to_semantic_scholar
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor
from tez.shared.http import HttpClient, SourcePolicy

API_HOST = "api.semanticscholar.org"
_URL = f"https://{API_HOST}/graph/v1/paper/search/bulk"
_FIELDS = (
    "title,abstract,year,venue,publicationVenue,publicationTypes,journal,authors,externalIds,"
    "url,openAccessPdf,citationCount"
)
_ARXIV_VENUE = "arxiv.org"
# In order: a paper with several types takes the first of these it has.
_VENUE_TYPES = (
    ("Conference", VenueType.CONFERENCE),
    ("JournalArticle", VenueType.JOURNAL),
    ("BookSection", VenueType.CHAPTER),
    ("Book", VenueType.BOOK),
)


def semantic_scholar_policy() -> SourcePolicy:
    # The documented keyed limit is one request per second; the shared pool is no faster.
    return SourcePolicy(
        name=SemanticScholarProvider.name, requests_per_second=1.0, backoff_seconds=2.0
    )


def _venue_type(paper: dict[str, Any], venue: str | None) -> VenueType | None:
    if (venue or "").casefold() == _ARXIV_VENUE:
        return VenueType.PREPRINT
    kinds = as_list(paper.get("publicationTypes"))
    return next((venue_type for kind, venue_type in _VENUE_TYPES if kind in kinds), None)


def map_paper(paper: dict[str, Any]) -> NormalizedRecord:
    external = as_dict(paper.get("externalIds"))
    journal = as_dict(paper.get("journal"))
    venue = paper.get("venue") or journal.get("name")
    return NormalizedRecord.model_validate(
        {
            "title": paper.get("title"),
            "authors": tuple(
                RecordAuthor(display_name=as_dict(a).get("name") or "")
                for a in as_list(paper.get("authors"))
            ),
            "year": paper.get("year"),
            "identifiers": {
                IdentifierScheme.S2: paper.get("paperId"),
                IdentifierScheme.DOI: external.get("DOI"),
                IdentifierScheme.ARXIV: external.get("ArXiv"),
                IdentifierScheme.DBLP: external.get("DBLP"),
            },
            "abstract": paper.get("abstract"),
            "venue": venue,
            "venue_type": _venue_type(paper, venue),
            "volume": journal.get("volume"),
            "pages": journal.get("pages"),
            "url": paper.get("url"),
            "oa_url": as_dict(paper.get("openAccessPdf")).get("url"),
            "citation_count": paper.get("citationCount"),
        }
    )


def _year_range(request: SearchRequest) -> str | None:
    if request.year_from is None and request.year_to is None:
        return None
    return f"{request.year_from or ''}-{request.year_to or ''}"


class SemanticScholarProvider(PagedProvider):
    name: str = "semantic_scholar"
    page_size: ClassVar[int] = 1000

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http, semantic_scholar_policy())

    def translate(self, request: SearchRequest) -> str:
        return to_semantic_scholar(request.query)

    async def fetch_page(
        self,
        request: SearchRequest,
        translated: str,
        cursor: str | int | None,
        size: int,
        on_wait: OnWait | None,
    ) -> Page:
        params: dict[str, Any] = {"query": translated, "fields": _FIELDS}
        if years := _year_range(request):
            params["year"] = years
        if cursor is not None:
            params["token"] = cursor
        response = await self._http.get(self._policy, _URL, params=params, on_wait=on_wait)
        body = self.json_object(response)
        if "data" not in body:
            raise self.bad_response("no_results")
        return Page(
            items=as_list(body["data"]),
            raw=response.text,
            total=body.get("total"),
            next_cursor=body.get("token"),
        )

    def map_item(self, item: Any) -> NormalizedRecord:
        return map_paper(item)
