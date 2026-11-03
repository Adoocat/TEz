"""Worker loop: one claimed job at a time, progress reported, failures recorded."""

import json
import threading
import time
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path

import pytest

from tez.core.db import Database
from tez.core.migrations import migrate
from tez.modules.jobs.models import JobStatus, ProcessingJob
from tez.modules.jobs.registry import JobContext, Registry
from tez.modules.jobs.repository import JobsRepository
from tez.worker import Worker

LEASE = timedelta(seconds=30)


@pytest.fixture
def db(tmp_path: Path) -> Generator[Database]:
    database = Database(tmp_path / "library.sqlite")
    migrate(database)
    yield database
    database.close()


def enqueue(
    db: Database, type: str, payload: dict[str, object] | None = None, max_attempts: int = 3
) -> str:
    with db.write_session() as s:
        job, _ = JobsRepository(s).enqueue(type, dict(payload or {}), max_attempts=max_attempts)
        return job.id


def load(db: Database, job_id: str) -> ProcessingJob:
    with db.session() as s:
        job = JobsRepository(s).get(job_id)
        assert job is not None
        return job


def test_runs_a_job_and_marks_it_done(db: Database) -> None:
    seen: list[dict[str, object]] = []
    registry = Registry()

    @registry.handler("echo")
    def echo(payload: dict[str, object], ctx: JobContext) -> None:
        seen.append(payload)
        ctx.report(0.5)

    job_id = enqueue(db, "echo", {"x": 1})

    assert Worker(db, registry, lease=LEASE).run_once() is True
    assert Worker(db, registry, lease=LEASE).run_once() is False  # queue empty

    assert seen == [{"x": 1}]
    job = load(db, job_id)
    assert job.status is JobStatus.DONE
    assert job.progress == 1.0


def test_progress_is_written_while_the_job_runs(db: Database) -> None:
    registry = Registry()
    halfway = threading.Event()
    release = threading.Event()

    @registry.handler("slow")
    def slow(payload: dict[str, object], ctx: JobContext) -> None:
        ctx.report(0.5)
        halfway.set()
        release.wait(5)

    job_id = enqueue(db, "slow")
    worker = Worker(db, registry, lease=LEASE, progress_interval=0)
    thread = threading.Thread(target=worker.run_once)
    thread.start()
    try:
        assert halfway.wait(5)
        deadline = time.monotonic() + 5
        while load(db, job_id).progress != 0.5:
            assert time.monotonic() < deadline, "progress never reached the database"
            time.sleep(0.02)
        assert load(db, job_id).status is JobStatus.RUNNING
    finally:
        release.set()
        thread.join(5)
    assert load(db, job_id).status is JobStatus.DONE


def test_handler_exception_is_recorded_and_retried(db: Database) -> None:
    registry = Registry()

    @registry.handler("broken")
    def broken(payload: dict[str, object], ctx: JobContext) -> None:
        raise ValueError("corrupt PDF")

    job_id = enqueue(db, "broken", max_attempts=2)

    Worker(db, registry, lease=LEASE).run_once()

    job = load(db, job_id)
    assert job.status is JobStatus.QUEUED  # will be retried after the back-off
    assert json.loads(job.error or "") == {
        "code": "job.handler_failed",
        "params": {"exception": "ValueError"},
    }


def test_unknown_job_type_fails_without_retries(db: Database) -> None:
    job_id = enqueue(db, "does.not.exist")

    Worker(db, Registry(), lease=LEASE).run_once()

    job = load(db, job_id)
    assert job.status is JobStatus.FAILED
    assert json.loads(job.error or "")["code"] == "job.unknown_type"


def test_a_long_job_keeps_its_lease_alive(db: Database) -> None:
    registry = Registry()

    @registry.handler("long")
    def long(payload: dict[str, object], ctx: JobContext) -> None:
        time.sleep(0.6)  # three lease lengths, no progress reports

    job_id = enqueue(db, "long")
    worker = Worker(db, registry, lease=timedelta(seconds=0.2))

    worker.run_once()

    job = load(db, job_id)
    assert job.status is JobStatus.DONE
    assert job.attempts == 1  # nobody re-claimed it while it ran


def test_built_in_diagnostics_job_reports_steps(db: Database) -> None:
    from tez.modules.jobs.handlers import registry

    job_id = enqueue(db, "diagnostics.sleep", {"steps": 4, "seconds": 0.01})

    Worker(db, registry, lease=LEASE).run_once()

    assert load(db, job_id).status is JobStatus.DONE
