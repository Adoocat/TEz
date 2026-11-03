from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import anyio
import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.core.db import Database, utcnow
from tez.main import create_app
from tez.modules.jobs.repository import JobsRepository
from tez.modules.jobs.service import (
    Cursor,
    decode_cursor,
    encode_cursor,
    job_updates,
)
from tez.modules.library.service import Library, open_library

LEASE = timedelta(seconds=30)


@pytest.fixture
def library(tmp_path: Path) -> Generator[Library]:
    lib = open_library(tmp_path / "TEz Library", create=True)
    yield lib
    lib.close()


@pytest.fixture
def client(library: Library) -> Generator[TestClient]:
    app = create_app(token=TOKEN, settings=Settings(), library=library)
    with TestClient(app) as c:
        yield c


def enqueue(db: Database, type: str = "diagnostics.sleep") -> str:
    with db.write_session() as s:
        return JobsRepository(s).enqueue(type, {})[0].id


def test_list_and_get_jobs(client: TestClient, library: Library) -> None:
    first = enqueue(library.db, "a")
    second = enqueue(library.db, "b")

    listed = client.get("/jobs", headers=AUTH).json()
    one = client.get(f"/jobs/{first}", headers=AUTH).json()

    assert [j["id"] for j in listed] == [second, first]
    assert one["status"] == "queued"
    assert one["error"] is None
    assert one["attempts"] == 0


def test_job_error_is_a_code_not_text(client: TestClient, library: Library) -> None:
    job_id = enqueue(library.db)
    with library.db.write_session() as s:
        jobs = JobsRepository(s)
        jobs.claim(now=utcnow(), lease=LEASE)
        jobs.fail(
            job_id,
            attempt=1,
            code="job.handler_failed",
            params={"exception": "X"},
            now=utcnow(),
            retry=False,
        )

    body = client.get(f"/jobs/{job_id}", headers=AUTH).json()

    assert body["status"] == "failed"
    assert body["error"] == {"code": "job.handler_failed", "params": {"exception": "X"}}


def test_unknown_job_is_404(client: TestClient) -> None:
    response = client.get("/jobs/nope", headers=AUTH)

    assert response.status_code == 404
    assert response.json()["error"] == {"code": "job.not_found", "params": {"job_id": "nope"}}


def test_worker_status_without_a_worker(client: TestClient) -> None:
    body = client.get("/jobs/worker", headers=AUTH).json()

    assert body == {"alive": False, "pid": None, "restarts": 0}


def test_jobs_need_an_open_library() -> None:
    client = TestClient(create_app(token=TOKEN, settings=Settings()))

    response = client.get("/jobs", headers=AUTH)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "library.not_open"


def test_events_need_the_token(client: TestClient) -> None:
    assert client.get("/jobs/events").status_code == 401


# --- the progress stream ----------------------------------------------------------------


def test_cursor_round_trip() -> None:
    cursor: Cursor = (utcnow(), "0195f3a0-0000-7000-8000-000000000000")

    assert decode_cursor(encode_cursor(cursor)) == cursor
    assert decode_cursor(None) is None
    assert decode_cursor("garbage") is None
    assert decode_cursor("not-a-date|id") is None


async def take(db: Database, after: Cursor | None, count: int) -> list[tuple[str, str, Cursor]]:
    """The first `count` updates as (job id, status, cursor)."""
    got: list[tuple[str, str, Cursor]] = []
    with anyio.fail_after(5):
        async for view, cursor in job_updates(db, after, poll_interval=0.01):
            got.append((view.id, view.status.value, cursor))
            if len(got) == count:
                break
    return got


@pytest.mark.anyio
async def test_stream_starts_with_active_jobs_then_follows_changes(library: Library) -> None:
    db = library.db
    waiting = enqueue(db)

    stream = job_updates(db, None, poll_interval=0.01)
    view, _ = await anext(stream)
    assert (view.id, view.status.value) == (waiting, "queued")

    with db.write_session() as s:
        JobsRepository(s).claim(now=utcnow(), lease=LEASE)
    view, _ = await anext(stream)
    assert (view.id, view.status.value) == (waiting, "running")
    await stream.aclose()


@pytest.mark.anyio
async def test_reconnect_with_last_event_id_gets_only_what_was_missed(library: Library) -> None:
    db = library.db
    first = enqueue(db)
    ((_, _, cursor),) = await take(db, None, 1)
    missed = enqueue(db)

    resumed = await take(db, cursor, 1)

    assert [r[0] for r in resumed] == [missed]
    assert first != missed


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
