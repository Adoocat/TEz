from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from tez.modules.reviews.models import CriterionKind, ReviewMethod, ReviewStatus, ScreeningStage

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
    # Set while the review is in the trash.
    deleted_at: datetime | None = None


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


# "E1", "I2", "E-LANG": stored upper case.
CriterionCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9._-]{1,16}$")
]
CriterionText = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
Keyword = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
# Terms screening highlights for a criterion; matched Turkish-safe, case- and accent-blind.
Keywords = Annotated[list[Keyword], Field(max_length=50)]


class CriterionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: CriterionKind
    # Left out: the next free "I<n>" or "E<n>".
    code: CriterionCode | None = None
    text: CriterionText
    # None: both stages.
    stage: ScreeningStage | None = None
    keywords: Keywords = []


class CriterionUpdate(BaseModel):
    """Only the fields sent change; `stage: null` means both stages."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: CriterionKind | None = None
    code: CriterionCode | None = None
    text: CriterionText | None = None
    stage: ScreeningStage | None = None
    archived: bool | None = None
    keywords: Keywords | None = None


class CriteriaOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Every active (not archived) criterion of the review, once, in the new order.
    criterion_ids: list[str]


class CriterionShortcuts(BaseModel):
    """The 1-9 key a criterion has in each stage's screening; None past the ninth."""

    title_abstract: int | None
    full_text: int | None


class CriterionView(BaseModel):
    id: str
    kind: CriterionKind
    code: str
    text: str
    stage: ScreeningStage | None
    position: int
    archived: bool
    # A screening decision cites it: it can be archived, not deleted.
    used: bool
    shortcuts: CriterionShortcuts
    keywords: list[str]


class StageCriterion(BaseModel):
    """A criterion as one stage's screening shows it, with its key (for Task 31's service)."""

    id: str
    kind: CriterionKind
    code: str
    text: str
    shortcut: int | None
    keywords: list[str]
