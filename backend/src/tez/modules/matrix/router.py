from typing import Annotated

from fastapi import APIRouter, Depends, Response

from tez.modules.library.router import get_library
from tez.modules.library.service import Library
from tez.modules.matrix import service
from tez.modules.matrix.schemas import (
    CellPut,
    CellView,
    ColumnCreate,
    ColumnOrder,
    ColumnPatch,
    ColumnView,
    MatrixCreate,
    MatrixPatch,
    MatrixSummary,
    MatrixView,
    TypeChange,
    TypeChangeReport,
)

router = APIRouter(tags=["matrix"])

LibraryDep = Annotated[Library, Depends(get_library)]
_MATRIX = "/matrices/{matrix_id}"
_COLUMN = f"{_MATRIX}/columns/{{column_id}}"


@router.get("/reviews/{review_id}/matrices")
def list_matrices(review_id: str, library: LibraryDep) -> list[MatrixSummary]:
    return service.list_matrices(library.db, review_id)


@router.post("/reviews/{review_id}/matrices", status_code=201)
def create_matrix(review_id: str, body: MatrixCreate, library: LibraryDep) -> MatrixView:
    return service.create_matrix(library.db, review_id, body.name)


@router.get(_MATRIX)
def get_matrix(matrix_id: str, library: LibraryDep) -> MatrixView:
    """Columns and rows: the included papers, then excluded ones whose cells are kept."""
    return service.get_matrix(library.db, matrix_id)


@router.patch(_MATRIX)
def rename_matrix(matrix_id: str, body: MatrixPatch, library: LibraryDep) -> MatrixView:
    return service.rename_matrix(library.db, matrix_id, body.name)


@router.delete(_MATRIX, status_code=204)
def delete_matrix(matrix_id: str, library: LibraryDep) -> Response:
    service.delete_matrix(library.db, matrix_id)
    return Response(status_code=204)


@router.post(f"{_MATRIX}/columns", status_code=201)
def add_column(matrix_id: str, body: ColumnCreate, library: LibraryDep) -> ColumnView:
    return service.add_column(library.db, matrix_id, body)


@router.put(f"{_MATRIX}/columns/order")
def reorder_columns(matrix_id: str, body: ColumnOrder, library: LibraryDep) -> list[ColumnView]:
    return service.reorder_columns(library.db, matrix_id, body.column_ids)


@router.patch(_COLUMN)
def update_column(
    matrix_id: str, column_id: str, body: ColumnPatch, library: LibraryDep
) -> ColumnView:
    return service.update_column(library.db, matrix_id, column_id, body)


@router.put(f"{_COLUMN}/type")
def change_column_type(
    matrix_id: str, column_id: str, body: TypeChange, library: LibraryDep
) -> TypeChangeReport:
    """New type or options. Cells that cannot be converted keep their text, marked, and are
    listed; with `dry_run` nothing changes."""
    return service.change_type(library.db, matrix_id, column_id, body)


@router.delete(_COLUMN, status_code=204)
def delete_column(matrix_id: str, column_id: str, library: LibraryDep) -> Response:
    service.delete_column(library.db, matrix_id, column_id)
    return Response(status_code=204)


@router.put(f"{_MATRIX}/cells/{{paper_id}}/{{column_id}}")
def put_cell(
    matrix_id: str, paper_id: str, column_id: str, body: CellPut, library: LibraryDep
) -> CellView | None:
    """Set a cell; null clears it (the response is then null)."""
    return service.put_cell(library.db, matrix_id, paper_id, column_id, body.value, body.kept_text)
