"""Quality assessment (plan, data model group 2; ADR 0019 keeps it tool-neutral).

A review has at most one question set. Each question carries its own scale, so a set can
mix "Yes / No / Unclear" items with a final "Good / Fair / Poor" rating. Answers are
current state, not history: unlike screening decisions they are edited in place.
"""

from typing import Any

from sqlalchemy import (
    JSON,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, TimestampMixin


class QualitySetting(TimestampMixin, Base):
    """Whether the review uses the optional quality stage. No row means off."""

    __tablename__ = "quality_setting"

    review_id: Mapped[str] = mapped_column(ForeignKey("review.id", ondelete="CASCADE"), unique=True)
    enabled: Mapped[bool] = mapped_column(default=False)


class QualityQuestion(TimestampMixin, Base):
    __tablename__ = "quality_question"

    review_id: Mapped[str] = mapped_column(ForeignKey("review.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    guidance: Mapped[str | None] = mapped_column(Text)
    # [{"value": "yes", "label": "Yes", "score": 1.0}, ...]; score may be null.
    scale_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # The bundled template the question came from (e.g. "nhlbi_cohort"), for the report.
    template: Mapped[str | None] = mapped_column(String(64))


class QualityAssessment(TimestampMixin, Base):
    """One reviewer's answer to one question for one paper."""

    __tablename__ = "quality_assessment"
    __table_args__ = (
        UniqueConstraint("review_id", "paper_id", "question_id", "reviewer"),
        # Only papers taken into the review can be assessed in it.
        ForeignKeyConstraint(
            ["review_id", "paper_id"],
            ["review_record.review_id", "review_record.paper_id"],
            ondelete="RESTRICT",
        ),
    )

    review_id: Mapped[str] = mapped_column(ForeignKey("review.id", ondelete="RESTRICT"))
    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="RESTRICT"), index=True)
    question_id: Mapped[str] = mapped_column(
        ForeignKey("quality_question.id", ondelete="RESTRICT"), index=True
    )
    # The chosen scale option's `value`; null while only a note is written.
    answer: Mapped[str | None] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)
    # Ready for a second assessor, as `screening_decision.reviewer` is.
    reviewer: Mapped[str] = mapped_column(String(64), default="owner")
