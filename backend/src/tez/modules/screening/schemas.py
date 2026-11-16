from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from tez.modules.files.schemas import AttachmentView
from tez.modules.library.models import RetractionStatus
from tez.modules.reviews.models import Decision, ScreeningStage


class RecordState(StrEnum):
    """Where a record stands at one stage; derived from its current decision."""

    UNDECIDED = "undecided"
    INCLUDE = "include"
    EXCLUDE = "exclude"
    MAYBE = "maybe"
    NOT_RETRIEVED = "not_retrieved"


class QueueFilter(StrEnum):
    ALL = "all"
    UNDECIDED = "undecided"
    INCLUDE = "include"
    EXCLUDE = "exclude"
    MAYBE = "maybe"
    NOT_RETRIEVED = "not_retrieved"


class ChosenDecision(StrEnum):
    """What a person can choose; `undecided` is only ever written by undo."""

    INCLUDE = "include"
    EXCLUDE = "exclude"
    MAYBE = "maybe"
    NOT_RETRIEVED = "not_retrieved"


class DecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    paper_id: str
    decision: ChosenDecision
    criterion_id: str | None = None
    note: str | None = Field(default=None, max_length=10_000)


class UndoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The decision to take back; the state before it is restored as a new row.
    decision_id: str


class DecisionView(BaseModel):
    id: str
    paper_id: str
    stage: ScreeningStage
    decision: Decision
    criterion_id: str | None
    note: str | None
    reviewer: str
    supersedes_id: str | None
    created_at: datetime


class StateCounts(BaseModel):
    total: int
    undecided: int
    include: int
    exclude: int
    maybe: int
    not_retrieved: int


class QueueItem(BaseModel):
    """One row of the queue, as the list mode shows it."""

    paper_id: str
    position: int  # 1-based, in the stage's stable order
    state: RecordState
    decision_id: str | None
    criterion_id: str | None
    title: str
    year: int | None
    venue: str | None
    first_author: str | None
    author_count: int


class ScreeningQueue(BaseModel):
    stage: ScreeningStage
    counts: StateCounts
    items: list[QueueItem]


class ScreeningRecord(BaseModel):
    """One record as the focus mode shows it, with where it sits in the queue."""

    paper_id: str
    position: int
    total: int
    state: RecordState
    decision: DecisionView | None
    title: str
    abstract: str | None
    authors: list[str]
    year: int | None
    venue: str | None
    doi: str | None
    retraction_status: RetractionStatus
    # The record's files; full-text screening opens its PDF beside the criteria (Task 33).
    attachments: list[AttachmentView]
