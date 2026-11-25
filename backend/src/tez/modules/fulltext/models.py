from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
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
