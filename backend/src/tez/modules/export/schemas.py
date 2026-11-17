from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from tez.modules.export.csl import CslLocale, CslStyle
from tez.modules.search.models import RunMethod, RunStatus


class ExportResult(BaseModel):
    format: Literal["bibtex", "ris"]
    # Papers written.
    count: int
    content: str
    # In the file's order.
    citekeys: list[str]


class ExportRequest(BaseModel):
    format: Literal["bibtex", "ris"] = "bibtex"
    # One scope at most; none is the whole library.
    review_id: str | None = None
    # With a review: only its included studies, not every paper taken into it.
    included: bool = False
    collection_id: str | None = None
    paper_ids: list[str] | None = Field(default=None, max_length=10_000)


class BibliographyRequest(BaseModel):
    style: CslStyle = CslStyle.APA
    locale: CslLocale = CslLocale.TR
    # One scope at most; none is the whole library. A review means its included studies.
    review_id: str | None = None
    collection_id: str | None = None
    paper_ids: list[str] | None = Field(default=None, max_length=10_000)


class BibliographyEntry(BaseModel):
    citekey: str
    # Inline HTML (escaped text with <i>, <b>, <sup>, <sub>, small-caps <span>).
    html: str
    text: str


class BibliographyResult(BaseModel):
    style: CslStyle
    locale: CslLocale
    count: int
    # In the style's order.
    entries: list[BibliographyEntry]
    # The whole list: one line per entry, and one <p> per entry (pastes into Word with its
    # formatting).
    text: str
    html: str


class StrategyRow(BaseModel):
    run_id: str
    # A provider id ("openalex"), a database name for an import ("Scopus"), or the source of
    # a snowballing or grey-literature run.
    source: str
    method: RunMethod
    snowball_round: int | None
    executed_at: datetime
    # Exactly as sent to the source, or as the user ran it there (imports).
    query: str | None
    file_name: str | None
    # What the source said it had; None when it does not say (files, some APIs).
    total_reported: int | None
    retrieved: int
    status: RunStatus


class SearchStrategy(BaseModel):
    review_id: str
    # Oldest first; one per search run.
    rows: list[StrategyRow]
