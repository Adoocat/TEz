"""The paging loop every source shares, with a scripted source."""

import asyncio
from collections.abc import Sequence
from typing import Any, ClassVar

from tests.unit.providers.conftest import no_sleep
from tez.core.errors import ErrorCode, TezError
from tez.modules.search.models import RunStatus
from tez.modules.search.providers.base import (
    OnWait,
    Page,
    PagedProvider,
    ProviderResult,
    SearchRequest,
)
from tez.modules.search.schemas import NormalizedRecord
from tez.shared.http import HttpClient, SourcePolicy


class Scripted(PagedProvider):
    name = "scripted"
    page_size: ClassVar[int] = 2

    def __init__(self, script: Sequence[Page | TezError]) -> None:
        super().__init__(HttpClient(sleep=no_sleep), SourcePolicy("scripted", 1))
        self.script = list(script)
        self.calls: list[tuple[str | int | None, int]] = []

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
        self.calls.append((cursor, size))
        step = self.script[len(self.calls) - 1]
        if isinstance(step, TezError):
            raise step
        return step

    def map_item(self, item: Any) -> NormalizedRecord:
        return NormalizedRecord(title=item["title"])


def page(*titles: str, cursor: str | None = None, total: int | None = None) -> Page:
    return Page(
        items=[{"title": t} for t in titles], raw=f"raw:{titles}", total=total, next_cursor=cursor
    )


def search(provider: Scripted, limit: int = 10) -> ProviderResult:
    return asyncio.run(provider.search(SearchRequest("q", limit=limit)))


def titles(result: ProviderResult) -> list[str]:
    return [r.title for r in result.records]


FAILURE = TezError(ErrorCode.SOURCE_TIMEOUT, {"source": "scripted"})


def test_pages_are_followed_until_the_source_ends() -> None:
    provider = Scripted([page("a", "b", cursor="c1", total=3), page("c")])

    result = search(provider)

    assert titles(result) == ["a", "b", "c"]
    assert provider.calls == [(None, 2), ("c1", 2)]
    assert result.status is RunStatus.OK
    assert result.total_reported == 3
    assert result.raw_pages == ("raw:('a', 'b')", "raw:('c',)")


def test_the_limit_stops_paging_and_shrinks_the_last_request() -> None:
    provider = Scripted([page("a", "b", cursor="c1"), page("c", cursor="c2")])

    result = search(provider, limit=3)

    assert titles(result) == ["a", "b", "c"]
    assert provider.calls == [(None, 2), ("c1", 1)]


def test_a_source_that_ignores_the_page_size_is_cut_at_the_limit() -> None:
    provider = Scripted([page("a", "b", "c", "d", cursor="c1")])

    assert titles(search(provider, limit=3)) == ["a", "b", "c"]


def test_failure_on_the_first_page_is_an_error_result_not_an_exception() -> None:
    result = search(Scripted([FAILURE]))

    assert result.status is RunStatus.ERROR
    assert result.error is FAILURE
    assert result.records == ()


def test_failure_on_a_later_page_keeps_what_arrived() -> None:
    result = search(Scripted([page("a", "b", cursor="c1", total=9), FAILURE]))

    assert result.status is RunStatus.PARTIAL
    assert titles(result) == ["a", "b"]
    assert result.total_reported == 9
    assert result.error is FAILURE


def test_a_cursor_that_does_not_advance_ends_the_search() -> None:
    provider = Scripted([page("a", "b", cursor="same"), page("c", "d", cursor="same")])

    assert titles(search(provider)) == ["a", "b", "c", "d"]
    assert len(provider.calls) == 2


def test_an_empty_page_ends_the_search() -> None:
    provider = Scripted([page(cursor="c1")])

    assert search(provider).status is RunStatus.OK
    assert len(provider.calls) == 1


def test_unmappable_items_are_counted_and_the_rest_kept() -> None:
    odd = Page(items=[{"title": "ok"}, {"nope": 1}, {"title": "  "}], raw="", next_cursor=None)

    result = search(Scripted([odd]))

    assert titles(result) == ["ok"]
    assert result.skipped == 2
    assert result.status is RunStatus.OK


def test_a_query_with_nothing_to_send_makes_no_request() -> None:
    provider = Scripted([])

    result = asyncio.run(provider.search(SearchRequest("")))

    assert result.status is RunStatus.ERROR
    assert result.error is not None
    assert result.error.code is ErrorCode.SOURCE_QUERY_UNSUPPORTED
    assert provider.calls == []
