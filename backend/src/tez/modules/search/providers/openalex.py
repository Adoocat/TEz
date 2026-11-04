"""OpenAlex (https://help.openalex.org/). Docs checked on 2026-11-04.

`search=` takes boolean syntax directly. Without a key, a network shares one small daily budget,
anonymous search can be paused under load and paging stops after the first page; a free key
avoids all three. The key goes in the `Authorization` header, which `HttpClient` adds below its
cache (ADR 0007). OpenAlex no longer uses the `mailto` parameter.
"""

from typing import Any, ClassVar

from tez.core.errors import ErrorCode, TezError
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.providers.base import (
    OnWait,
    Page,
    PagedProvider,
    SearchRequest,
    as_dict,
    as_list,
)
from tez.modules.search.providers.query import to_openalex
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor
from tez.shared.http import HttpClient, SourcePolicy

API_HOST = "api.openalex.org"
_URL = f"https://{API_HOST}/works"
_FIELDS = (
    "id,doi,title,publication_year,type,language,cited_by_count,is_retracted,authorships,"
    "primary_location,best_oa_location,biblio,abstract_inverted_index"
)
# Searches with more than a few boolean operators have the lower limit, so plan for it.
_ANONYMOUS_RATE = 1.0
_KEYED_RATE = 5.0
_SOURCE_VENUE_TYPES = {
    "journal": VenueType.JOURNAL,
    "conference": VenueType.CONFERENCE,
    "repository": VenueType.PREPRINT,
    "book series": VenueType.BOOK,
    "ebook platform": VenueType.BOOK,
}
_WORK_VENUE_TYPES = {
    "preprint": VenueType.PREPRINT,
    "book": VenueType.BOOK,
    "book-chapter": VenueType.CHAPTER,
    "dissertation": VenueType.THESIS,
    "report": VenueType.REPORT,
}


def openalex_policy(*, has_key: bool = False) -> SourcePolicy:
    return SourcePolicy(
        name=OpenAlexProvider.name, requests_per_second=_KEYED_RATE if has_key else _ANONYMOUS_RATE
    )


def _after_slash(url: str | None) -> str | None:
    return url.rsplit("/", 1)[-1] if url else None


def _doi(url: str | None) -> str | None:
    return url.removeprefix("https://doi.org/") if url else None


def _abstract(inverted: dict[str, Any]) -> str | None:
    """OpenAlex sends abstracts as {word: [positions]}."""
    positioned = [(pos, word) for word, spots in inverted.items() for pos in as_list(spots)]
    return " ".join(word for _, word in sorted(positioned)) or None


def _pages(biblio: dict[str, Any]) -> str | None:
    first, last = biblio.get("first_page"), biblio.get("last_page")
    if first and last and first != last:
        return f"{first}-{last}"
    return first or last


def _author(authorship: dict[str, Any]) -> RecordAuthor:
    person = as_dict(authorship.get("author"))
    raw = as_list(authorship.get("raw_affiliation_strings"))
    return RecordAuthor(
        display_name=person.get("display_name") or authorship.get("raw_author_name") or "",
        orcid=person.get("orcid"),
        affiliation=raw[0] if raw else None,
    )


def map_work(work: dict[str, Any]) -> NormalizedRecord:
    primary = as_dict(work.get("primary_location"))
    source = as_dict(primary.get("source"))
    best_oa = as_dict(work.get("best_oa_location"))
    biblio = as_dict(work.get("biblio"))
    venue_type = _WORK_VENUE_TYPES.get(work.get("type") or "") or _SOURCE_VENUE_TYPES.get(
        source.get("type") or ""
    )
    return NormalizedRecord.model_validate(
        {
            "title": work.get("title"),
            "authors": tuple(_author(a) for a in as_list(work.get("authorships"))),
            "year": work.get("publication_year"),
            "identifiers": {
                IdentifierScheme.OPENALEX: _after_slash(work.get("id")),
                IdentifierScheme.DOI: _doi(work.get("doi")),
            },
            "abstract": _abstract(as_dict(work.get("abstract_inverted_index"))),
            "venue": source.get("display_name"),
            "venue_type": venue_type,
            "volume": biblio.get("volume"),
            "issue": biblio.get("issue"),
            "pages": _pages(biblio),
            "language": work.get("language"),
            "url": primary.get("landing_page_url") or work.get("doi"),
            "oa_url": best_oa.get("pdf_url"),
            "citation_count": work.get("cited_by_count"),
            "is_retracted": bool(work.get("is_retracted")),
        }
    )


class OpenAlexProvider(PagedProvider):
    name: ClassVar[str] = "openalex"
    page_size: ClassVar[int] = 100

    def __init__(self, http: HttpClient, *, has_key: bool = False) -> None:
        super().__init__(http, openalex_policy(has_key=has_key))
        self._has_key = has_key

    def translate(self, request: SearchRequest) -> str:
        return to_openalex(request.query)

    async def fetch_page(
        self,
        request: SearchRequest,
        translated: str,
        cursor: str | int | None,
        size: int,
        on_wait: OnWait | None,
    ) -> Page:
        if cursor is not None and not self._has_key:
            raise TezError(ErrorCode.SOURCE_KEY_REQUIRED, {"source": self.name}, status=502)
        params: dict[str, Any] = {
            "search": translated,
            "per_page": size,
            "cursor": cursor or "*",
            "select": _FIELDS,
        }
        if years := _year_filter(request):
            params["filter"] = years
        response = await self._http.get(self._policy, _URL, params=params, on_wait=on_wait)
        body = self.json_object(response)
        if "results" not in body:
            raise self.bad_response("no_results")
        meta = as_dict(body.get("meta"))
        return Page(
            items=as_list(body["results"]),
            raw=response.text,
            total=meta.get("count"),
            next_cursor=meta.get("next_cursor"),
        )

    def map_item(self, item: Any) -> NormalizedRecord:
        return map_work(item)


def _year_filter(request: SearchRequest) -> str | None:
    match request.year_from, request.year_to:
        case None, None:
            return None
        case int() as start, int() as end:
            return f"publication_year:{start}-{end}"
        case int() as start, None:
            return f"publication_year:>{start - 1}"
        case _, end:
            return f"publication_year:<{(end or 0) + 1}"
