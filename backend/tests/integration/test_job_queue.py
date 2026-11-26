"""Task 6b acceptance: when the worker process is killed, its job is retried once the lease
runs out; progress reaches the UI (here: the SSE stream the UI reads).
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Callable, Generator
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import pytest

from tests.integration.sidecar import run_sidecar
from tez.core.db import Database
from tez.modules.jobs.models import JobStatus
from tez.modules.jobs.repository import JobsRepository
from tez.modules.library.service import create_library

# Each test starts the backend as a process and waits for it against a deadline: run alone
# (`pnpm check`), not beside eleven other test processes.
pytestmark = pytest.mark.timing

TOKEN = "integration-token-0123456789"
LEASE_ENV = {"TEZ_JOB_LEASE_SECONDS": "1", "TEZ_WORKER_POLL_SECONDS": "0.1"}
# ~4 s of work in 40 steps: long enough to kill the worker in the middle.
SLOW_JOB = {"steps": 40, "seconds": 0.1}
TIMEOUT_S = 30


@pytest.fixture
def library(tmp_path: Path) -> Path:
    path = tmp_path / "TEz Library"
    create_library(path)
    return path


@pytest.fixture
def db(library: Path) -> Generator[Database]:
    database = Database(library / "library.sqlite")
    yield database
    database.close()


def enqueue(db: Database) -> str:
    with db.write_session() as s:
        job, _ = JobsRepository(s).enqueue("diagnostics.sleep", SLOW_JOB)
        return job.id


def job_state(db: Database, job_id: str) -> tuple[JobStatus, int, float | None]:
    with db.session() as s:
        job = JobsRepository(s).get(job_id)
        assert job is not None
        return job.status, job.attempts, job.progress


def wait_for(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + TIMEOUT_S
    while not condition():
        if time.monotonic() > deadline:
            pytest.fail(f"timed out waiting for {what}")
        time.sleep(0.05)


def hard_kill(pid: int) -> None:
    """No clean-up runs: the job stays 'running' until its lease expires."""
    os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))


def start_worker(library: Path) -> tuple[subprocess.Popen[str], int]:
    proc = subprocess.Popen(
        [sys.executable, "-m", "tez", "worker", "--library", str(library)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        env={**os.environ, **LEASE_ENV},
    )
    assert proc.stdout is not None
    line = proc.stdout.readline()
    assert line.startswith("TEZ_WORKER_READY "), line
    return proc, json.loads(line.removeprefix("TEZ_WORKER_READY "))["pid"]


def stop(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.kill()
    proc.wait()
    for pipe in (proc.stdin, proc.stdout):
        if pipe is not None:
            pipe.close()


def test_job_of_a_killed_worker_is_retried_after_the_lease(library: Path, db: Database) -> None:
    job_id = enqueue(db)
    first, first_pid = start_worker(library)
    try:
        wait_for(lambda: (job_state(db, job_id)[2] or 0) > 0, "progress from worker 1")
        hard_kill(first_pid)
        first.wait(timeout=TIMEOUT_S)
    finally:
        stop(first)
    killed_at = time.monotonic()
    status, attempts, _ = job_state(db, job_id)
    assert (status, attempts) == (JobStatus.RUNNING, 1)  # orphaned, still leased

    second, _ = start_worker(library)
    try:
        wait_for(lambda: job_state(db, job_id)[1] == 2, "worker 2 to take the job over")
        # Not before the lease (1 s) has run out.
        assert time.monotonic() - killed_at >= 0.5
        wait_for(lambda: job_state(db, job_id)[0] is JobStatus.DONE, "the retried job to finish")
    finally:
        stop(second)

    assert job_state(db, job_id) == (JobStatus.DONE, 2, 1.0)


def read_events(url: str, events: "Queue[dict[str, Any]]", stop_flag: threading.Event) -> None:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            assert response.headers["content-type"].startswith("text/event-stream")
            for raw in response:
                line = raw.decode().strip()
                if line.startswith("data: "):
                    events.put(json.loads(line.removeprefix("data: ")))
                if stop_flag.is_set():
                    return
    except OSError:
        if not stop_flag.is_set():
            raise
        # Expected: the test shut the server down while the stream was open.


def test_api_restarts_a_killed_worker_and_streams_the_progress(library: Path, db: Database) -> None:
    with run_sidecar(TOKEN, "--library", str(library), env=LEASE_ENV) as sidecar:
        assert sidecar.first_line()[0] == "TEZ_READY"

        def worker() -> dict[str, Any]:
            status, body = sidecar.get("/jobs/worker", token=TOKEN)
            assert status == 200
            result: dict[str, Any] = json.loads(body)
            return result

        wait_for(lambda: worker()["pid"] is not None, "the API to start its worker")
        first_pid = worker()["pid"]

        events: Queue[dict[str, Any]] = Queue()
        done_reading = threading.Event()
        reader = threading.Thread(
            target=read_events,
            args=(sidecar.url("/jobs/events"), events, done_reading),
            daemon=True,
        )
        reader.start()
        time.sleep(0.5)  # let the stream subscribe before the job exists
        job_id = enqueue(db)

        wait_for(lambda: (job_state(db, job_id)[2] or 0) > 0, "progress from the first worker")
        hard_kill(first_pid)
        wait_for(
            lambda: worker()["restarts"] == 1 and worker()["pid"] not in (None, first_pid),
            "the API to restart the worker",
        )
        wait_for(lambda: job_state(db, job_id)[0] is JobStatus.DONE, "the retried job to finish")

        seen: list[dict[str, Any]] = []
        while not seen or seen[-1]["status"] != "done":
            try:
                seen.append(events.get(timeout=TIMEOUT_S))
            except Empty:
                pytest.fail(f"no 'done' event; got {seen}")
        done_reading.set()

    mine = [e for e in seen if e["id"] == job_id]
    progress = [e["progress"] for e in mine if e["progress"] is not None]
    # Polling reports the latest state, so a brief state (queued) may be folded into the next.
    assert {e["attempts"] for e in mine if e["status"] == "running"} == {1, 2}
    assert len(progress) >= 5  # the UI saw it move, not just start and end
    assert mine[-1] == {**mine[-1], "status": "done", "progress": 1.0, "attempts": 2}
