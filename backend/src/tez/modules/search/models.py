"""Search history (plan, data model group 2).

`search_run` and `search_result` are append-only (database triggers, ADR 0004): a run is
written once, when its source has answered.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, CreatedMixin, TimestampMixin, UtcDateTime, enum_type


class InitiatedVia(StrEnum):
    GUI = "gui"
    CLI = "cli"


class RunStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    ERROR = "error"


class MatchMethod(StrEnum):
    DOI = "doi"
    ID = "id"
    TITLE_FUZZY = "title_fuzzy"
    NEW = "new"


class SearchQuery(TimestampMixin, Base):
    __tablename__ = "search_query"

    review_id: Mapped[str] = mapped_column(ForeignKey("review.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    query_text: Mapped[str] = mapped_column(Text)
    filters_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    alert_enabled: Mapped[bool] = mapped_column(default=False)
    alert_last_run_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class SearchRun(CreatedMixin, Base):
    """One source's answer to one search, or one imported export file."""

    __tablename__ = "search_run"
    __table_args__ = (
        CheckConstraint("retrieved_count >= 0", name="retrieved_count"),
        CheckConstraint("total_reported >= 0", name="total_reported"),
    )

    review_id: Mapped[str] = mapped_column(ForeignKey("review.id", ondelete="RESTRICT"), index=True)
    # Empty for imports of exported results (Task 15).
    query_id: Mapped[str | None] = mapped_column(ForeignKey("search_query.id", ondelete="RESTRICT"))
    # Groups the runs of one search across sources. Running a query again is a new search.
    search_id: Mapped[str | None] = mapped_column(String(36), index=True)
    source: Mapped[str] = mapped_column(String(64))
    # The query as sent to this source; reporting standards ask for it per source.
    translated_query: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime] = mapped_column(UtcDateTime)
    initiated_via: Mapped[InitiatedVia] = mapped_column(enum_type(InitiatedVia, "initiated_via"))
    total_reported: Mapped[int | None] = mapped_column(Integer)
    retrieved_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[RunStatus] = mapped_column(enum_type(RunStatus, "status"))
    error: Mapped[str | None] = mapped_column(Text)
    # Raw API response, compressed, relative to the library folder.
    snapshot_path: Mapped[str | None] = mapped_column(Text)


class SearchResult(CreatedMixin, Base):
    __tablename__ = "search_result"
    __table_args__ = (
        UniqueConstraint("run_id", "rank"),
        CheckConstraint("rank >= 1", name="rank"),
        CheckConstraint("match_score BETWEEN 0 AND 1", name="match_score"),
    )

    run_id: Mapped[str] = mapped_column(ForeignKey("search_run.id", ondelete="RESTRICT"))
    rank: Mapped[int] = mapped_column(Integer)
    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="RESTRICT"), index=True)
    match_method: Mapped[MatchMethod] = mapped_column(enum_type(MatchMethod, "match_method"))
    match_score: Mapped[float | None] = mapped_column(Float)
