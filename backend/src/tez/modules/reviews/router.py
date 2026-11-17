from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.library.router import get_library
from tez.modules.library.schemas import PaperSelection, SelectionResult
from tez.modules.library.service import Library
from tez.modules.reviews import service
from tez.modules.reviews.schemas import (
    CriteriaOrder,
    CriterionCreate,
    CriterionUpdate,
    CriterionView,
    ReviewCreate,
    ReviewOverview,
    ReviewView,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.get("")
def list_reviews(library: LibraryDep, deleted: bool = False) -> list[ReviewView]:
    """The reviews in use; `deleted=true` lists those in the trash."""
    return service.list_reviews(library.db, deleted=deleted)


@router.post("", status_code=201)
def create_review(body: ReviewCreate, library: LibraryDep) -> ReviewView:
    return service.create_review(library.db, body)


@router.get("/{review_id}")
def get_review(review_id: str, library: LibraryDep) -> ReviewView:
    return service.get_review(library.db, review_id)


@router.delete("/{review_id}", status_code=204)
def delete_review(review_id: str, library: LibraryDep) -> None:
    """Move the review to the trash; nothing recorded under it is removed."""
    service.delete_review(library.db, review_id)


@router.post("/{review_id}/restore")
def restore_review(review_id: str, library: LibraryDep) -> ReviewView:
    return service.restore_review(library.db, review_id)


@router.get("/{review_id}/overview")
def get_overview(review_id: str, library: LibraryDep) -> ReviewOverview:
    """The review panel's counts per screening stage, derived on every read."""
    return service.overview(library.db, review_id)


@router.post("/{review_id}/records")
def add_records(review_id: str, body: PaperSelection, library: LibraryDep) -> SelectionResult:
    """Take papers into the review. Adding one twice changes nothing."""
    return service.add_papers(library.db, review_id, body.paper_ids, body.search_id)


@router.get("/{review_id}/criteria")
def list_criteria(review_id: str, library: LibraryDep) -> list[CriterionView]:
    """Screening criteria: active ones in order (with their 1-9 keys), then archived ones."""
    return service.list_criteria(library.db, review_id)


@router.post("/{review_id}/criteria", status_code=201)
def add_criterion(review_id: str, body: CriterionCreate, library: LibraryDep) -> CriterionView:
    return service.add_criterion(library.db, review_id, body)


@router.put("/{review_id}/criteria/order")
def reorder_criteria(
    review_id: str, body: CriteriaOrder, library: LibraryDep
) -> list[CriterionView]:
    """Reorder the active criteria; the 1-9 keys follow the new order."""
    return service.reorder_criteria(library.db, review_id, body)


@router.patch("/{review_id}/criteria/{criterion_id}")
def update_criterion(
    review_id: str, criterion_id: str, body: CriterionUpdate, library: LibraryDep
) -> CriterionView:
    """Edit or (un)archive a criterion. A cited criterion keeps its kind."""
    return service.update_criterion(library.db, review_id, criterion_id, body)


@router.delete("/{review_id}/criteria/{criterion_id}", status_code=204)
def delete_criterion(review_id: str, criterion_id: str, library: LibraryDep) -> None:
    """Delete an unused criterion; a used one answers screening.criterion_in_use."""
    service.delete_criterion(library.db, review_id, criterion_id)
