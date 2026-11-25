from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tez.modules.anchors.models import AnchorKind

Coordinate = Annotated[float, Field(allow_inf_nan=False, ge=-100_000, le=100_000)]
Rect = Annotated[list[Coordinate], Field(min_length=4, max_length=4)]


class AnchorCreate(BaseModel):
    """A place the user selected in the reader."""

    model_config = ConfigDict(extra="forbid")

    kind: AnchorKind = AnchorKind.TEXT
    # Counts from 1, like the reader's address.
    page: int = Field(ge=1)
    # [left, bottom, right, top] in PDF user space, one per line.
    rects: list[Rect] = Field(min_length=1, max_length=500)
    quote: str = Field(default="", max_length=20_000)
    # What stands before and after the selection on the page: tells repeats apart.
    prefix: str = Field(default="", max_length=500)
    suffix: str = Field(default="", max_length=500)
    # Which of the page's identical passages this is, from 0, in reading order.
    occurrence: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _text_has_a_quote(self) -> Self:
        if self.kind is AnchorKind.TEXT and not self.quote.strip():
            raise ValueError("a text anchor needs the selected text")
        return self


# `checking`: the file was replaced and the new one is not read yet.
AnchorStatus = Literal["verified", "unverified", "checking", "lost"]


class AnchorPaper(BaseModel):
    """Enough of the paper for a source chip ("Kim et al. 2024 · p. 7")."""

    id: str
    title: str
    first_author: str | None
    author_count: int
    year: int | None
    citekey: str | None


class AnchorView(BaseModel):
    id: str
    attachment_id: str
    kind: AnchorKind
    status: AnchorStatus
    page: int
    rects: list[Rect]
    quote: str
    prefix: str
    suffix: str
    paper: AnchorPaper
