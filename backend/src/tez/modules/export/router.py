from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.export import service
from tez.modules.export.schemas import BibliographyRequest, BibliographyResult, ExportResult
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


@router.post("/bibliography")
def formatted_bibliography(library: LibraryDep, body: BibliographyRequest) -> BibliographyResult:
    """A bibliography in a CSL style (APA 7, MLA, Chicago, Vancouver, IEEE), Turkish or
    English: chosen papers, a collection, a review's included studies, or the whole library."""
    return service.bibliography(
        library.db,
        body.style,
        body.locale,
        review_id=body.review_id,
        collection_id=body.collection_id,
        paper_ids=body.paper_ids,
    )
