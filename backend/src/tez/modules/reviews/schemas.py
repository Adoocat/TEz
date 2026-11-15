from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from tez.modules.reviews.models import ReviewMethod, ReviewStatus, ScreeningStage

ResearchQuestion = Annotated[str, StringConstraints(max_length=1000)]


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    # PRISMA 2020 unless the user picks otherwise (ADR 0019).
    method: ReviewMethod = ReviewMethod.PRISMA2020
    # One line each; blank ones are dropped.
    research_questions: list[ResearchQuestion] = Field(default_factory=list, max_length=20)
    protocol: str | None = Field(default=None, max_length=20_000)

    @field_validator("research_questions")
    @classmethod
    def _one_line_each(cls, questions: list[str]) -> list[str]:
        lines = (" ".join(question.split()) for question in questions)
        return [line for line in lines if line]

    @field_validator("protocol")
    @classmethod
    def _blank_is_none(cls, protocol: str | None) -> str | None:
        return protocol or None


class ReviewView(BaseModel):
    id: str
    title: str
    method: ReviewMethod
    status: ReviewStatus
    research_questions: list[str]
    protocol: str | None
    created_at: datetime


class StageProgress(BaseModel):
    """Where one screening stage stands, derived from the decisions in force."""

    stage: ScreeningStage
    # Records that reach this stage: all of them for title-abstract; for full text, those
    # included or marked "maybe" at title-abstract.
    eligible: int
    decided: int
    pending: int
    included: int
    excluded: int
    maybe: int


class ReviewOverview(BaseModel):
    """The review panel's numbers (design 5.1). Derived on every read, never stored."""

    review_id: str
    records: int
    stages: list[StageProgress]
