from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    model_validator,
)

from tez.modules.library.models import ReadingStatus
from tez.modules.matrix.models import CellOrigin
from tez.modules.matrix.values import DataType
from tez.shared.text import fold

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Instruction = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Word = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
# What a cell holds: text, a number, yes/no, an option id or several (null: empty).
CellValue = StrictBool | StrictInt | StrictFloat | StrictStr | list[StrictStr] | None


class OptionIn(BaseModel):
    """An option as the user edits it: with its id when it already exists."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, max_length=36)
    label: Label


class OptionView(BaseModel):
    id: str
    label: str


def _unique_labels(options: list[OptionIn] | None) -> None:
    labels = [fold(option.label) for option in options or []]
    if len(set(labels)) != len(labels):
        raise ValueError("option labels must differ")


class MatrixCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name


class MatrixPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name


class ColumnCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    instruction: Instruction | None = None
    data_type: DataType = DataType.TEXT
    options: list[OptionIn] = Field(default_factory=list[OptionIn], max_length=200)

    @model_validator(mode="after")
    def _check(self) -> Self:
        _unique_labels(self.options)
        return self


class ColumnPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    instruction: Instruction | None = None


class TypeChange(BaseModel):
    """A new type or new options for a column; the cells are converted, none dropped."""

    model_config = ConfigDict(extra="forbid")

    data_type: DataType
    # For enum and multi-enum. Left out: the choices already written in the cells.
    options: list[OptionIn] | None = Field(default=None, max_length=200)
    # Only report what would happen.
    dry_run: bool = False
    # How yes and no are written if a yes/no column becomes text: the user's language.
    true_text: Word = "yes"
    false_text: Word = "no"

    @model_validator(mode="after")
    def _check(self) -> Self:
        _unique_labels(self.options)
        return self


class ColumnOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column_ids: list[str] = Field(max_length=500)


class CellPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: CellValue
    # With a null value: put back text a type change kept (undo of an edit over it).
    kept_text: Annotated[str, StringConstraints(min_length=1, max_length=10_000)] | None = None

    @model_validator(mode="after")
    def _one_of(self) -> Self:
        if self.value is not None and self.kept_text is not None:
            raise ValueError("a value or kept text, not both")
        return self


class ColumnView(BaseModel):
    id: str
    name: str
    instruction: str | None
    data_type: DataType
    options: list[OptionView]
    sort_order: int


class EvidenceView(BaseModel):
    """A passage a cell rests on, enough to show it and to go there."""

    anchor_id: str
    attachment_id: str
    page: int
    quote: str
    # verified / unverified / checking / lost (ADR 0033)
    status: str


class CellView(BaseModel):
    column_id: str
    value: CellValue
    # Not null when a type change could not convert the value: the text it was.
    kept_text: str | None
    origin: CellOrigin
    updated_at: datetime
    evidence: list[EvidenceView]


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor_id: str
    # Write the passage into the cell when it is an empty text cell.
    fill: bool = False


class Coverage(BaseModel):
    """How much of the included papers' content rests on a passage (derived)."""

    filled: int
    sourced: int
    rows: int
    rows_sourced: int


class RowView(BaseModel):
    paper_id: str
    title: str
    year: int | None
    venue: str | None
    first_author: str | None
    author_count: int
    reading_status: ReadingStatus
    # False for a paper excluded after its cells were written: they are kept, not shown.
    included: bool
    cells: list[CellView]


class MatrixSummary(BaseModel):
    id: str
    review_id: str
    name: str
    columns: int
    created_at: datetime


class MatrixView(BaseModel):
    id: str
    review_id: str
    name: str
    columns: list[ColumnView]
    # The included papers in screening order, then excluded ones that have cells.
    rows: list[RowView]
    coverage: Coverage


class PaperMatrix(BaseModel):
    """A matrix a paper is a row of, with that row's cells (the reader's Matrix tab)."""

    matrix_id: str
    matrix_name: str
    review_id: str
    columns: list[ColumnView]
    cells: list[CellView]


class KeptCell(BaseModel):
    paper_id: str
    text: str


class TypeChangeReport(BaseModel):
    column: ColumnView
    applied: bool
    cells: int
    converted: int
    # Cells whose value could not be read as the new type: kept as text, marked.
    kept: list[KeptCell]
