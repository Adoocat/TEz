"""Searches running in this process, and the per-source progress clients follow.

Progress lives in memory: it is about the present. What each source said is in the database.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Coroutine
from dataclasses import dataclass, field
from typing import Any

from tez.modules.search.service import SourceUpdate

logger = logging.getLogger(__name__)


@dataclass
class LiveSearch:
    search_id: str
    latest: dict[str, SourceUpdate] = field(default_factory=dict[str, SourceUpdate])
    finished: bool = False
    _subscribers: set[asyncio.Queue[SourceUpdate | None]] = field(
        default_factory=set[asyncio.Queue[SourceUpdate | None]]
    )

    def publish(self, update: SourceUpdate) -> None:
        self.latest[update.source] = update
        for queue in self._subscribers:
            queue.put_nowait(update)

    def finish(self) -> None:
        self.finished = True
        for queue in self._subscribers:
            queue.put_nowait(None)

    async def follow(self) -> AsyncIterator[SourceUpdate]:
        """Where each source stands now, then every change until the search ends."""
        queue: asyncio.Queue[SourceUpdate | None] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            for update in list(self.latest.values()):
                yield update
            if self.finished:
                return
            while (update := await queue.get()) is not None:
                yield update
        finally:
            self._subscribers.discard(queue)


class SearchRegistry:
    def __init__(self) -> None:
        self._searches: dict[str, LiveSearch] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def get(self, search_id: str) -> LiveSearch | None:
        return self._searches.get(search_id)

    def start(self, live: LiveSearch, work: Coroutine[Any, Any, None]) -> None:
        """Run `work` in the background; `live` reports it. Keeps a reference so it is not lost."""
        self._searches[live.search_id] = live

        async def run() -> None:
            try:
                await work
            except Exception:
                # run_search records each source's failure itself; this is everything else.
                logger.exception("search failed", extra={"search_id": live.search_id})
            finally:
                live.finish()

        task = asyncio.create_task(run())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
