from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from tez.modules.anchors.schemas import AnchorView
from tez.modules.notes.models import LinkTarget

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Body = Annotated[str, Field(max_length=1_000_000)]


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    body: Body = ""
    parent_id: str | None = None
    paper_id: str | None = None
    review_id: str | None = None


class NotePatch(BaseModel):
    """What to change; fields left out stay. `null` clears a parent, paper or review."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    body: Body | None = None
    parent_id: str | None = None
    paper_id: str | None = None
    review_id: str | None = None
    # The version the change is based on; another one is `note.conflict`. Left out: no check.
    base_version: int | None = None


class NoteAppend(BaseModel):
    """Add to the end of a note without opening it (a quote from the reader)."""

    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=100_000)]


class NoteSummary(BaseModel):
    id: str
    title: str
    parent_id: str | None
    paper_id: str | None
    review_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class NoteLinkView(BaseModel):
    """A link in the note. `broken`: its target is gone, or `[[name]]` names nothing."""

    target_type: LinkTarget | None
    target_id: str | None
    label: str
    status: Literal["ok", "broken"]
    # The target's own title now, for a note or a paper.
    title: str | None
    anchor: AnchorView | None


class NoteView(NoteSummary):
    body: str
    links: list[NoteLinkView]


class Backlink(BaseModel):
    """A note that links here, with the passage the link is in."""

    note_id: str
    title: str
    passage: str


class NoteHitPart(BaseModel):
    text: str
    hit: bool


class NoteHit(BaseModel):
    note_id: str
    title: str
    passage: list[NoteHitPart]


class LinkSuggestion(BaseModel):
    """Something `[[` can link to."""

    target_type: Literal["note", "paper"]
    target_id: str
    title: str
    # For a paper: "Kim et al. 2024".
    detail: str | None
