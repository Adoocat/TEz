"""The matrix as a file: CSV, Excel or Markdown, with each value's passages and pages (Task 54).

Only the included papers' rows. Each column that has passages gets an evidence column beside it
(CSV, Excel); Markdown numbers the passages under the table. The words of the file (headers,
"p.", yes and no) come from the app in the user's language.
"""

import base64
import csv
from collections.abc import Sequence
from dataclasses import dataclass
from io import StringIO

from tez.modules.matrix import values
from tez.modules.matrix.schemas import (
    CellView,
    ColumnView,
    ExportLabels,
    MatrixExportFile,
    MatrixView,
    RowView,
)
from tez.modules.matrix.values import DataType, Option
from tez.shared.xlsx import CellValue, write_xlsx

MIME = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "md": "text/markdown",
}


@dataclass(frozen=True)
class Score:
    """A paper's quality total, out of the best it could reach (Task 38)."""

    score: float
    maximum: float


def _number(value: float) -> str:
    return f"{value:g}"


def _citation(row: RowView, labels: ExportLabels) -> str:
    family = (row.first_author or "").split(" ")[-1]
    who = f"{family} {labels.et_al}" if family and row.author_count > 1 else (family or row.title)
    return " ".join(part for part in (who, str(row.year or "")) if part)


def _value(column: ColumnView, cell: CellView | None, labels: ExportLabels) -> CellValue:
    if cell is None:
        return None
    if cell.kept_text is not None:
        return cell.kept_text
    if cell.value is None:
        return None
    if column.data_type is DataType.NUMBER and isinstance(cell.value, int | float):
        return cell.value
    options = [Option(id=o.id, label=o.label) for o in column.options]
    words = values.Words(true=labels.yes, false=labels.no)
    return values.render(column.data_type, cell.value, options, words)


def _passages(cell: CellView | None, labels: ExportLabels) -> list[str]:
    return [f"“{e.quote}” ({labels.page} {e.page})" for e in cell.evidence] if cell else []


@dataclass(frozen=True)
class Table:
    header: list[str]
    rows: list[list[CellValue]]


def table(matrix: MatrixView, scores: dict[str, Score] | None, labels: ExportLabels) -> Table:
    """The included rows as a table: citation, title, year, quality, then each column and,
    where it has any, its passages."""
    rows = [row for row in matrix.rows if row.included]
    cells = {(r.paper_id, c.column_id): c for r in rows for c in r.cells}
    with_evidence = {c.column_id for r in rows for c in r.cells if c.evidence}
    header = [labels.paper, labels.title, labels.year]
    if scores is not None:
        header.append(labels.quality)
    for column in matrix.columns:
        header.append(column.name)
        if column.id in with_evidence:
            header.append(f"{column.name} ({labels.evidence})")
    body: list[list[CellValue]] = []
    for row in rows:
        line: list[CellValue] = [_citation(row, labels), row.title, row.year]
        if scores is not None:
            score = scores.get(row.paper_id)
            line.append(f"{_number(score.score)} / {_number(score.maximum)}" if score else None)
        for column in matrix.columns:
            cell = cells.get((row.paper_id, column.id))
            line.append(_value(column, cell, labels))
            if column.id in with_evidence:
                line.append("\n".join(_passages(cell, labels)) or None)
        body.append(line)
    return Table(header=header, rows=body)


def _text(value: CellValue) -> str:
    if value is None:
        return ""
    return _number(value) if isinstance(value, float) else str(value)


def to_csv(found: Table) -> bytes:
    """UTF-8 with a byte order mark: Excel then reads Turkish letters right."""
    out = StringIO(newline="")
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(found.header)
    writer.writerows([_text(v) for v in row] for row in found.rows)
    return ("\ufeff" + out.getvalue()).encode("utf-8")


def _md(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def to_markdown(matrix: MatrixView, scores: dict[str, Score] | None, labels: ExportLabels) -> bytes:
    """A table of values, each with the numbers of its passages; the passages under it."""
    rows = [row for row in matrix.rows if row.included]
    header = [labels.paper, labels.title, labels.year]
    if scores is not None:
        header.append(labels.quality)
    header += [column.name for column in matrix.columns]
    lines = [
        f"# {_md(matrix.name)}",
        "",
        "| " + " | ".join(_md(h) for h in header) + " |",
        "|" + "---|" * len(header),
    ]
    notes: list[str] = []
    for row in rows:
        cells = {c.column_id: c for c in row.cells}
        citation = _citation(row, labels)
        line = [citation, row.title, str(row.year or "")]
        if scores is not None:
            score = scores.get(row.paper_id)
            line.append(f"{_number(score.score)} / {_number(score.maximum)}" if score else "")
        for column in matrix.columns:
            cell = cells.get(column.id)
            text = _text(_value(column, cell, labels))
            refs: list[str] = []
            for passage in _passages(cell, labels):
                notes.append(f"{citation}, {column.name}: {passage}")
                refs.append(f"[{len(notes)}]")
            line.append(" ".join(part for part in (text, "".join(refs)) if part))
        lines.append("| " + " | ".join(_md(part) for part in line) + " |")
    if notes:
        lines += ["", f"## {_md(labels.evidence)}", ""]
        lines += [f"{n}. {_md(note)}" for n, note in enumerate(notes, start=1)]
    return ("\n".join(lines) + "\n").encode("utf-8")


def to_file(
    matrix: MatrixView,
    scores: dict[str, Score] | None,
    labels: ExportLabels,
    kind: str,
) -> MatrixExportFile:
    if kind == "md":
        data = to_markdown(matrix, scores, labels)
    else:
        found = table(matrix, scores, labels)
        rows: Sequence[Sequence[CellValue]] = [found.header, *found.rows]
        data = to_csv(found) if kind == "csv" else write_xlsx(rows, matrix.name)
    return MatrixExportFile(
        mime_type=MIME[kind], content_base64=base64.b64encode(data).decode("ascii")
    )
