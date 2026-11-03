from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tez.modules.jobs.models import ACTIVE_STATUSES, ProcessingJob


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
