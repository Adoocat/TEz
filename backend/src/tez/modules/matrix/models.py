"""The literature matrix (plan, data model group 3; Task 51, ADR 0035).

A review has matrices; a matrix has typed columns. Its rows are not stored as a list: they
are the papers included at full text, so a paper that leaves the review leaves the grid. A
`matrix_row` is made for a paper the first time one of its cells is written, and it stays,
with its cells, when the paper is excluded later: including it again brings them back.
"""

from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, CreatedMixin, TimestampMixin, enum_type
from tez.modules.matrix.values import DataType


class CellOrigin(StrEnum):
    MANUAL = "manual"
    # An AI suggestion the user accepted (Phase 5); never written without that.
    AI_ACCEPTED = "ai_accepted"


class Matrix(TimestampMixin, Base):
    __tablename__ = "matrix"

    review_id: Mapped[str] = mapped_column(ForeignKey("review.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)


class MatrixColumn(TimestampMixin, Base):
    __tablename__ = "matrix_column"

    matrix_id: Mapped[str] = mapped_column(ForeignKey("matrix.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    # What to write here: a note for the user, and later the instruction an AI is given.
    instruction: Mapped[str | None] = mapped_column(Text)
    data_type: Mapped[DataType] = mapped_column(enum_type(DataType, "matrix_data_type"))
    # [{"id": "...", "label": "Survey"}, ...] for enum and multi_enum; [] otherwise.
    options_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class MatrixRow(TimestampMixin, Base):
    __tablename__ = "matrix_row"
    __table_args__ = (UniqueConstraint("matrix_id", "paper_id"),)

    matrix_id: Mapped[str] = mapped_column(ForeignKey("matrix.id", ondelete="CASCADE"))
    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="RESTRICT"), index=True)


class MatrixCell(TimestampMixin, Base):
    __tablename__ = "matrix_cell"
    __table_args__ = (UniqueConstraint("row_id", "column_id"),)

    row_id: Mapped[str] = mapped_column(ForeignKey("matrix_row.id", ondelete="CASCADE"))
    column_id: Mapped[str] = mapped_column(
        ForeignKey("matrix_column.id", ondelete="CASCADE"), index=True
    )
    # The value in the column's type (text, number, true/false, option id or ids).
    value_json: Mapped[Any] = mapped_column(JSON(none_as_null=True), nullable=True)
    # Set only when a type change could not convert the value: the text it was, kept.
    value_text: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[CellOrigin] = mapped_column(
        enum_type(CellOrigin, "matrix_cell_origin"), default=CellOrigin.MANUAL
    )


class CellEvidence(CreatedMixin, Base):
    """A passage in a PDF that a cell's value rests on (Task 53). A cell can have several."""

    __tablename__ = "cell_evidence"
    __table_args__ = (UniqueConstraint("cell_id", "anchor_id"),)

    cell_id: Mapped[str] = mapped_column(ForeignKey("matrix_cell.id", ondelete="CASCADE"))
    # Anchors are never deleted (ADR 0033): a lost one stays visible as lost.
    anchor_id: Mapped[str] = mapped_column(ForeignKey("anchor.id", ondelete="RESTRICT"), index=True)
