from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from tez.core.errors import ErrorDetail
from tez.modules.reviews.models import RecordOrigin, ScreeningStage
from tez.modules.search.models import InitiatedVia, RunStatus
from tez.modules.search.schemas import MAX_RESULTS_PER_SOURCE
from tez.modules.snowballing.sources import CITATION_SOURCES, Direction


class SnowballStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Seeds: papers of the review included so far (at title-abstract or full text).
    paper_ids: list[str] = Field(min_length=1, max_length=500)
    directions: list[Direction] = Field(min_length=1)
    sources: list[str] = Field(min_length=1, examples=[list(CITATION_SOURCES)])
    # Per seed, direction and source.
    limit: int = Field(default=1000, ge=1, le=MAX_RESULTS_PER_SOURCE)
    initiated_via: InitiatedVia = InitiatedVia.GUI


class SnowballStarted(BaseModel):
    search_id: str
    round: int
    job_id: str


class SnowballRunView(BaseModel):
    seed_paper_id: str
    direction: Direction
    source: str
    status: RunStatus
    translated_query: str | None
    total_reported: int | None
    retrieved_count: int
    error: ErrorDetail | None


class SnowballRoundView(BaseModel):
    """One snowballing action and what it found. Every count is derived."""

    search_id: str
    round: int
    started_at: datetime
    directions: list[Direction]
    sources: list[str]
    seeds: int
    # Records the sources returned, repeats included (PRISMA's "identified").
    identified: int
    unique: int
    # Taken into the review by this action; the rest were already there.
    added: int
    already_in_review: int
    runs: list[SnowballRunView]


class RoundCount(BaseModel):
    """One snowballing round across its actions, for PRISMA's other-methods branch."""

    round: int
    identified: int
    unique: int
    added: int


class SnowballSeed(BaseModel):
    paper_id: str
    title: str
    first_author: str | None
    year: int | None
    origin: RecordOrigin
    # 0 for papers from database searches or added by hand; else the round that found it.
    round: int
    included_at: ScreeningStage
    # A source can look the paper up (it has an OpenAlex, Semantic Scholar, DOI or arXiv id).
    traceable: bool
    # Directions already followed from this paper.
    followed: list[Direction]
