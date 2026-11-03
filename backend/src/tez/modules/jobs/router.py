from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from tez.core.errors import ErrorCode, TezError
from tez.modules.jobs import service
from tez.modules.jobs.schemas import JobView, WorkerStatus
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

router = APIRouter(prefix="/jobs", tags=["jobs"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.get("")
def list_jobs(library: LibraryDep) -> list[JobView]:
    """The most recent jobs, newest first."""
    return service.list_jobs(library.db)


@router.get("/worker")
def worker_status(request: Request, library: LibraryDep) -> WorkerStatus:
    supervisor = request.app.state.worker
    if supervisor is None:
        return WorkerStatus(alive=False, pid=None, restarts=0)
    status: WorkerStatus = supervisor.status()
    return status


@router.get("/events", response_class=EventSourceResponse)
async def job_events(
    library: LibraryDep,
    last_event_id: Annotated[str | None, Header()] = None,
) -> AsyncIterator[ServerSentEvent]:
    """Job progress as Server-Sent Events (`event: job`, data: a JobView).

    Send the token in the Authorization header: read the stream with fetch, since the
    browser's EventSource cannot set headers. On reconnect, `Last-Event-ID` resumes.
    """
    async for view, cursor in service.job_updates(library.db, service.decode_cursor(last_event_id)):
        yield ServerSentEvent(event="job", data=view, id=service.encode_cursor(cursor))


@router.get("/{job_id}")
def get_job(job_id: str, library: LibraryDep) -> JobView:
    job = service.get_job(library.db, job_id)
    if job is None:
        raise TezError(ErrorCode.JOB_NOT_FOUND, {"job_id": job_id}, status=404)
    return job
