"""What a search source is: a `Protocol`, and the paging loop they all share.

`search` never raises for a source's failure. It returns what it has together with the error,
so the federated search (Task 13) can record that source's run and carry on with the others.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol, cast

import httpx2
from pydantic import ValidationError

from tez.core.errors import ErrorCode, TezError
from tez.modules.search.models import RunStatus
from tez.modules.search.schemas import NormalizedRecord
from tez.shared.http import HttpClient, SourcePolicy

logger = logging.getLogger(__name__)

OnWait = Callable[[float], None]
DEFAULT_LIMIT = 1000


def as_dict(value: Any) -> dict[str, Any]:
    """A nested JSON object, or an empty one if the source sent null or something else."""
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    """A nested JSON array, or an empty one if the source sent null or something else."""
    return cast(list[Any], value) if isinstance(value, list) else []


@dataclass(frozen=True)
class SearchRequest:
    query: str
    year_from: int | None = None
    year_to: int | None = None
    limit: int = DEFAULT_LIMIT


@dataclass(frozen=True)
class ProviderResult:
    """One source's whole answer. `raw_pages` go to the snapshot file as they arrived."""

    source: str
    translated_query: str
    records: tuple[NormalizedRecord, ...] = ()
    total_reported: int | None = None
    raw_pages: tuple[str, ...] = ()
    # Items the source sent that could not be mapped; logged, not lost silently.
    skipped: int = 0
    error: TezError | None = field(default=None, compare=False)

    @property
    def status(self) -> RunStatus:
        if self.error is None:
            return RunStatus.OK
        return RunStatus.PARTIAL if self.records else RunStatus.ERROR


class SearchProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def search(
        self, request: SearchRequest, *, on_wait: OnWait | None = None
    ) -> ProviderResult: ...


@dataclass(frozen=True)
class Page:
    items: Sequence[Any]
    raw: str
    total: int | None = None
    next_cursor: str | int | None = None


class PagedProvider(ABC):
    """A source that answers page by page. Subclasses translate, fetch one page and map."""

    name: ClassVar[str]
    page_size: ClassVar[int]

    def __init__(self, http: HttpClient, policy: SourcePolicy) -> None:
        self._http = http
        self._policy = policy

    @abstractmethod
    def translate(self, request: SearchRequest) -> str:
        """The query as this source will receive it; empty if it cannot be expressed."""

    @abstractmethod
    async def fetch_page(
        self,
        request: SearchRequest,
        translated: str,
        cursor: str | int | None,
        size: int,
        on_wait: OnWait | None,
    ) -> Page: ...

    @abstractmethod
    def map_item(self, item: Any) -> NormalizedRecord: ...

    async def search(
        self, request: SearchRequest, *, on_wait: OnWait | None = None
    ) -> ProviderResult:
        translated = self.translate(request)
        if not translated:
            error = TezError(ErrorCode.SOURCE_QUERY_UNSUPPORTED, {"source": self.name})
            return ProviderResult(self.name, translated, error=error)

        records: list[NormalizedRecord] = []
        raw_pages: list[str] = []
        total: int | None = None
        skipped = 0
        cursor: str | int | None = None
        error: TezError | None = None
        while len(records) < request.limit:
            size = min(self.page_size, request.limit - len(records))
            try:
                page = await self.fetch_page(request, translated, cursor, size, on_wait)
            except TezError as exc:
                logger.warning("source failed", extra={"source": self.name, "code": exc.code})
                error = exc
                break
            raw_pages.append(page.raw)
            total = page.total if page.total is not None else total
            mapped, failed = self.map_all(page.items)
            records.extend(mapped[: request.limit - len(records)])
            skipped += failed
            if not page.items or page.next_cursor is None or page.next_cursor == cursor:
                break
            cursor = page.next_cursor
        return ProviderResult(
            source=self.name,
            translated_query=translated,
            records=tuple(records),
            total_reported=total,
            raw_pages=tuple(raw_pages),
            skipped=skipped,
            error=error,
        )

    def map_all(self, items: Sequence[Any]) -> tuple[list[NormalizedRecord], int]:
        mapped: list[NormalizedRecord] = []
        failed = 0
        for item in items:
            try:
                mapped.append(self.map_item(item))
            except (ValidationError, KeyError, TypeError, ValueError, AttributeError) as exc:
                # One odd record must not lose the page (CLAUDE.md rule 5).
                logger.warning("record skipped", extra={"source": self.name, "error": repr(exc)})
                failed += 1
        return mapped, failed

    def bad_response(self, reason: str) -> TezError:
        return TezError(
            ErrorCode.SOURCE_BAD_RESPONSE, {"source": self.name, "reason": reason}, status=502
        )

    def json_object(self, response: httpx2.Response) -> dict[str, Any]:
        """The body as a JSON object. A bot-check HTML page or a broken body is a source error."""
        try:
            body: object = response.json()
        except ValueError as exc:
            raise self.bad_response("not_json") from exc
        if not isinstance(body, dict):
            raise self.bad_response("not_an_object")
        return cast(dict[str, Any], body)
