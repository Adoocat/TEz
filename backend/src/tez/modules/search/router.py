from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from starlette.concurrency import run_in_threadpool

from tez.core.errors import ErrorCode, TezError
from tez.modules.library.router import get_library
from tez.modules.library.service import Library
from tez.modules.reviews import service as reviews_service
from tez.modules.search import queries
from tez.modules.search.live import LiveSearch, SearchRegistry
from tez.modules.search.providers.base import SearchRequest
from tez.modules.search.providers.registry import (
    SOURCE_NAMES,
    ProviderFactory,
    read_access,
)
from tez.modules.search.schemas import (
    SearchOverview,
    SearchResultRow,
    SearchStart,
    SearchStarted,
    SourceProgress,
)
from tez.modules.search.service import SourceUpdate, run_search
from tez.modules.settings import service as settings_service
from tez.shared.ids import new_id

router = APIRouter(prefix="/searches", tags=["search"])

LibraryDep = Annotated[Library, Depends(get_library)]


def get_registry(request: Request) -> SearchRegistry:
    registry: SearchRegistry = request.app.state.search_registry
    return registry


RegistryDep = Annotated[SearchRegistry, Depends(get_registry)]


@router.post("", status_code=202)
async def start_search(
    body: SearchStart, request: Request, library: LibraryDep, registry: RegistryDep
) -> SearchStarted:
    """Start asking the sources; follow it at `/searches/{id}/events`."""
    unknown = [s for s in body.sources if s not in SOURCE_NAMES]
    if unknown:
        raise TezError(ErrorCode.SOURCE_UNKNOWN, {"sources": unknown}, status=422)
    if not await run_in_threadpool(reviews_service.review_exists, library.db, body.review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": body.review_id}, status=404)

    settings = await run_in_threadpool(settings_service.read_settings, library.db)
    access = await run_in_threadpool(
        read_access, request.app.state.secret_store, settings.sources_email
    )
    factory: ProviderFactory = request.app.state.provider_factory
    search_id = new_id()
    live = LiveSearch(search_id)
    search_request = SearchRequest(
        query=body.query, year_from=body.year_from, year_to=body.year_to, limit=body.limit
    )

    async def work() -> None:
        async with factory(body.sources, access) as providers:
            await run_search(
                library.db,
                library.path,
                body.review_id,
                search_request,
                providers,
                search_id=search_id,
                initiated_via=body.initiated_via,
                listener=live.publish,
            )

    registry.start(live, work())
    return SearchStarted(search_id=search_id, sources=body.sources)


def _progress(update: SourceUpdate) -> SourceProgress:
    return SourceProgress(
        source=update.source,
        state=update.state,
        retrieved=update.retrieved,
        total_reported=update.total_reported,
        wait_seconds=update.wait_seconds,
        error_code=update.error_code,
    )


def get_live_search(search_id: str, registry: RegistryDep) -> LiveSearch:
    """A dependency, because an error raised inside a stream can no longer become a 404."""
    live = registry.get(search_id)
    if live is None:
        raise TezError(ErrorCode.SEARCH_NOT_FOUND, {"search_id": search_id}, status=404)
    return live


@router.get("")
def list_searches(review_id: str, library: LibraryDep) -> list[SearchOverview]:
    """The review's search history, newest first."""
    return queries.history(library.db, review_id)


# `responses` puts SourceProgress in the OpenAPI schema, so the client knows the event's shape.
@router.get(
    "/{search_id}/events",
    response_class=EventSourceResponse,
    responses={200: {"model": SourceProgress}},
)
async def search_events(
    search_id: str, live: Annotated[LiveSearch, Depends(get_live_search)]
) -> AsyncIterator[ServerSentEvent]:
    """Per-source progress as Server-Sent Events (`event: source`), then `event: finished`.

    Only searches running in this process have events. Afterwards, read `/searches/{id}`.
    """
    async for update in live.follow():
        yield ServerSentEvent(event="source", data=_progress(update))
    yield ServerSentEvent(event="finished", data={"search_id": search_id})


@router.get("/{search_id}")
def get_search(search_id: str, library: LibraryDep) -> SearchOverview:
    """What each source answered, and the counts derived from it."""
    overview = queries.overview(library.db, search_id)
    if overview is None:
        raise TezError(ErrorCode.SEARCH_NOT_FOUND, {"search_id": search_id}, status=404)
    return overview


@router.get("/{search_id}/results")
def get_results(search_id: str, library: LibraryDep) -> list[SearchResultRow]:
    """The deduplicated papers of a search, with the sources that found each."""
    return queries.result_rows(library.db, search_id)
