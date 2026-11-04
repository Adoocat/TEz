"""`NormalizedRecord`: one paper as any source or import file describes it (plan, Task 10).

Sources send messy data. An impossible optional value (a year 0, a blank venue, a link that
is not a web link) means "unknown" and becomes None, so one bad field does not lose a paper.
A record with no title is unusable and is rejected. So is an unknown scheme or venue type:
those come from our own mapping code, not from the source, so they are bugs.

Identifiers are kept as the source sent them; deduplication normalizes them (Task 12).
"""

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from tez.core.errors import ErrorDetail
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.models import InitiatedVia, MatchMethod, RunStatus
from tez.shared.text import normalize_title

_MIN_YEAR = 1000
_SHORT_FIELD_LENGTH = 32  # paper.volume, paper.issue, paper.pages
_ORCID = re.compile(r"(?:https?://(?:www\.)?orcid\.org/)?(\d{4}-\d{4}-\d{4}-\d{3}[\dX])")
_WEB_LINK = re.compile(r"https?://\S+", re.IGNORECASE)
_LATEST_PLAUSIBLE_YEAR_AHEAD = 2  # Journals date issues ahead of publication.


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip() or None
    return value


def _short_or_none(value: Any) -> Any:
    value = _blank_to_none(value)
    if isinstance(value, str) and len(value) > _SHORT_FIELD_LENGTH:
        return None
    return value


def _web_link_or_none(value: Any) -> Any:
    value = _blank_to_none(value)
    if isinstance(value, str) and _WEB_LINK.fullmatch(value) is None:
        return None
    return value


def _orcid_or_none(value: Any) -> Any:
    value = _blank_to_none(value)
    if not isinstance(value, str):
        return value
    match = _ORCID.fullmatch(value)
    return match.group(1) if match else None


Text = Annotated[str | None, BeforeValidator(_blank_to_none)]
ShortText = Annotated[str | None, BeforeValidator(_short_or_none)]
WebLink = Annotated[str | None, BeforeValidator(_web_link_or_none)]


class RecordAuthor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    display_name: str
    family: Text = None
    given: Text = None
    orcid: Annotated[str | None, BeforeValidator(_orcid_or_none)] = None
    affiliation: Text = None


class NormalizedRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(min_length=1)
    authors: tuple[RecordAuthor, ...] = ()
    year: int | None = None
    identifiers: dict[IdentifierScheme, str] = Field(default_factory=dict[IdentifierScheme, str])
    abstract: Text = None
    venue: Text = None
    venue_type: VenueType | None = None
    volume: ShortText = None
    issue: ShortText = None
    pages: ShortText = None
    language: Text = None
    url: WebLink = None
    oa_url: WebLink = None
    citation_count: int | None = None
    is_retracted: bool = False

    @property
    def title_norm(self) -> str:
        return normalize_title(self.title)

    @field_validator("title", mode="before")
    @classmethod
    def _collapse_title(cls, value: Any) -> Any:
        return " ".join(value.split()) if isinstance(value, str) else value

    @field_validator("authors", mode="before")
    @classmethod
    def _drop_nameless_authors(cls, value: Any) -> Any:
        if not isinstance(value, list | tuple):
            return value
        return tuple(a for a in value if _author_name(a))  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]

    @field_validator("year", mode="after")
    @classmethod
    def _plausible_year(cls, value: int | None) -> int | None:
        latest = datetime.now(UTC).year + _LATEST_PLAUSIBLE_YEAR_AHEAD
        return value if value is not None and _MIN_YEAR <= value <= latest else None

    @field_validator("citation_count", mode="after")
    @classmethod
    def _non_negative(cls, value: int | None) -> int | None:
        return value if value is not None and value >= 0 else None

    @field_validator("language", mode="after")
    @classmethod
    def _lower_language(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None

    @field_validator("identifiers", mode="before")
    @classmethod
    def _drop_blank_identifiers(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        stripped = {k: _blank_to_none(v) for k, v in value.items()}  # pyright: ignore[reportUnknownVariableType]
        return {k: v for k, v in stripped.items() if v is not None}  # pyright: ignore[reportUnknownVariableType]


def _author_name(author: Any) -> bool:
    name: Any = "?"  # Not an author at all: let validation report it.
    if isinstance(author, RecordAuthor):
        name = author.display_name
    elif isinstance(author, dict):
        name = author.get("display_name")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return not isinstance(name, str) or bool(name.strip())


# --- API ------------------------------------------------------------------------------

MAX_RESULTS_PER_SOURCE = 5000


class SourceState(StrEnum):
    WAITING = "waiting"
    SEARCHING = "searching"
    RATE_LIMITED = "rate_limited"
    DONE = "done"
    PARTIAL = "partial"
    FAILED = "failed"


class SearchStart(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    review_id: str
    query: str = Field(min_length=1, max_length=4000)
    sources: list[str] = Field(min_length=1)
    year_from: int | None = None
    year_to: int | None = None
    limit: int = Field(default=1000, ge=1, le=MAX_RESULTS_PER_SOURCE)

    @model_validator(mode="after")
    def _years_in_order(self) -> Self:
        if (
            self.year_from is not None
            and self.year_to is not None
            and self.year_from > self.year_to
        ):
            raise ValueError("year_from is after year_to")
        return self


class SearchStarted(BaseModel):
    search_id: str
    sources: list[str]


class SourceProgress(BaseModel):
    source: str
    state: SourceState
    retrieved: int | None = None
    total_reported: int | None = None
    # While rate limited: how long this wait lasts, for a countdown.
    wait_seconds: float | None = None
    error_code: str | None = None


class RunView(BaseModel):
    source: str
    status: RunStatus
    translated_query: str | None
    executed_at: datetime
    total_reported: int | None
    retrieved_count: int
    error: ErrorDetail | None


class SearchOverview(BaseModel):
    search_id: str
    review_id: str
    query: str
    filters: dict[str, Any] | None
    initiated_via: InitiatedVia
    started_at: datetime
    runs: list[RunView]
    retrieved: int
    unique: int
    duplicates: int
    in_library: int


class ResultSource(BaseModel):
    source: str
    rank: int
    match_method: MatchMethod
    match_score: float | None


class SearchResultRow(BaseModel):
    paper_id: str
    title: str
    first_author: str | None
    author_count: int
    year: int | None
    venue: str | None
    venue_type: VenueType | None
    abstract: str | None
    citation_count: int | None
    doi: str | None
    arxiv_id: str | None
    url: str | None
    oa_url: str | None
    language: str | None
    is_retracted: bool
    in_library: bool
    in_review: bool
    sources: list[ResultSource]
