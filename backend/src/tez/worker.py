"""The job worker: a separate process that runs queued jobs (`tez-backend worker`).

It is separate so that a crash in native code (a broken PDF in a C library) takes down
only the worker; the API keeps serving and restarts it (plan, "Mimari"). Jobs are
claimed with a lease that a heartbeat thread keeps extending; if this process dies, the
lease runs out and another worker retries the job.
"""

import json
import logging
import os
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from tez.core.db import Database, utcnow
from tez.modules.jobs.registry import JobContext, JobFailed, Registry
from tez.modules.jobs.repository import JobsRepository

logger = logging.getLogger("tez.worker")

DATABASE_FILE = "library.sqlite"


class Worker:
    def __init__(
        self,
        db: Database,
        registry: Registry,
        *,
        lease: timedelta,
        poll_interval: float = 0.5,
        progress_interval: float = 0.25,
    ) -> None:
        self.db = db
        self.registry = registry
        self.lease = lease
        self.poll_interval = poll_interval
        self.progress_interval = progress_interval

    def run_forever(self, stop: threading.Event) -> None:
        while not stop.is_set():
            if not self.run_once():
                stop.wait(self.poll_interval)

    def run_once(self) -> bool:
        """Run the next due job to its end. False if there was nothing to do."""
        with self.db.write_session() as s:
            job = JobsRepository(s).claim(now=utcnow(), lease=self.lease)
            if job is None:
                return False
            job_id, attempt, job_type = job.id, job.attempts, job.type
            max_attempts = job.max_attempts
            payload = dict(job.payload_json)
        log = {"job_id": job_id, "job_type": job_type, "attempt": attempt}

        handler = self.registry.get(job_type)
        if handler is None:
            logger.error("unknown job type", extra=log)
            self._finish_failed(job_id, attempt, "job.unknown_type", {"type": job_type}, False)
            return True

        ctx = JobContext(job_id, db=self.db, attempt=attempt, max_attempts=max_attempts)
        stop_heartbeat = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat,
            args=(job_id, attempt, ctx, stop_heartbeat),
            name=f"heartbeat-{job_id}",
            daemon=True,
        )
        logger.info("job started", extra=log)
        heartbeat.start()
        failure: JobFailed | None = None
        try:
            handler(payload, ctx)
        except JobFailed as error:
            # An expected failure with its own code; the handler says whether to retry.
            logger.info("job failed", extra={**log, "code": error.code})
            failure = error
        except Exception as error:
            logger.exception("job failed", extra=log)
            failure = JobFailed(
                "job.handler_failed", {"exception": type(error).__name__}, retry=True
            )
        finally:
            stop_heartbeat.set()
            heartbeat.join()

        if failure is not None:
            self._finish_failed(job_id, attempt, failure.code, failure.params, failure.retry)
        else:
            with self.db.write_session() as s:
                owned = JobsRepository(s).complete(job_id, attempt=attempt)
            if owned:
                logger.info("job done", extra=log)
            else:
                logger.warning("job finished after losing its lease; result dropped", extra=log)
        return True

    def _finish_failed(
        self, job_id: str, attempt: int, code: str, params: dict[str, Any], retry: bool
    ) -> None:
        with self.db.write_session() as s:
            JobsRepository(s).fail(
                job_id, attempt=attempt, code=code, params=params, now=utcnow(), retry=retry
            )

    def _heartbeat(self, job_id: str, attempt: int, ctx: JobContext, stop: threading.Event) -> None:
        """Extend the lease (and save progress) until the handler returns."""
        renew_every = self.lease.total_seconds() / 3
        tick = max(min(self.progress_interval, renew_every), 0.02)
        written_progress: float | None = None
        last_write = time.monotonic()
        while not stop.wait(tick):
            progress = ctx.progress
            if progress == written_progress and time.monotonic() - last_write < renew_every:
                continue
            with self.db.write_session() as s:
                owned = JobsRepository(s).heartbeat(
                    job_id, attempt=attempt, progress=progress, now=utcnow(), lease=self.lease
                )
            written_progress, last_write = progress, time.monotonic()
            if not owned:
                # Another worker took the job over (our lease ran out): stop working on it.
                logger.warning("lost the job lease", extra={"job_id": job_id})
                ctx.cancel()
                return


def run_worker_process(library: Path, *, lease: timedelta, poll_interval: float) -> int:
    """Entry point of `tez-backend worker`. Runs until stdin closes (the API went away).

    The API process owns the library lock; the worker is part of that same instance and
    opens the database directly. Prints `TEZ_WORKER_READY {"pid": N}` once running.
    """
    from tez.modules.jobs.handlers import registry

    db = Database(library / DATABASE_FILE)
    stop = threading.Event()

    def stop_when_stdin_closes() -> None:
        try:
            while sys.stdin.readline():
                pass
        except (OSError, ValueError):
            logger.warning("stdin watcher failed; stopping", exc_info=True)
        stop.set()

    threading.Thread(target=stop_when_stdin_closes, daemon=True, name="stdin-eof").start()
    print("TEZ_WORKER_READY " + json.dumps({"pid": os.getpid()}), flush=True)
    logger.info("worker started", extra={"library": str(library)})
    try:
        Worker(db, registry, lease=lease, poll_interval=poll_interval).run_forever(stop)
    finally:
        db.close()
    logger.info("worker stopped")
    return 0
