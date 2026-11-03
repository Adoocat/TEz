import json
from datetime import datetime

from pydantic import BaseModel

from tez.core.errors import ErrorDetail
from tez.modules.jobs.models import JobStatus, ProcessingJob


class JobView(BaseModel):
    id: str
    type: str
    status: JobStatus
    progress: float | None
    attempts: int
    max_attempts: int
    error: ErrorDetail | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, job: ProcessingJob) -> "JobView":
        return cls(
            id=job.id,
            type=job.type,
            status=job.status,
            progress=job.progress,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            error=None if job.error is None else ErrorDetail.model_validate(json.loads(job.error)),
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class WorkerStatus(BaseModel):
    alive: bool
    pid: int | None
    restarts: int
