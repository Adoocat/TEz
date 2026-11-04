from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.library.router import get_library
from tez.modules.library.schemas import PaperSelection, SelectionResult
from tez.modules.library.service import Library
from tez.modules.reviews import service
from tez.modules.reviews.schemas import ReviewCreate, ReviewView

router = APIRouter(prefix="/reviews", tags=["reviews"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.get("")
def list_reviews(library: LibraryDep) -> list[ReviewView]:
    return service.list_reviews(library.db)


@router.post("", status_code=201)
def create_review(body: ReviewCreate, library: LibraryDep) -> ReviewView:
    return service.create_review(library.db, body.title, body.method)


@router.post("/{review_id}/records")
def add_records(review_id: str, body: PaperSelection, library: LibraryDep) -> SelectionResult:
    """Take papers into the review. Adding one twice changes nothing."""
    return service.add_papers(library.db, review_id, body.paper_ids, body.search_id)
