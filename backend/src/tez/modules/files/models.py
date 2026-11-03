from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, TimestampMixin, enum_type


class AttachmentKind(StrEnum):
    PDF = "pdf"
    SUPPLEMENT = "supplement"


class TextStatus(StrEnum):
    PENDING = "pending"
    OK = "ok"
    NEEDS_OCR = "needs_ocr"
    FAILED = "failed"


class Attachment(TimestampMixin, Base):
    __tablename__ = "attachment"
    __table_args__ = (
        CheckConstraint("length(sha256) = 64", name="sha256_length"),
        CheckConstraint("page_count >= 0", name="page_count"),
    )

    # RESTRICT: deleting a paper must also delete its files on disk, so it is explicit.
    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[AttachmentKind] = mapped_column(
        enum_type(AttachmentKind, "kind"), default=AttachmentKind.PDF
    )
    # Relative to the library folder: files/<first 2 hex>/<sha256>.pdf
    rel_path: Mapped[str] = mapped_column(Text)
    # The same file is stored once.
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    page_count: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(Text)
    text_status: Mapped[TextStatus] = mapped_column(
        enum_type(TextStatus, "text_status"), default=TextStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text)
