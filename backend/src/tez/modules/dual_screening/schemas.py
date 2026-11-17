from pydantic import BaseModel, ConfigDict, Field

from tez.modules.dual_screening.matching import MatchProblem
from tez.modules.reviews.models import Decision, ScreeningStage
from tez.modules.screening.schemas import ChosenDecision


class DecisionImport(BaseModel):
    # The decision file's text, as the user picked it.
    content: str = Field(min_length=1, max_length=50_000_000)


class UnmatchedRecord(BaseModel):
    ref: str
    title: str
    problem: MatchProblem


class UnknownCriterion(BaseModel):
    code: str
    # How many of the file's decisions cite it; they were not imported.
    decisions: int


class SkippedDecision(BaseModel):
    # The decision's id in the exporting library.
    source_id: str
    stage: ScreeningStage
    # Why this review's rules refused it (an error code).
    code: str


class ImportReport(BaseModel):
    reviewer: str
    records: int
    matched: int
    # Rows appended: first decisions, and corrections of earlier imported ones.
    added: int
    corrected: int
    # Decisions already in force as the file has them; nothing written.
    unchanged: int
    # Imported decisions in force that the file no longer has; left as they are.
    withdrawn: int
    unmatched: list[UnmatchedRecord]
    unknown_criteria: list[UnknownCriterion]
    skipped: list[SkippedDecision]


class StageAgreementView(BaseModel):
    stage: ScreeningStage
    # Records both reviewers decided at this stage (their own decisions, before reconciling).
    compared: int
    agreed: int
    # 0-100; None with nothing to compare.
    percent: float | None
    # Cohen's kappa; None when undefined (nothing compared, or one category throughout).
    kappa: float | None
    # Disagreements nobody has reconciled yet.
    conflicts: int


class AgreementView(BaseModel):
    # The colleague compared with the owner; None when no colleague's decisions are here.
    reviewer: str | None
    reviewers: list[str]
    stages: list[StageAgreementView]


class SideDecision(BaseModel):
    decision: Decision
    criterion_code: str | None
    criterion_text: str | None
    note: str | None


class ConflictView(BaseModel):
    paper_id: str
    title: str
    first_author: str | None
    author_count: int
    year: int | None
    venue: str | None
    owner: SideDecision
    other: SideDecision


class ConflictList(BaseModel):
    reviewer: str | None
    stage: ScreeningStage
    items: list[ConflictView]


class Reconciliation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    paper_id: str
    decision: ChosenDecision
    criterion_id: str | None = None
    note: str | None = Field(default=None, max_length=10_000)
