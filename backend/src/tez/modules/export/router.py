from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.export import service
from tez.modules.export.schemas import ExportResult
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

router = APIRouter(prefix="/export", tags=["export"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.get("")
def export_references(
    library: LibraryDep,
    format: service.ExportFormat = service.ExportFormat.BIBTEX,
    review_id: str | None = None,
    collection_id: str | None = None,
) -> ExportResult:
    """References as BibTeX or RIS: a review's papers, a collection, or the whole library."""
    return service.export(library.db, format, review_id=review_id, collection_id=collection_id)
