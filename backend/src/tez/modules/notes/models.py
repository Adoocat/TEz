"""Notes and what they link to (plan, data model group 3; ADR 0034)."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, TimestampMixin, UtcDateTime, enum_type


class Note(TimestampMixin, Base):
    __tablename__ = "note"

    title: Mapped[str] = mapped_column(Text)
    body_md: Mapped[str] = mapped_column(Text, default="")
    # The note tree: a note can hold others.
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("note.id", ondelete="SET NULL"), index=True
    )
    paper_id: Mapped[str | None] = mapped_column(
        ForeignKey("paper.id", ondelete="SET NULL"), index=True
    )
    review_id: Mapped[str | None] = mapped_column(
        ForeignKey("review.id", ondelete="SET NULL"), index=True
    )
    # Counts every save; a save based on an older one is refused (`note.conflict`).
    version: Mapped[int] = mapped_column(Integer, default=1)
    # Deleted notes can be restored.
    deleted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class LinkTarget(StrEnum):
    NOTE = "note"
    PAPER = "paper"
    ANCHOR = "anchor"


class NoteLink(TimestampMixin, Base):
    """One link in a note's text, read from it at every save. Backlinks are the reverse query."""

    __tablename__ = "note_link"
    __table_args__ = (
        CheckConstraint("(target_type IS NULL) = (target_id IS NULL)", name="target_is_whole"),
    )

    source_note_id: Mapped[str] = mapped_column(
        ForeignKey("note.id", ondelete="CASCADE"), index=True
    )
    ord: Mapped[int] = mapped_column(Integer)
    # Null for a [[name]] that names nothing (yet). Not a foreign key: a target can go, and then
    # the link is shown as broken.
    target_type: Mapped[LinkTarget | None] = mapped_column(enum_type(LinkTarget, "target_type"))
    target_id: Mapped[str | None] = mapped_column(String(36), index=True)
    # The words of the link, as written.
    label: Mapped[str] = mapped_column(Text)
