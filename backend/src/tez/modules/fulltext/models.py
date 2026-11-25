from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, TimestampMixin


class TextChunk(TimestampMixin, Base):
    """The text of one page of a PDF, as PDFium reads it (Task 43).

    `text` has exactly one character per PDFium character of the page, so a position in it is
    also a position PDFium can give a box for (ADR 0030). `char_start` and `char_end` are that
    range; a chunk is a whole page today, and can become part of one later.
    """

    __tablename__ = "text_chunk"
    __table_args__ = (
        UniqueConstraint("attachment_id", "ord"),
        # Everything a search needs about a page, without reading the row and its text.
        Index("ix_text_chunk_search", "search_row", "attachment_id", "page_index"),
        CheckConstraint("page_index >= 0", name="page_index"),
        CheckConstraint("char_end >= char_start", name="char_range"),
    )

    attachment_id: Mapped[str] = mapped_column(ForeignKey("attachment.id", ondelete="CASCADE"))
    # Counts from 0.
    page_index: Mapped[int] = mapped_column(Integer)
    ord: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    # The page's rowid in `chunk_fts` (search_index.py).
    search_row: Mapped[int] = mapped_column(Integer, unique=True)
