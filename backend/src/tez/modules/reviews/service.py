"""Reviews for the API and for other modules, which do not reach the repository directly."""

from collections.abc import Sequence

from sqlalchemy import select

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.library.paper_service import PaperService
from tez.modules.library.schemas import SelectionResult
from tez.modules.reviews.models import RecordOrigin, Review, ReviewMethod
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.reviews.schemas import ReviewView


def _view(review: Review) -> ReviewView:
    return ReviewView(
        id=review.id,
        title=review.title,
        method=review.method,
        status=review.status,
        created_at=review.created_at,
    )


def list_reviews(db: Database) -> list[ReviewView]:
    with db.session() as session:
        reviews = session.scalars(select(Review).order_by(Review.created_at, Review.id))
        return [_view(review) for review in reviews]


def create_review(db: Database, title: str, method: ReviewMethod) -> ReviewView:
    with db.write_session() as session:
        return _view(ReviewsRepository(session).add_review(title, method=method))


def review_exists(db: Database, review_id: str) -> bool:
    with db.session() as session:
        return ReviewsRepository(session).get_review(review_id) is not None


def paper_ids_in_review(db: Database, review_id: str) -> set[str]:
    with db.session() as session:
        return {record.paper_id for record in ReviewsRepository(session).records(review_id)}


def add_papers(
    db: Database, review_id: str, paper_ids: Sequence[str], search_id: str | None
) -> SelectionResult:
    """Take papers into a review, as found by a database search. Repeats change nothing."""
    with db.write_session() as session:
        repository = ReviewsRepository(session)
        if repository.get_review(review_id) is None:
            raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
        wanted = set(paper_ids)
        if missing := wanted - PaperService(session).existing_ids(wanted):
            raise TezError(ErrorCode.PAPER_NOT_FOUND, {"paper_ids": sorted(missing)}, status=404)
        present = {record.paper_id for record in repository.records(review_id)}
        new = wanted - present
        for paper_id in sorted(new):
            repository.add_record(review_id, paper_id, RecordOrigin.DATABASE, search_id)
    return SelectionResult(added=len(new), already_present=len(wanted) - len(new))
