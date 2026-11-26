from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tez.modules.matrix.models import Matrix, MatrixCell, MatrixColumn, MatrixRow


class MatrixRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- matrices ------------------------------------------------------------------------

    def matrices(self, review_id: str) -> list[Matrix]:
        return list(
            self.session.scalars(
                select(Matrix)
                .where(Matrix.review_id == review_id)
                .order_by(Matrix.created_at, Matrix.id)
            )
        )

    def get_matrix(self, matrix_id: str) -> Matrix | None:
        return self.session.get(Matrix, matrix_id)

    def add_matrix(self, review_id: str, name: str) -> Matrix:
        matrix = Matrix(review_id=review_id, name=name)
        self.session.add(matrix)
        self.session.flush()
        return matrix

    def delete(self, row: Matrix | MatrixColumn | MatrixCell) -> None:
        self.session.delete(row)
        self.session.flush()

    # --- columns -------------------------------------------------------------------------

    def columns(self, matrix_id: str) -> list[MatrixColumn]:
        return list(
            self.session.scalars(
                select(MatrixColumn)
                .where(MatrixColumn.matrix_id == matrix_id)
                .order_by(MatrixColumn.sort_order, MatrixColumn.id)
            )
        )

    def column_counts(self, matrix_ids: Iterable[str]) -> dict[str, int]:
        found = self.session.execute(
            select(MatrixColumn.matrix_id, func.count())
            .where(MatrixColumn.matrix_id.in_(list(matrix_ids)))
            .group_by(MatrixColumn.matrix_id)
        )
        return {matrix_id: count for matrix_id, count in found}

    def get_column(self, matrix_id: str, column_id: str) -> MatrixColumn | None:
        column = self.session.get(MatrixColumn, column_id)
        return column if column is not None and column.matrix_id == matrix_id else None

    def add_column(self, column: MatrixColumn) -> MatrixColumn:
        """Append after the last column."""
        last = self.session.scalar(
            select(func.max(MatrixColumn.sort_order)).where(
                MatrixColumn.matrix_id == column.matrix_id
            )
        )
        column.sort_order = 0 if last is None else last + 1
        self.session.add(column)
        self.session.flush()
        return column

    # --- rows and cells ------------------------------------------------------------------

    def rows(self, matrix_id: str) -> list[MatrixRow]:
        return list(self.session.scalars(select(MatrixRow).where(MatrixRow.matrix_id == matrix_id)))

    def row_for(self, matrix_id: str, paper_id: str, *, create: bool) -> MatrixRow | None:
        row = self.session.scalars(
            select(MatrixRow).where(
                MatrixRow.matrix_id == matrix_id, MatrixRow.paper_id == paper_id
            )
        ).one_or_none()
        if row is None and create:
            row = MatrixRow(matrix_id=matrix_id, paper_id=paper_id)
            self.session.add(row)
            self.session.flush()
        return row

    def cells(self, matrix_id: str) -> list[tuple[MatrixCell, str]]:
        """Every cell of the matrix with its paper id."""
        found = self.session.execute(
            select(MatrixCell, MatrixRow.paper_id)
            .join(MatrixRow, MatrixCell.row_id == MatrixRow.id)
            .where(MatrixRow.matrix_id == matrix_id)
            .order_by(MatrixCell.id)
        )
        return [(cell, paper_id) for cell, paper_id in found]

    def column_cells(self, column_id: str) -> list[tuple[MatrixCell, str]]:
        found = self.session.execute(
            select(MatrixCell, MatrixRow.paper_id)
            .join(MatrixRow, MatrixCell.row_id == MatrixRow.id)
            .where(MatrixCell.column_id == column_id)
            .order_by(MatrixCell.id)
        )
        return [(cell, paper_id) for cell, paper_id in found]

    def get_cell(self, row_id: str, column_id: str) -> MatrixCell | None:
        return self.session.scalars(
            select(MatrixCell).where(MatrixCell.row_id == row_id, MatrixCell.column_id == column_id)
        ).one_or_none()

    def add_cell(self, cell: MatrixCell) -> MatrixCell:
        self.session.add(cell)
        self.session.flush()
        return cell
