"""The literature matrix (Task 51, ADR 0035).

Rows are derived: the papers whose current full-text decision is include (reconciled where
two reviewers decided), in the screening service's order. Cells are kept per paper, so a paper
excluded later keeps its cells, hidden, and shows them again when it is included again. A type
change converts every cell and drops none (`values.convert`).
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.anchors import service as anchors
from tez.modules.library.paper_service import PaperService
from tez.modules.matrix import values
from tez.modules.matrix.models import CellOrigin, Matrix, MatrixCell, MatrixColumn
from tez.modules.matrix.repository import MatrixRepository
from tez.modules.matrix.schemas import (
    CellView,
    ColumnCreate,
    ColumnPatch,
    ColumnView,
    Coverage,
    EvidenceView,
    KeptCell,
    MatrixSummary,
    MatrixView,
    OptionIn,
    OptionView,
    PaperMatrix,
    RowView,
    TypeChange,
    TypeChangeReport,
)
from tez.modules.matrix.values import DataType, Option
from tez.modules.reviews import service as reviews
from tez.modules.reviews.models import ScreeningStage
from tez.modules.screening.service import RECONCILED, ScreeningService
from tez.shared.ids import new_id

CHOICES = (DataType.ENUM, DataType.MULTI_ENUM)
# How many cells a type change report names; the count covers them all.
KEPT_SHOWN = 50


# --- lookups --------------------------------------------------------------------------------


def _require_review(db: Database, review_id: str) -> None:
    if not reviews.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)


def _require_matrix(repository: MatrixRepository, matrix_id: str) -> Matrix:
    matrix = repository.get_matrix(matrix_id)
    if matrix is None:
        raise TezError(ErrorCode.MATRIX_NOT_FOUND, {"matrix_id": matrix_id}, status=404)
    return matrix


def _require_column(repository: MatrixRepository, matrix_id: str, column_id: str) -> MatrixColumn:
    column = repository.get_column(matrix_id, column_id)
    if column is None:
        raise TezError(ErrorCode.MATRIX_COLUMN_NOT_FOUND, {"column_id": column_id}, status=404)
    return column


def _included(session: Session, review_id: str) -> list[str]:
    return ScreeningService(session).included(review_id, ScreeningStage.FULL_TEXT, RECONCILED)


def _options(column: MatrixColumn) -> list[Option]:
    return [Option(id=str(o["id"]), label=str(o["label"])) for o in column.options_json]


def _new_options(given: Sequence[OptionIn], old: Sequence[Option]) -> list[Option]:
    """Options as the user wrote them: known ids are kept, new options get one."""
    known = {option["id"] for option in old}
    options: list[Option] = []
    for option in given:
        if option.id is not None and option.id not in known:
            raise TezError(ErrorCode.MATRIX_OPTION_UNKNOWN, {"option_id": option.id})
        options.append(Option(id=option.id or new_id(), label=option.label))
    return options


# --- views ----------------------------------------------------------------------------------


def _column_view(column: MatrixColumn) -> ColumnView:
    return ColumnView(
        id=column.id,
        name=column.name,
        instruction=column.instruction,
        data_type=column.data_type,
        options=[OptionView(id=o["id"], label=o["label"]) for o in _options(column)],
        sort_order=column.sort_order,
    )


def _cell_view(cell: MatrixCell, evidence: Sequence[EvidenceView] = ()) -> CellView:
    return CellView(
        column_id=cell.column_id,
        value=cell.value_json,
        kept_text=cell.value_text,
        origin=cell.origin,
        updated_at=cell.updated_at,
        evidence=list(evidence),
    )


def _cell_views(session: Session, cells: Sequence[MatrixCell]) -> dict[str, CellView]:
    """Cells with their evidence, by cell id."""
    links = MatrixRepository(session).evidence_of(cell.id for cell in cells)
    found = anchors.by_id(session, [a for ids in links.values() for a in ids])
    views: dict[str, CellView] = {}
    for cell in cells:
        evidence = [
            EvidenceView(
                anchor_id=anchor.id,
                attachment_id=anchor.attachment_id,
                page=anchor.page,
                quote=anchor.quote,
                status=anchor.status,
            )
            for anchor_id in links.get(cell.id, [])
            if (anchor := found.get(anchor_id)) is not None
        ]
        views[cell.id] = _cell_view(cell, evidence)
    return views


def _filled(cell: CellView) -> bool:
    return cell.value is not None or cell.kept_text is not None


def _coverage(rows: Sequence[RowView]) -> Coverage:
    filled = sourced = with_content = rows_sourced = 0
    for row in rows:
        if not row.included:
            continue
        cells = [cell for cell in row.cells if _filled(cell)]
        backed = sum(1 for cell in cells if cell.evidence)
        filled += len(cells)
        sourced += backed
        if cells:
            with_content += 1
            rows_sourced += backed == len(cells)
    return Coverage(filled=filled, sourced=sourced, rows=with_content, rows_sourced=rows_sourced)


def _summary(matrix: Matrix, columns: int) -> MatrixSummary:
    return MatrixSummary(
        id=matrix.id,
        review_id=matrix.review_id,
        name=matrix.name,
        columns=columns,
        created_at=matrix.created_at,
    )


def _matrix_view(session: Session, matrix: Matrix) -> MatrixView:
    repository = MatrixRepository(session)
    columns = repository.columns(matrix.id)
    included = _included(session, matrix.review_id)
    cells_of = repository.cells(matrix.id)
    views = _cell_views(session, [cell for cell, _ in cells_of])
    by_paper: dict[str, list[CellView]] = {}
    for cell, paper_id in cells_of:
        by_paper.setdefault(paper_id, []).append(views[cell.id])
    shown = set(included)
    hidden = [paper_id for paper_id in by_paper if paper_id not in shown]
    cards = PaperService(session).cards([*included, *hidden])
    order = {column.id: column.sort_order for column in columns}
    rows: list[RowView] = []
    for paper_id in [*included, *hidden]:
        card = cards.get(paper_id)
        if card is None:
            continue
        cells = sorted(by_paper.get(paper_id, []), key=lambda c: order.get(c.column_id, 0))
        rows.append(
            RowView(
                paper_id=paper_id,
                title=card.paper.title,
                year=card.paper.year,
                venue=card.paper.venue,
                first_author=card.first_author.display_name if card.first_author else None,
                author_count=card.author_count,
                reading_status=card.paper.reading_status,
                included=paper_id in shown,
                cells=cells,
            )
        )
    return MatrixView(
        id=matrix.id,
        review_id=matrix.review_id,
        name=matrix.name,
        columns=[_column_view(column) for column in columns],
        rows=rows,
        coverage=_coverage(rows),
    )


# --- matrices -------------------------------------------------------------------------------


def list_matrices(db: Database, review_id: str) -> list[MatrixSummary]:
    _require_review(db, review_id)
    with db.session() as session:
        repository = MatrixRepository(session)
        matrices = repository.matrices(review_id)
        counts = repository.column_counts(m.id for m in matrices)
        return [_summary(matrix, counts.get(matrix.id, 0)) for matrix in matrices]


def create_matrix(db: Database, review_id: str, name: str) -> MatrixView:
    _require_review(db, review_id)
    with db.write_session() as session:
        matrix = MatrixRepository(session).add_matrix(review_id, name)
        return _matrix_view(session, matrix)


def get_matrix(db: Database, matrix_id: str) -> MatrixView:
    with db.session() as session:
        matrix = _require_matrix(MatrixRepository(session), matrix_id)
        return _matrix_view(session, matrix)


def rename_matrix(db: Database, matrix_id: str, name: str) -> MatrixView:
    with db.write_session() as session:
        matrix = _require_matrix(MatrixRepository(session), matrix_id)
        matrix.name = name
        session.flush()
        return _matrix_view(session, matrix)


def delete_matrix(db: Database, matrix_id: str) -> None:
    """Delete a matrix with its columns and cells. The papers stay."""
    with db.write_session() as session:
        repository = MatrixRepository(session)
        repository.delete(_require_matrix(repository, matrix_id))


# --- columns --------------------------------------------------------------------------------


def add_column(db: Database, matrix_id: str, body: ColumnCreate) -> ColumnView:
    with db.write_session() as session:
        repository = MatrixRepository(session)
        _require_matrix(repository, matrix_id)
        options = _new_options(body.options, []) if body.data_type in CHOICES else []
        column = repository.add_column(
            MatrixColumn(
                matrix_id=matrix_id,
                name=body.name,
                instruction=body.instruction or None,
                data_type=body.data_type,
                options_json=[dict(o) for o in options],
            )
        )
        return _column_view(column)


def update_column(db: Database, matrix_id: str, column_id: str, body: ColumnPatch) -> ColumnView:
    with db.write_session() as session:
        column = _require_column(MatrixRepository(session), matrix_id, column_id)
        if body.name is not None:
            column.name = body.name
        if "instruction" in body.model_fields_set:
            column.instruction = body.instruction or None
        session.flush()
        return _column_view(column)


def delete_column(db: Database, matrix_id: str, column_id: str) -> None:
    """Delete a column and its cells: asked for by name, so not silent."""
    with db.write_session() as session:
        repository = MatrixRepository(session)
        repository.delete(_require_column(repository, matrix_id, column_id))


def reorder_columns(db: Database, matrix_id: str, column_ids: Sequence[str]) -> list[ColumnView]:
    """Put the columns in the given order; it must name each column exactly once."""
    with db.write_session() as session:
        repository = MatrixRepository(session)
        _require_matrix(repository, matrix_id)
        columns = {column.id: column for column in repository.columns(matrix_id)}
        if len(column_ids) != len(columns) or set(column_ids) != set(columns):
            raise TezError(ErrorCode.MATRIX_ORDER_MISMATCH)
        for position, column_id in enumerate(column_ids):
            columns[column_id].sort_order = position
        session.flush()
        return [_column_view(columns[column_id]) for column_id in column_ids]


def change_type(db: Database, matrix_id: str, column_id: str, body: TypeChange) -> TypeChangeReport:
    """Give a column a new type or new options and convert its cells.

    Every cell is written out as text and read back as the new type. A cell that cannot be
    read back keeps that text, marked, and is named in the report: nothing is lost without
    a word. With `dry_run` only the report is made.
    """
    words = values.Words(true=body.true_text, false=body.false_text)
    with db.write_session() as session:
        repository = MatrixRepository(session)
        column = _require_column(repository, matrix_id, column_id)
        old = (column.data_type, _options(column))
        cells = repository.column_cells(column.id)
        before = [values.Cell(cell.value_json, cell.value_text) for cell, _ in cells]
        options = _options_for_change(body, old, before, words)
        new = (body.data_type, options)
        after = [values.convert(cell, old, new, words) for cell in before]
        kept = [
            KeptCell(paper_id=paper_id, text=converted.kept_text)
            for (_, paper_id), converted in zip(cells, after, strict=True)
            if converted.kept_text is not None
        ]
        if not body.dry_run:
            column.data_type = body.data_type
            column.options_json = [dict(o) for o in options]
            linked = repository.evidence_of(cell.id for cell, _ in cells)
            for (cell, _), converted in zip(cells, after, strict=True):
                # An emptied cell goes, unless passages are linked to it.
                if (
                    converted.value is None
                    and converted.kept_text is None
                    and cell.id not in linked
                ):
                    repository.delete(cell)
                else:
                    cell.value_json = converted.value
                    cell.value_text = converted.kept_text
            session.flush()
        view = _column_view(column)
        if body.dry_run:
            view = view.model_copy(
                update={
                    "data_type": body.data_type,
                    "options": [OptionView(id=o["id"], label=o["label"]) for o in options],
                }
            )
        return TypeChangeReport(
            column=view,
            applied=not body.dry_run,
            cells=len(cells),
            converted=len(cells) - len(kept),
            kept=kept[:KEPT_SHOWN],
        )


def _options_for_change(
    body: TypeChange,
    old: tuple[DataType, list[Option]],
    cells: Sequence[values.Cell],
    words: values.Words,
) -> list[Option]:
    if body.data_type not in CHOICES:
        return []
    if body.options is not None:
        return _new_options(body.options, old[1])
    if old[0] in CHOICES:
        return old[1]
    # Not told which: the choices already written in the cells, in the order first met.
    texts = [
        cell.kept_text if cell.value is None else values.render(old[0], cell.value, old[1], words)
        for cell in cells
    ]
    multi = body.data_type == DataType.MULTI_ENUM
    labels = values.labels_in((t for t in texts if t), multi)
    return [Option(id=new_id(), label=label[:200]) for label in labels[:200]]


# --- cells ----------------------------------------------------------------------------------


def put_cell(
    db: Database,
    matrix_id: str,
    paper_id: str,
    column_id: str,
    value: Any,
    kept_text: str | None = None,
) -> CellView | None:
    """Set or clear a cell of an included paper. Returns None once it is empty.

    `kept_text` (with no value) puts back text a type change kept, so undoing an edit over
    such a cell loses nothing."""
    with db.write_session() as session:
        repository = MatrixRepository(session)
        matrix = _require_matrix(repository, matrix_id)
        column = _require_column(repository, matrix_id, column_id)
        if paper_id not in _included(session, matrix.review_id):
            raise TezError(ErrorCode.MATRIX_PAPER_NOT_INCLUDED, {"paper_id": paper_id}, status=409)
        try:
            stored = values.check(column.data_type, value, _options(column))
        except values.InvalidValue as error:
            raise TezError(
                ErrorCode.MATRIX_VALUE_INVALID,
                {"column_id": column_id, "data_type": column.data_type.value, "reason": str(error)},
            ) from error
        row = repository.row_for(
            matrix_id, paper_id, create=stored is not None or kept_text is not None
        )
        cell = row and repository.get_cell(row.id, column_id)
        if stored is None and kept_text is None:
            if cell is None:
                return None
            if not repository.evidence_of([cell.id]):
                repository.delete(cell)
                return None
        assert row is not None
        if cell is None:
            cell = repository.add_cell(MatrixCell(row_id=row.id, column_id=column_id))
        cell.value_json = stored
        cell.value_text = kept_text if stored is None else None
        cell.origin = CellOrigin.MANUAL
        session.flush()
        return _cell_views(session, [cell])[cell.id]


# --- evidence -------------------------------------------------------------------------------


def link_evidence(
    db: Database, matrix_id: str, paper_id: str, column_id: str, anchor_id: str, fill: bool
) -> CellView:
    """Link a passage of the paper's PDF to a cell. With `fill`, an empty text cell gets the
    passage as its value."""
    with db.write_session() as session:
        repository = MatrixRepository(session)
        matrix = _require_matrix(repository, matrix_id)
        column = _require_column(repository, matrix_id, column_id)
        if paper_id not in _included(session, matrix.review_id):
            raise TezError(ErrorCode.MATRIX_PAPER_NOT_INCLUDED, {"paper_id": paper_id}, status=409)
        anchor = anchors.by_id(session, [anchor_id]).get(anchor_id)
        if anchor is None:
            raise TezError(ErrorCode.ANCHOR_NOT_FOUND, {"anchor_id": anchor_id}, status=404)
        if anchor.paper.id != paper_id:
            raise TezError(ErrorCode.MATRIX_EVIDENCE_OTHER_PAPER, {"anchor_id": anchor_id})
        row = repository.row_for(matrix_id, paper_id, create=True)
        assert row is not None
        cell = repository.get_cell(row.id, column_id) or repository.add_cell(
            MatrixCell(row_id=row.id, column_id=column_id)
        )
        empty = cell.value_json is None and cell.value_text is None
        if fill and empty and column.data_type is DataType.TEXT:
            cell.value_json = anchor.quote.strip()[: values.MAX_TEXT] or None
        repository.add_evidence(cell.id, anchor_id)
        session.flush()
        return _cell_views(session, [cell])[cell.id]


def unlink_evidence(
    db: Database, matrix_id: str, paper_id: str, column_id: str, anchor_id: str
) -> CellView | None:
    """Take a passage off a cell. The passage stays (anchors are never deleted); a cell left
    with nothing goes. Returns None then."""
    with db.write_session() as session:
        repository = MatrixRepository(session)
        _require_matrix(repository, matrix_id)
        _require_column(repository, matrix_id, column_id)
        row = repository.row_for(matrix_id, paper_id, create=False)
        cell = row and repository.get_cell(row.id, column_id)
        evidence = cell and repository.get_evidence(cell.id, anchor_id)
        if cell is None or evidence is None:
            raise TezError(
                ErrorCode.MATRIX_EVIDENCE_NOT_FOUND, {"anchor_id": anchor_id}, status=404
            )
        repository.remove_evidence(evidence)
        empty = cell.value_json is None and cell.value_text is None
        if empty and not repository.evidence_of([cell.id]):
            repository.delete(cell)
            return None
        return _cell_views(session, [cell])[cell.id]


def paper_matrices(db: Database, paper_id: str) -> list[PaperMatrix]:
    """The matrices the paper is a row of (its review includes it at full text), with its
    cells: the reader's Matrix tab."""
    with db.session() as session:
        repository = MatrixRepository(session)
        found: list[PaperMatrix] = []
        included: dict[str, bool] = {}
        for matrix in repository.all_matrices():
            if matrix.review_id not in included:
                included[matrix.review_id] = paper_id in _included(session, matrix.review_id)
            if not included[matrix.review_id]:
                continue
            row = repository.row_for(matrix.id, paper_id, create=False)
            cells = [cell for cell, owner in repository.cells(matrix.id) if owner == paper_id]
            views = _cell_views(session, cells) if row else {}
            found.append(
                PaperMatrix(
                    matrix_id=matrix.id,
                    matrix_name=matrix.name,
                    review_id=matrix.review_id,
                    columns=[_column_view(c) for c in repository.columns(matrix.id)],
                    cells=list(views.values()),
                )
            )
        return found
