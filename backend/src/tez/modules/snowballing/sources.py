"""Where citations come from: OpenAlex and Semantic Scholar, behind one `Protocol`.

Backward snowballing follows a seed paper's references, forward snowballing the papers that
cite it (Wohlin 2014). Both sources answer page by page like a search, so they reuse the
search providers' paging loop and record mapping. A failure is returned with what came, never
raised, so a round can record it and go on with the next seed.

Checked against the API documents on 2026-11-14:

- OpenAlex: the `cited_by:W...` filter lists the works W cites (its references), `cites:W...`
  the works citing W. A seed known only by DOI is looked up once at `/works/doi:...`.
- Semantic Scholar: `/paper/{id}/references` and `/paper/{id}/citations`, paged by `offset`
  (at most 1000 a page); `{id}` may be its own id, `DOI:...` or `ARXIV:...`.
"""

from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar, Protocol

from tez.core.errors import ErrorCode, TezError
from tez.modules.library.models import IdentifierScheme
from tez.modules.search.providers import openalex, semantic_scholar
from tez.modules.search.providers.base import (
    DEFAULT_LIMIT,
    OnWait,
    Page,
    PagedProvider,
    ProviderResult,
    SearchRequest,
    as_dict,
    as_list,
)
from tez.modules.search.providers.openalex import OpenAlexProvider, map_work, openalex_policy
from tez.modules.search.providers.registry import SourceAccess, secret_headers
from tez.modules.search.providers.semantic_scholar import (
    SemanticScholarProvider,
    map_paper,
    semantic_scholar_policy,
)
from tez.modules.search.schemas import NormalizedRecord
from tez.shared.http import HttpClient

_NOT_FOUND = 404


class Direction(StrEnum):
    BACKWARD = "backward"  # the seed's references
    FORWARD = "forward"  # the papers citing the seed


@dataclass(frozen=True)
class Seed:
    paper_id: str
    identifiers: Mapping[IdentifierScheme, str]


class CitationSource(Protocol):
    name: str

    async def citations(
        self,
        seed: Seed,
        direction: Direction,
        *,
        limit: int = DEFAULT_LIMIT,
        on_wait: OnWait | None = None,
    ) -> ProviderResult: ...


def _seed_error(code: ErrorCode, source: str, translated: str = "") -> ProviderResult:
    return ProviderResult(source, translated, error=TezError(code, {"source": source}))


def _not_found(error: TezError) -> bool:
    return error.code is ErrorCode.SOURCE_REJECTED and error.params.get("status") == _NOT_FOUND


class OpenAlexCitations(PagedProvider):
    """`translate` gets the whole filter (`cites:W...`) as the request's query."""

    name: str = OpenAlexProvider.name
    # The most OpenAlex sends at once: without a key there is only the first page.
    page_size: ClassVar[int] = 200

    def __init__(self, http: HttpClient, *, has_key: bool = False) -> None:
        super().__init__(http, openalex_policy(has_key=has_key))
        self._has_key = has_key

    async def citations(
        self,
        seed: Seed,
        direction: Direction,
        *,
        limit: int = DEFAULT_LIMIT,
        on_wait: OnWait | None = None,
    ) -> ProviderResult:
        work_id = seed.identifiers.get(IdentifierScheme.OPENALEX)
        doi = seed.identifiers.get(IdentifierScheme.DOI)
        if work_id is None and doi is not None:
            try:
                work_id = await self._work_id(doi, on_wait)
            except TezError as error:
                if _not_found(error):
                    return _seed_error(ErrorCode.SNOWBALL_SEED_NOT_FOUND, self.name, f"doi:{doi}")
                return ProviderResult(self.name, f"doi:{doi}", error=error)
        if work_id is None:
            return _seed_error(ErrorCode.SNOWBALL_SEED_UNIDENTIFIED, self.name)
        kind = "cited_by" if direction is Direction.BACKWARD else "cites"
        return await self.search(SearchRequest(f"{kind}:{work_id}", limit=limit), on_wait=on_wait)

    async def _work_id(self, doi: str, on_wait: OnWait | None) -> str | None:
        url = f"https://{openalex.API_HOST}/works/doi:{doi}"
        response = await self._http.get(
            self._policy, url, params={"select": "id"}, on_wait=on_wait, cache_ttl=86400
        )
        found = self.json_object(response).get("id")
        return found.rsplit("/", 1)[-1] if isinstance(found, str) and found else None

    def translate(self, request: SearchRequest) -> str:
        return request.query

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
            "filter": translated,
            "per_page": size,
            "cursor": cursor or "*",
            "select": openalex.WORK_FIELDS,
        }
        url = f"https://{openalex.API_HOST}/works"
        response = await self._http.get(self._policy, url, params=params, on_wait=on_wait)
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


def _s2_key(identifiers: Mapping[IdentifierScheme, str]) -> str | None:
    if found := identifiers.get(IdentifierScheme.S2):
        return found
    if found := identifiers.get(IdentifierScheme.DOI):
        return f"DOI:{found}"
    if found := identifiers.get(IdentifierScheme.ARXIV):
        return f"ARXIV:{found}"
    return None


class SemanticScholarCitations(PagedProvider):
    """`translate` gets the path below `/paper/` (`DOI:.../citations`) as the request's query."""

    name: str = SemanticScholarProvider.name
    page_size: ClassVar[int] = 1000

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http, semantic_scholar_policy())

    async def citations(
        self,
        seed: Seed,
        direction: Direction,
        *,
        limit: int = DEFAULT_LIMIT,
        on_wait: OnWait | None = None,
    ) -> ProviderResult:
        key = _s2_key(seed.identifiers)
        if key is None:
            return _seed_error(ErrorCode.SNOWBALL_SEED_UNIDENTIFIED, self.name)
        kind = "references" if direction is Direction.BACKWARD else "citations"
        return await self.search(SearchRequest(f"{key}/{kind}", limit=limit), on_wait=on_wait)

    def translate(self, request: SearchRequest) -> str:
        return request.query

    async def fetch_page(
        self,
        request: SearchRequest,
        translated: str,
        cursor: str | int | None,
        size: int,
        on_wait: OnWait | None,
    ) -> Page:
        params: dict[str, Any] = {
            "fields": semantic_scholar.PAPER_FIELDS,
            "offset": cursor or 0,
            "limit": size,
        }
        url = f"https://{semantic_scholar.API_HOST}/graph/v1/paper/{translated}"
        try:
            response = await self._http.get(self._policy, url, params=params, on_wait=on_wait)
        except TezError as error:
            if _not_found(error):
                raise TezError(ErrorCode.SNOWBALL_SEED_NOT_FOUND, {"source": self.name}) from error
            raise
        body = self.json_object(response)
        if "data" not in body:
            raise self.bad_response("no_results")
        return Page(items=as_list(body["data"]), raw=response.text, next_cursor=body.get("next"))

    def map_item(self, item: Any) -> NormalizedRecord:
        # Each item holds one paper: `citedPaper` for references, `citingPaper` for citations.
        entry = as_dict(item)
        return map_paper(as_dict(entry.get("citedPaper") or entry.get("citingPaper")))


CITATION_SOURCES = (OpenAlexCitations.name, SemanticScholarCitations.name)


def _build(name: str, http: HttpClient, access: SourceAccess) -> CitationSource:
    if name == OpenAlexCitations.name:
        return OpenAlexCitations(http, has_key=bool(access.openalex_key))
    if name == SemanticScholarCitations.name:
        return SemanticScholarCitations(http)
    raise ValueError(f"unknown citation source: {name}")


@asynccontextmanager
async def open_citation_sources(
    names: Sequence[str], access: SourceAccess
) -> AsyncGenerator[dict[str, CitationSource]]:
    """The named sources on one HTTP client, by name."""
    async with HttpClient(secret_headers=secret_headers(access)) as http:
        yield {name: _build(name, http, access) for name in names}
