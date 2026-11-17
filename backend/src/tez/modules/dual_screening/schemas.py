from pydantic import BaseModel, Field

from tez.modules.dual_screening.matching import MatchProblem
from tez.modules.reviews.models import ScreeningStage


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
