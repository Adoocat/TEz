"""PRISMA 2020 flow counts (Task 34). Every number is derived on each read; none is stored."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from tez.modules.search.models import RunMethod


class SourceCount(BaseModel):
    """Records one source returned across its runs, repeats included."""

    source: str
    runs: int
    identified: int


class OtherMethodCount(BaseModel):
    """Records one other method found: snowballing (per round), websites, organisations,
    registers or theses."""

    method: RunMethod
    # Snowballing only: the round (Wohlin); None for the other methods.
    round: int | None
    identified: int


class ReasonCount(BaseModel):
    criterion_id: str | None
    code: str | None
    text: str | None
    count: int


class Branch(BaseModel):
    """One side of the PRISMA 2020 diagram, from identification to inclusion.

    Invariants (tested): identified = duplicates + not_taken + screened;
    screened = excluded + awaiting_screening + sought; sought = not_retrieved + assessed +
    awaiting_full_text; assessed = sum(excluded_reports) + included.
    """

    identified: int
    # Of those, records in the review with no logged run (from before runs were kept).
    unlogged: int
    # Records that matched a paper found before (in this branch or the other one).
    duplicates: int
    # Found by a search but never taken into the review ("removed for other reasons").
    not_taken: int
    # Title-abstract screening.
    screened: int
    excluded: int
    awaiting_screening: int
    # Full text: reports sought for retrieval, not retrieved, assessed for eligibility.
    sought: int
    not_retrieved: int
    assessed: int
    awaiting_full_text: int
    excluded_reports: list[ReasonCount]
    included: int


class DatabasesBranch(Branch):
    sources: list[SourceCount]


class OtherMethodsBranch(Branch):
    methods: list[OtherMethodCount]


class PrismaCounts(BaseModel):
    review_id: str
    databases: DatabasesBranch
    other_methods: OtherMethodsBranch
    # Studies included in the review: both branches.
    included: int


# The diagram's boxes whose titles can be edited (Task 35); the web app draws the same list.
BoxKey = Literal[
    "identification",
    "screening",
    "included_phase",
    "db_identified",
    "db_removed",
    "db_screened",
    "db_excluded",
    "db_sought",
    "db_not_retrieved",
    "db_assessed",
    "db_reports_excluded",
    "other_identified",
    "other_removed",
    "other_screened",
    "other_excluded",
    "other_sought",
    "other_not_retrieved",
    "other_assessed",
    "other_reports_excluded",
    "included",
]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class PrismaLabels(BaseModel):
    """Edited box titles; a box not listed shows its translated default."""

    model_config = ConfigDict(extra="forbid")

    labels: dict[BoxKey, Label]
