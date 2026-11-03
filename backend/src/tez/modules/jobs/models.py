from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Float, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, TimestampMixin, UtcDateTime, enum_type


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_STATUSES = (JobStatus.QUEUED, JobStatus.RUNNING)


class ProcessingJob(TimestampMixin, Base):
    __tablename__ = "processing_job"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="attempts"),
        CheckConstraint("max_attempts >= 1", name="max_attempts"),
        CheckConstraint("progress BETWEEN 0 AND 1", name="progress"),
        # The same work is never queued twice at once, but may run again once finished
        # (e.g. "reprocess this PDF"). Deviation from plan's plain UNIQUE; ADR 0004.
        Index(
            "uq_processing_job_dedupe_key_active",
            "dedupe_key",
            unique=True,
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
        Index("ix_processing_job_pick", "status", "priority", "created_at"),
    )

    type: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    dedupe_key: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[JobStatus] = mapped_column(
        enum_type(JobStatus, "status"), default=JobStatus.QUEUED
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    lease_until: Mapped[datetime | None] = mapped_column(UtcDateTime)
    progress: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
