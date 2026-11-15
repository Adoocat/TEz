"""Review, its records and screening (plan, data model group 2).

`screening_decision` is append-only (database triggers, ADR 0004): a correction is a new
row whose `supersedes_id` points at the decision it replaces.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, ForeignKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, CreatedMixin, TimestampMixin, UtcDateTime, enum_type


class ReviewMethod(StrEnum):
    PRISMA2020 = "prisma2020"
    KITCHENHAM_SLR = "kitchenham_slr"


class ReviewStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class RecordOrigin(StrEnum):
    DATABASE = "database"
    CITATION_BACKWARD = "citation_backward"
    CITATION_FORWARD = "citation_forward"
    MANUAL = "manual"


class CriterionKind(StrEnum):
    INCLUSION = "inclusion"
    EXCLUSION = "exclusion"


class ScreeningStage(StrEnum):
    TITLE_ABSTRACT = "title_abstract"
    FULL_TEXT = "full_text"


class Decision(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    MAYBE = "maybe"


class Review(TimestampMixin, Base):
    __tablename__ = "review"

    title: Mapped[str] = mapped_column(Text)
    research_questions_md: Mapped[str | None] = mapped_column(Text)
    protocol_md: Mapped[str | None] = mapped_column(Text)
    method: Mapped[ReviewMethod] = mapped_column(enum_type(ReviewMethod, "method"))
    status: Mapped[ReviewStatus] = mapped_column(
        enum_type(ReviewStatus, "status"), default=ReviewStatus.ACTIVE
    )


class ReviewRecord(TimestampMixin, Base):
    """A paper taken into a review, and how it got there (PRISMA's identification)."""

    __tablename__ = "review_record"
    __table_args__ = (UniqueConstraint("review_id", "paper_id"),)

    review_id: Mapped[str] = mapped_column(ForeignKey("review.id", ondelete="CASCADE"))
    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="RESTRICT"), index=True)
    origin: Mapped[RecordOrigin] = mapped_column(enum_type(RecordOrigin, "origin"))
    # E.g. the search run or the paper whose references led here.
    origin_ref: Mapped[str | None] = mapped_column(String(36))


class ScreeningCriterion(TimestampMixin, Base):
    __tablename__ = "screening_criterion"
    __table_args__ = (UniqueConstraint("review_id", "code"),)

    review_id: Mapped[str] = mapped_column(ForeignKey("review.id", ondelete="CASCADE"))
    kind: Mapped[CriterionKind] = mapped_column(enum_type(CriterionKind, "kind"))
    code: Mapped[str] = mapped_column(String(16))  # "E1"
    text: Mapped[str] = mapped_column(Text)
    # None: both stages.
    stage: Mapped[ScreeningStage | None] = mapped_column(enum_type(ScreeningStage, "stage"))
    # Order in the review; a stage's first nine active criteria get the 1-9 keys (Task 25).
    position: Mapped[int] = mapped_column(default=0, server_default=sql_text("0"))
    # A criterion that decisions use is archived, never deleted.
    archived_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class ScreeningDecision(CreatedMixin, Base):
    __tablename__ = "screening_decision"
    __table_args__ = (
        # Only papers taken into the review can be screened in it.
        ForeignKeyConstraint(
            ["review_id", "paper_id"],
            ["review_record.review_id", "review_record.paper_id"],
            ondelete="RESTRICT",
        ),
    )

    review_id: Mapped[str] = mapped_column(ForeignKey("review.id", ondelete="RESTRICT"))
    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="RESTRICT"), index=True)
    stage: Mapped[ScreeningStage] = mapped_column(enum_type(ScreeningStage, "stage"))
    decision: Mapped[Decision] = mapped_column(enum_type(Decision, "decision"))
    criterion_id: Mapped[str | None] = mapped_column(
        ForeignKey("screening_criterion.id", ondelete="RESTRICT")
    )
    note: Mapped[str | None] = mapped_column(Text)
    # Ready for dual screening (Cohen's kappa) without a schema change.
    reviewer: Mapped[str] = mapped_column(String(64), default="owner")
    # A decision is corrected at most once, so corrections form a chain.
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("screening_decision.id", ondelete="RESTRICT"), unique=True
    )
