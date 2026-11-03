"""The job queue: `processing_job` rows leased to a worker for a limited time.

A worker claims a job (status `running`, `attempts + 1`, `lease_until = now + lease`) and
keeps extending the lease while it works. If it dies, the lease runs out and the next
claim takes the job again, until `max_attempts` is used up. `attempts` doubles as a
fencing token: a worker that lost its lease can no longer change the job.

For a queued job, `lease_until` means "not before": failed attempts back off this way.
"""

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from tez.modules.jobs.models import ACTIVE_STATUSES, JobStatus, ProcessingJob

MAX_BACKOFF = timedelta(minutes=5)


def error_json(code: str, params: dict[str, Any] | None = None) -> str:
    """Errors are stored as codes; the UI turns them into text (CLAUDE.md, error model)."""
    return json.dumps({"code": code, "params": params or {}}, ensure_ascii=False)


class JobsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def enqueue(
        self,
        type: str,
        payload: dict[str, Any],
        *,
        dedupe_key: str | None = None,
        priority: int = 0,
        max_attempts: int = 3,
    ) -> tuple[ProcessingJob, bool]:
        """Queue a job, or return the queued/running one with the same key (and False).

        Call inside a write session: its BEGIN IMMEDIATE keeps check-then-insert race-free.
        """
        if dedupe_key is not None:
            active = self.session.scalar(
                select(ProcessingJob).where(
                    ProcessingJob.dedupe_key == dedupe_key,
                    ProcessingJob.status.in_(ACTIVE_STATUSES),
                )
            )
            if active is not None:
                return active, False
        job = ProcessingJob(
            type=type,
            payload_json=payload,
            dedupe_key=dedupe_key,
            priority=priority,
            max_attempts=max_attempts,
        )
        self.session.add(job)
        self.session.flush()
        return job, True

    def get(self, job_id: str) -> ProcessingJob | None:
        return self.session.get(ProcessingJob, job_id)

    # --- worker side ------------------------------------------------------------------

    def claim(self, *, now: datetime, lease: timedelta) -> ProcessingJob | None:
        """Lease the next job: highest priority, then oldest. None if nothing is due.

        A running job whose lease ran out belongs to a dead worker: it is claimed again,
        or failed if it has no attempts left.
        """
        while True:
            job = self.session.scalar(
                select(ProcessingJob)
                .where(
                    or_(
                        and_(
                            ProcessingJob.status == JobStatus.QUEUED,
                            or_(
                                ProcessingJob.lease_until.is_(None),
                                ProcessingJob.lease_until <= now,
                            ),
                        ),
                        and_(
                            ProcessingJob.status == JobStatus.RUNNING,
                            ProcessingJob.lease_until <= now,
                        ),
                    )
                )
                .order_by(ProcessingJob.priority.desc(), ProcessingJob.created_at)
                .limit(1)
            )
            if job is None:
                return None
            if job.attempts >= job.max_attempts:
                job.status = JobStatus.FAILED
                job.lease_until = None
                job.error = error_json("job.lease_expired", {"attempts": job.attempts})
                self.session.flush()
                continue
            job.status = JobStatus.RUNNING
            job.attempts += 1
            job.lease_until = now + lease
            self.session.flush()
            return job

    def heartbeat(
        self,
        job_id: str,
        *,
        attempt: int,
        progress: float | None,
        now: datetime,
        lease: timedelta,
    ) -> bool:
        """Extend the lease (and record progress). False if this worker no longer owns it."""
        values: dict[str, Any] = {"lease_until": now + lease}
        if progress is not None:
            values["progress"] = progress
        return self._update_owned(job_id, attempt, values)

    def complete(self, job_id: str, *, attempt: int) -> bool:
        return self._update_owned(
            job_id,
            attempt,
            {"status": JobStatus.DONE, "progress": 1.0, "lease_until": None, "error": None},
        )

    def fail(
        self,
        job_id: str,
        *,
        attempt: int,
        code: str,
        now: datetime,
        params: dict[str, Any] | None = None,
        retry: bool = True,
    ) -> bool:
        """Record a failed attempt: queue it again after a back-off, or give up."""
        job = self.session.get(ProcessingJob, job_id)
        if job is None:
            return False
        if retry and job.attempts < job.max_attempts:
            backoff = min(timedelta(seconds=2**job.attempts), MAX_BACKOFF)
            values: dict[str, Any] = {"status": JobStatus.QUEUED, "lease_until": now + backoff}
        else:
            values = {"status": JobStatus.FAILED, "lease_until": None}
        values["error"] = error_json(code, params)
        return self._update_owned(job_id, attempt, values)

    def _update_owned(self, job_id: str, attempt: int, values: dict[str, Any]) -> bool:
        # One conditional UPDATE: the ownership check and the change cannot be split.
        result = self.session.execute(
            update(ProcessingJob)
            .where(
                ProcessingJob.id == job_id,
                ProcessingJob.status == JobStatus.RUNNING,
                ProcessingJob.attempts == attempt,
            )
            .values(**values)
            .execution_options(synchronize_session="fetch")
        )
        return result.rowcount == 1  # type: ignore[attr-defined]

    # --- readers (API, progress stream) -------------------------------------------------

    def active(self) -> list[ProcessingJob]:
        return list(
            self.session.scalars(
                select(ProcessingJob)
                .where(ProcessingJob.status.in_(ACTIVE_STATUSES))
                .order_by(ProcessingJob.created_at)
            )
        )

    def recent(self, *, limit: int) -> list[ProcessingJob]:
        return list(
            self.session.scalars(
                select(ProcessingJob)
                .order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
                .limit(limit)
            )
        )

    def changed_since(
        self, cursor: tuple[datetime, str] | None, *, limit: int = 100
    ) -> list[ProcessingJob]:
        """Jobs updated after `cursor` (updated_at, id), oldest change first."""
        query = select(ProcessingJob).order_by(ProcessingJob.updated_at, ProcessingJob.id)
        if cursor is not None:
            updated_at, job_id = cursor
            query = query.where(
                or_(
                    ProcessingJob.updated_at > updated_at,
                    and_(ProcessingJob.updated_at == updated_at, ProcessingJob.id > job_id),
                )
            )
        return list(self.session.scalars(query.limit(limit)))

    def latest_change(self) -> tuple[datetime, str] | None:
        """Cursor of the most recent change, to stream only what happens next."""
        row = self.session.execute(
            select(ProcessingJob.updated_at, ProcessingJob.id)
            .order_by(ProcessingJob.updated_at.desc(), ProcessingJob.id.desc())
            .limit(1)
        ).first()
        return None if row is None else (row[0], row[1])
