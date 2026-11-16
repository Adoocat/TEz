from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from tez.modules.library.models import ThesisType
from tez.modules.search.models import RunMethod


class GreyKind(StrEnum):
    THESIS = "thesis"
    REPORT = "report"
    REGISTER_RECORD = "register_record"
    WEB_PAGE = "web_page"


# PRISMA 2020's other-methods boxes a grey-literature record is counted in (ADR 0025).
GreyBox = Literal[RunMethod.WEBSITE, RunMethod.ORGANISATION, RunMethod.REGISTER, RunMethod.THESIS]

Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class GreyRecordCreate(BaseModel):
    """One record entered by hand: a thesis, a report, a register record or a web page."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: GreyKind
    # The PRISMA box; left out, it follows the kind (a thesis counts as a thesis, a web page
    # as a website, a register record as a register, a report as an organisation's).
    found_via: GreyBox | None = None
    # Where it was found, as the methods section names it: "YÖK Ulusal Tez Merkezi", "WHO".
    source: str = Field(min_length=1, max_length=64)
    found_at: date | None = None
    title: Line
    authors: list[Line] = Field(default_factory=list[str], max_length=100)
    year: int | None = Field(default=None, ge=1000, le=2100)
    # University, organisation or registry.
    institution: str | None = Field(default=None, max_length=500)
    thesis_type: ThesisType | None = None
    url: str | None = Field(default=None, max_length=2000)
    doi: str | None = Field(default=None, max_length=200)
    abstract: str | None = Field(default=None, max_length=20_000)


class GreyRecordAdded(BaseModel):
    paper_id: str
    search_id: str
    found_via: GreyBox
    # The record matched a paper the library already had (a duplicate for PRISMA).
    matched_existing: bool
    # False when the paper was already in the review.
    added_to_review: bool


class GreyEntry(BaseModel):
    """A grey-literature run of the review: one record by hand, or a marked import."""

    search_id: str
    found_via: RunMethod
    source: str
    executed_at: datetime
    file_name: str | None
    records: int
    titles: list[str]
