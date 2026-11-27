"""A paper's sections and reference list, read by GROBID (plan, data model group 4; Task 56).

`structure_read` says a file was read, when, and why it failed if it did; the sections and
references of a file are replaced whole by each reading.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, CreatedMixin, TimestampMixin, UtcDateTime


class StructureRead(TimestampMixin, Base):
    __tablename__ = "structure_read"

    attachment_id: Mapped[str] = mapped_column(
        ForeignKey("attachment.id", ondelete="CASCADE"), unique=True
    )
    read_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # An error code when the last reading failed (grobid.unreachable, ...).
    error: Mapped[str | None] = mapped_column(String(64))


class DocumentSection(CreatedMixin, Base):
    __tablename__ = "document_section"
    __table_args__ = (UniqueConstraint("attachment_id", "ord"),)

    attachment_id: Mapped[str] = mapped_column(ForeignKey("attachment.id", ondelete="CASCADE"))
    ord: Mapped[int] = mapped_column(Integer)
    # abstract / intro / method / results / discussion / other
    type: Mapped[str] = mapped_column(String(16))
    heading: Mapped[str] = mapped_column(Text)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)


class ReferenceEntry(CreatedMixin, Base):
    __tablename__ = "reference_entry"
    __table_args__ = (UniqueConstraint("attachment_id", "ord"),)

    attachment_id: Mapped[str] = mapped_column(ForeignKey("attachment.id", ondelete="CASCADE"))
    ord: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text)
    # {"title", "authors", "year", "doi", "page"} as GROBID read them.
    parsed_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    # A paper in the library this reference is, found by DOI or by its folded title.
    matched_paper_id: Mapped[str | None] = mapped_column(
        ForeignKey("paper.id", ondelete="SET NULL"), index=True
    )
    match_score: Mapped[float | None] = mapped_column(Float)
