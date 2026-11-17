from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.export import service
from tez.modules.export.schemas import (
    BibliographyRequest,
    BibliographyResult,
    ExportRequest,
    ExportResult,
    SearchStrategy,
)
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

router = APIRouter(prefix="/export", tags=["export"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.get("")
def export_references(
    library: LibraryDep,
    format: service.ExportFormat = service.ExportFormat.BIBTEX,
    review_id: str | None = None,
    included: bool = False,
    collection_id: str | None = None,
) -> ExportResult:
    """References as BibTeX or RIS: a review's papers (or only its included studies), a
    collection, or the whole library."""
    return service.export(
        library.db,
        format,
        review_id=review_id,
        included_only=included,
        collection_id=collection_id,
    )


@router.post("/references")
def export_chosen_references(library: LibraryDep, body: ExportRequest) -> ExportResult:
    """BibTeX or RIS for any scope, chosen papers included (too many ids for a URL)."""
    return service.export(
        library.db,
        service.ExportFormat(body.format),
        review_id=body.review_id,
        included_only=body.included,
        collection_id=body.collection_id,
        paper_ids=body.paper_ids,
    )


@router.get("/search-strategy")
def search_strategy(library: LibraryDep, review_id: str) -> SearchStrategy:
    """The review's searches for the methods chapter: source, date, exact query and result
    count, one row per search run."""
    return service.search_strategy(library.db, review_id)


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
