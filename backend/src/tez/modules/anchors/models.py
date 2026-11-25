"""Anchors: a place in a PDF (plan, data model group 3).

Everything taken from a PDF points at one (CLAUDE.md rule 2): highlights, note quotes, matrix
evidence, later AI quotes. Coordinates are PDF user space, not pixels; the quoted text with what
stands before and after it finds the place again when the file changes.
"""

from enum import StrEnum

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, TimestampMixin, enum_type


class AnchorKind(StrEnum):
    TEXT = "text"
    # A rectangle drawn on the page: a figure, a table, a scan without text.
    AREA = "area"


class AnchorState(StrEnum):
    # The quote is in the file's text, at `char_start`..`char_end` (an area: drawn on this file).
    VERIFIED = "verified"
    # The text is not read yet, or the quote is not in it as the reader showed it.
    UNVERIFIED = "unverified"
    # The file changed and the place is not in the new one.
    LOST = "lost"


class Anchor(TimestampMixin, Base):
    __tablename__ = "anchor"
    __table_args__ = (
        CheckConstraint("page_index >= 0", name="page_index"),
        CheckConstraint("char_end > char_start", name="char_range"),
    )

    # RESTRICT: evidence does not disappear because a file was removed.
    attachment_id: Mapped[str] = mapped_column(
        ForeignKey("attachment.id", ondelete="RESTRICT"), index=True
    )
    # The file the coordinates belong to; another hash on the attachment means it was replaced.
    file_sha256: Mapped[str] = mapped_column(String(64))
    kind: Mapped[AnchorKind] = mapped_column(enum_type(AnchorKind, "kind"))
    state: Mapped[AnchorState] = mapped_column(enum_type(AnchorState, "state"))
    # Counts from 0.
    page_index: Mapped[int] = mapped_column(Integer)
    # [[left, bottom, right, top], ...] in points, one per line of text.
    rects_json: Mapped[list[list[float]]] = mapped_column(JSON)
    # Empty for an area.
    quote_exact: Mapped[str] = mapped_column(Text, default="")
    quote_prefix: Mapped[str] = mapped_column(Text, default="")
    quote_suffix: Mapped[str] = mapped_column(Text, default="")
    # Positions in the page's `text_chunk.text`, when verified.
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
