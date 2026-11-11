"""Reading jobs for the API, and the progress stream behind `GET /jobs/events`."""

from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

import anyio
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from tez.core.db import Database
from tez.modules.jobs.repository import JobsRepository
from tez.modules.jobs.schemas import JobView

POLL_INTERVAL_S = 0.25

Cursor = tuple[datetime, str]


def encode_cursor(cursor: Cursor) -> str:
    return f"{cursor[0].isoformat()}|{cursor[1]}"


def decode_cursor(value: str | None) -> Cursor | None:
    """The SSE `Last-Event-ID` a reconnecting client sends back; None if unusable."""
    if not value:
        return None
    stamp, sep, job_id = value.partition("|")
    try:
        return (datetime.fromisoformat(stamp), job_id) if sep else None
    except ValueError:
        return None


async def job_updates(
    db: Database, after: Cursor | None, *, poll_interval: float = POLL_INTERVAL_S
) -> AsyncGenerator[tuple[JobView, Cursor]]:
    """Every job change, as it happens, each with the cursor to resume from.

    A fresh client (no cursor) first gets the active jobs, then changes from that moment;
    a reconnecting one gets exactly what it missed. The database is polled because the
    writer is another process (the worker).
    """
    cursor = after
    if cursor is None:
        snapshot, cursor = await run_in_threadpool(_snapshot, db)
        for view in snapshot:
            yield view, cursor
    while True:
        changes = await run_in_threadpool(_changes, db, cursor)
        for view in changes:
            cursor = (view.updated_at, view.id)
            yield view, cursor
        if not changes:
            await anyio.sleep(poll_interval)


def _snapshot(db: Database) -> tuple[list[JobView], Cursor]:
    with db.session() as s:
        jobs = JobsRepository(s)
        active = [JobView.of(job) for job in jobs.active()]
        latest = jobs.latest_change()
    epoch = (datetime.fromisoformat("1970-01-01T00:00:00+00:00"), "")
    return active, latest or epoch


def _changes(db: Database, cursor: Cursor) -> list[JobView]:
    with db.session() as s:
        return [JobView.of(job) for job in JobsRepository(s).changed_since(cursor)]


def list_jobs(db: Database, *, limit: int = 100) -> list[JobView]:
    with db.session() as s:
        return [JobView.of(job) for job in JobsRepository(s).recent(limit=limit)]


def get_job(db: Database, job_id: str) -> JobView | None:
    with db.session() as s:
        job = JobsRepository(s).get(job_id)
        return None if job is None else JobView.of(job)


def enqueue(
    session: Session,
    job_type: str,
    payload: dict[str, Any],
    *,
    dedupe_key: str | None = None,
    priority: int = 0,
    max_attempts: int = 3,
) -> str:
    """Queue a job in the caller's write session; returns its id (the active one if a twin is
    already queued). For other modules, which do not use the jobs repository directly."""
    job, _ = JobsRepository(session).enqueue(
        job_type, payload, dedupe_key=dedupe_key, priority=priority, max_attempts=max_attempts
    )
    return job.id
