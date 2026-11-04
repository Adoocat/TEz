"""arXiv (https://info.arxiv.org/help/api/user-manual.html). Docs checked on 2026-11-04.

The API answers in Atom XML and asks for three seconds between calls. ElementTree does not fetch
external entities, and the bundled expat limits entity expansion, so it is safe for this input.
"""

import xml.etree.ElementTree as ET
from typing import Any, ClassVar

from tez.core.errors import ErrorCode, TezError
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.providers.base import OnWait, Page, PagedProvider, SearchRequest
from tez.modules.search.providers.query import to_arxiv
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor
from tez.shared.http import HttpClient, SourcePolicy

_URL = "https://export.arxiv.org/api/query"
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}
_ABS_PATH = "/abs/"
_ERROR_PATH = "/api/errors"
_EARLIEST_YEAR = 1900
_LATEST_YEAR = 2999


def arxiv_policy() -> SourcePolicy:
    return SourcePolicy(name=ArxivProvider.name, requests_per_second=1 / 3)


def _text(element: ET.Element, path: str) -> str | None:
    found = element.find(path, _NS)
    return found.text if found is not None else None


def _author(element: ET.Element) -> RecordAuthor:
    return RecordAuthor(
        display_name=_text(element, "atom:name") or "",
        affiliation=_text(element, "arxiv:affiliation"),
    )


def _link(entry: ET.Element, attribute: str, value: str) -> str | None:
    for link in entry.findall("atom:link", _NS):
        if link.get(attribute) == value:
            return link.get("href")
    return None


def map_entry(entry: ET.Element) -> NormalizedRecord:
    published = _text(entry, "atom:published") or ""
    entry_id = _text(entry, "atom:id") or ""
    return NormalizedRecord.model_validate(
        {
            "title": _text(entry, "atom:title"),
            "authors": tuple(_author(a) for a in entry.findall("atom:author", _NS)),
            "year": int(published[:4]) if published[:4].isdigit() else None,
            "identifiers": {
                IdentifierScheme.ARXIV: entry_id.partition(_ABS_PATH)[2],
                IdentifierScheme.DOI: _text(entry, "arxiv:doi"),
            },
            "abstract": " ".join((_text(entry, "atom:summary") or "").split()),
            "venue": "arXiv",
            "venue_type": VenueType.PREPRINT,
            "url": _link(entry, "rel", "alternate"),
            "oa_url": _link(entry, "title", "pdf"),
        }
    )


class ArxivProvider(PagedProvider):
    name: str = "arxiv"
    page_size: ClassVar[int] = 100

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http, arxiv_policy())

    def translate(self, request: SearchRequest) -> str:
        query = to_arxiv(request.query)
        if not query or (request.year_from is None and request.year_to is None):
            return query
        start = request.year_from or _EARLIEST_YEAR
        end = request.year_to or _LATEST_YEAR
        return f"({query}) AND submittedDate:[{start}01010000 TO {end}12312359]"

    async def fetch_page(
        self,
        request: SearchRequest,
        translated: str,
        cursor: str | int | None,
        size: int,
        on_wait: OnWait | None,
    ) -> Page:
        start = int(cursor or 0)
        params: dict[str, Any] = {
            "search_query": translated,
            "start": start,
            "max_results": size,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        response = await self._http.get(self._policy, _URL, params=params, on_wait=on_wait)
        try:
            feed = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise self.bad_response("not_xml") from exc
        entries = feed.findall("atom:entry", _NS)
        # Errors come as a single entry whose id points at the error's description.
        if entries and _ERROR_PATH in (_text(entries[0], "atom:id") or ""):
            raise TezError(ErrorCode.SOURCE_REJECTED, {"source": self.name}, status=502)
        total_text = _text(feed, "opensearch:totalResults")
        total = int(total_text) if total_text and total_text.isdigit() else None
        following = start + len(entries)
        return Page(
            items=entries,
            raw=response.text,
            total=total,
            next_cursor=following if total is not None and following < total else None,
        )

    def map_item(self, item: Any) -> NormalizedRecord:
        return map_entry(item)
