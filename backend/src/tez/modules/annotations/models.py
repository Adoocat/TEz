"""Highlights and marked areas in PDFs, with the reader's comment (plan, data model group 3)."""

from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, TimestampMixin, enum_type


class AnnotationKind(StrEnum):
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    AREA = "area"


class Annotation(TimestampMixin, Base):
    __tablename__ = "annotation"

    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="RESTRICT"), index=True)
    # A passage is marked once; marking it again changes its colour.
    anchor_id: Mapped[str] = mapped_column(
        ForeignKey("anchor.id", ondelete="RESTRICT"), unique=True
    )
    kind: Mapped[AnnotationKind] = mapped_column(enum_type(AnnotationKind, "kind"))
    # A design-token name (--color-highlight-<name>), never a raw value.
    color: Mapped[str] = mapped_column(String(16))
    comment_md: Mapped[str] = mapped_column(Text, default="")
