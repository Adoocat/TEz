from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from tez.modules.files.schemas import AttachmentView
from tez.modules.library.models import (
    IdentifierScheme,
    ReadingStatus,
    RetractionStatus,
    ThesisType,
    VenueType,
)

InstanceKind = Literal["app", "cli"]


class LibraryInfo(BaseModel):
    path: str
    name: str
    schema_revision: str


class ApiEndpoint(BaseModel):
    url: str
    token: str


class Instance(BaseModel):
    """Contents of `.tez/instance.json`: who has the library open, and how to reach it."""

    pid: int
    kind: InstanceKind
    host: str
    started_at: str
    version: str
    api: ApiEndpoint | None = None


class PaperSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_ids: list[str] = Field(min_length=1, max_length=20000)
    # Where the selection came from, kept on each new review record.
    search_id: str | None = None


class SelectionResult(BaseModel):
    added: int
    already_present: int


# --- collections, tags, reading status (Task 18) ----------------------------------------

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
# A colour token name or a #rrggbb value; the UI maps names to design tokens.
Color = Annotated[str, StringConstraints(pattern=r"^(#[0-9a-fA-F]{6}|[a-z]+)$", max_length=16)]


class CollectionView(BaseModel):
    id: str
    parent_id: str | None
    name: str
    sort_order: int
    # System collections (the inbox) have a fixed name the UI translates.
    is_system: bool
    # Papers directly in it, trash excluded.
    paper_count: int


class CollectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    parent_id: str | None = None


class CollectionPatch(BaseModel):
    """Only the fields sent change; `parent_id: null` moves it to the top level."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    parent_id: str | None = None


class TagView(BaseModel):
    id: str
    name: str
    color: str | None
    paper_count: int


class TagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    color: Color | None = None


class TagPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None
    ) = None
    color: Color | None = None


class PaperIds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_ids: list[str] = Field(min_length=1, max_length=20000)


class ReadingStatusChange(PaperIds):
    reading_status: ReadingStatus


class ChangeCount(BaseModel):
    changed: int
    unchanged: int


PdfState = Literal["none", "pending", "ok", "needs_ocr", "failed"]


class LibraryPaperRow(BaseModel):
    """A paper in the library list (Task 18; Task 19 adds the columns of the full table)."""

    id: str
    title: str
    first_author: str | None
    author_count: int
    year: int | None
    venue: str | None
    venue_type: VenueType | None
    thesis_type: ThesisType | None
    doi: str | None
    citekey: str | None
    citation_count: int | None
    reading_status: ReadingStatus
    tag_ids: list[str]
    collection_ids: list[str]
    pdf: PdfState
    added_at: datetime | None


class SearchHits(BaseModel):
    # Best match first. The list filters its loaded rows by these ids.
    paper_ids: list[str]
    elapsed_ms: float


class AuthorView(BaseModel):
    display_name: str
    family: str | None
    given: str | None
    orcid: str | None
    affiliation: str | None


class RelatedPaper(BaseModel):
    paper_id: str
    title: str
    year: int | None
    # How the related paper stands to this one.
    relation: Literal["preprint", "published_version", "erratum", "retraction"]


class PaperDetail(BaseModel):
    """Everything the inspector shows about one paper (design 4.4)."""

    id: str
    title: str
    abstract: str | None
    year: int | None
    venue: str | None
    venue_type: VenueType | None
    thesis_type: ThesisType | None
    volume: str | None
    issue: str | None
    pages: str | None
    language: str | None
    url: str | None
    oa_url: str | None
    citation_count: int | None
    reading_status: ReadingStatus
    citekey: str | None
    retraction_status: RetractionStatus
    added_at: datetime | None
    authors: list[AuthorView]
    identifiers: dict[IdentifierScheme, str]
    tag_ids: list[str]
    collection_ids: list[str]
    attachments: list[AttachmentView]
    related: list[RelatedPaper]


class PaperPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citekey: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
