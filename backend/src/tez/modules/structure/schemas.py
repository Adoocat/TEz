from datetime import datetime

from pydantic import BaseModel


class SectionView(BaseModel):
    type: str
    heading: str
    page_start: int | None
    page_end: int | None


class ReferenceView(BaseModel):
    ord: int
    raw_text: str
    title: str | None
    authors: list[str]
    year: int | None
    doi: str | None
    page: int | None
    matched_paper_id: str | None


class StructureView(BaseModel):
    """What GROBID read from a file; empty lists until it was read."""

    read_at: datetime | None
    error: str | None
    sections: list[SectionView]
    references: list[ReferenceView]


class StructureQueued(BaseModel):
    job_id: str


class GrobidStatus(BaseModel):
    """Whether GROBID is set up; everything that needs it is hidden while it is not."""

    configured: bool
