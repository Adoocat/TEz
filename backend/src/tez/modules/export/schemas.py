from typing import Literal

from pydantic import BaseModel, Field

from tez.modules.export.csl import CslLocale, CslStyle


class ExportResult(BaseModel):
    format: Literal["bibtex", "ris"]
    # Papers written.
    count: int
    content: str


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
