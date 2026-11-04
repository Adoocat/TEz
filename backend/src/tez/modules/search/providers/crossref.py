"""Crossref REST API (https://api.crossref.org). Limits checked on 2026-11-04.

`query.bibliographic` has no boolean logic: it is a bag of words ranked by score, so what it
returns is broad and the translated query records exactly what was asked. With a `mailto`
parameter list queries get 3 requests per second, without it 1. Cursor paging ignores relevance
unless `sort=score` is set.
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
from tez.modules.search.providers.query import to_keywords
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor
from tez.shared.http import HttpClient, SourcePolicy
from tez.shared.text import strip_markup

_URL = "https://api.crossref.org/works"
_FIELDS = (
    "DOI,title,author,issued,container-title,type,volume,issue,page,URL,abstract,"
    "is-referenced-by-count,updated-by"
)
_POLITE_RATE = 3.0
_PUBLIC_RATE = 1.0
_VENUE_TYPES = {
    "journal-article": VenueType.JOURNAL,
    "proceedings-article": VenueType.CONFERENCE,
    "posted-content": VenueType.PREPRINT,
    "book": VenueType.BOOK,
    "monograph": VenueType.BOOK,
    "edited-book": VenueType.BOOK,
    "reference-book": VenueType.BOOK,
    "book-chapter": VenueType.CHAPTER,
    "book-section": VenueType.CHAPTER,
    "book-part": VenueType.CHAPTER,
    "dissertation": VenueType.THESIS,
    "report": VenueType.REPORT,
}


def crossref_policy(*, polite: bool = False) -> SourcePolicy:
    return SourcePolicy(
        name=CrossrefProvider.name, requests_per_second=_POLITE_RATE if polite else _PUBLIC_RATE
    )


def _first(value: Any) -> Any:
    items = as_list(value)
    return items[0] if items else None


def _author(author: dict[str, Any]) -> RecordAuthor:
    given, family = author.get("given"), author.get("family")
    name = " ".join(part for part in (given, family) if part) or author.get("name") or ""
    return RecordAuthor(
        display_name=name,
        family=family,
        given=given,
        orcid=author.get("ORCID"),
        affiliation=as_dict(_first(author.get("affiliation"))).get("name"),
    )


def _year(item: dict[str, Any]) -> Any:
    return _first(_first(as_dict(item.get("issued")).get("date-parts")))


def _clean(value: Any) -> str | None:
    return strip_markup(value) if isinstance(value, str) else None


def map_work(item: dict[str, Any]) -> NormalizedRecord:
    updates = as_list(item.get("updated-by"))
    return NormalizedRecord.model_validate(
        {
            "title": _clean(_first(item.get("title"))),
            "authors": tuple(_author(a) for a in as_list(item.get("author"))),
            "year": _year(item),
            "identifiers": {IdentifierScheme.DOI: item.get("DOI")},
            "abstract": _clean(item.get("abstract")),
            "venue": _clean(_first(item.get("container-title"))),
            "venue_type": _VENUE_TYPES.get(item.get("type") or ""),
            "volume": item.get("volume"),
            "issue": item.get("issue"),
            "pages": item.get("page"),
            "url": item.get("URL"),
            "citation_count": item.get("is-referenced-by-count"),
            "is_retracted": any(as_dict(u).get("type") == "retraction" for u in updates),
        }
    )


def _date_filter(request: SearchRequest) -> str | None:
    parts: list[str] = []
    if request.year_from is not None:
        parts.append(f"from-pub-date:{request.year_from}")
    if request.year_to is not None:
        parts.append(f"until-pub-date:{request.year_to}")
    return ",".join(parts) or None


class CrossrefProvider(PagedProvider):
    name: ClassVar[str] = "crossref"
    page_size: ClassVar[int] = 100

    def __init__(self, http: HttpClient, *, email: str | None = None) -> None:
        super().__init__(http, crossref_policy(polite=email is not None))
        self._email = email

    def translate(self, request: SearchRequest) -> str:
        return to_keywords(request.query)

    async def fetch_page(
        self,
        request: SearchRequest,
        translated: str,
        cursor: str | int | None,
        size: int,
        on_wait: OnWait | None,
    ) -> Page:
        params: dict[str, Any] = {
            "query.bibliographic": translated,
            "rows": size,
            "cursor": cursor or "*",
            "sort": "score",
            "order": "desc",
            "select": _FIELDS,
        }
        if dates := _date_filter(request):
            params["filter"] = dates
        if self._email is not None:
            params["mailto"] = self._email
        response = await self._http.get(self._policy, _URL, params=params, on_wait=on_wait)
        message = self.json_object(response).get("message")
        if not isinstance(message, dict) or "items" not in message:
            raise self.bad_response("no_results")
        body = as_dict(message)
        items = as_list(body["items"])
        return Page(
            items=items,
            raw=response.text,
            total=body.get("total-results"),
            # Crossref always sends a next cursor; a short page is how it says "done".
            next_cursor=body.get("next-cursor") if len(items) == size else None,
        )

    def map_item(self, item: Any) -> NormalizedRecord:
        return map_work(item)
