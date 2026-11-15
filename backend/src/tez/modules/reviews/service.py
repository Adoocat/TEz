"""Reviews for the API and for other modules, which do not reach the repository directly."""

import re
from collections.abc import Iterable, Sequence

from sqlalchemy import select

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.library.paper_service import PaperService
from tez.modules.library.schemas import SelectionResult
from tez.modules.reviews.models import (
    Decision,
    RecordOrigin,
    Review,
    ScreeningStage,
)
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.reviews.schemas import ReviewCreate, ReviewOverview, ReviewView, StageProgress

_NUMBERED = re.compile(r"^\d+\.\s+")


def _questions_md(questions: Sequence[str]) -> str | None:
    """Research questions as a numbered Markdown list, one per line."""
    return "\n".join(f"{n}. {q}" for n, q in enumerate(questions, start=1)) or None


def _questions(markdown: str | None) -> list[str]:
    lines = (_NUMBERED.sub("", line).strip() for line in (markdown or "").splitlines())
    return [line for line in lines if line]


def _view(review: Review) -> ReviewView:
    return ReviewView(
        id=review.id,
        title=review.title,
        method=review.method,
        status=review.status,
        research_questions=_questions(review.research_questions_md),
        protocol=review.protocol_md,
        created_at=review.created_at,
    )


def _not_found(review_id: str) -> TezError:
    return TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)


def list_reviews(db: Database) -> list[ReviewView]:
    with db.session() as session:
        reviews = session.scalars(select(Review).order_by(Review.created_at, Review.id))
        return [_view(review) for review in reviews]


def create_review(db: Database, body: ReviewCreate) -> ReviewView:
    with db.write_session() as session:
        review = ReviewsRepository(session).add_review(
            body.title,
            method=body.method,
            research_questions_md=_questions_md(body.research_questions),
            protocol_md=body.protocol,
        )
        return _view(review)


def get_review(db: Database, review_id: str) -> ReviewView:
    with db.session() as session:
        review = ReviewsRepository(session).get_review(review_id)
        if review is None:
            raise _not_found(review_id)
        return _view(review)


def _progress(
    stage: ScreeningStage, eligible: set[str], decisions: dict[str, Decision]
) -> StageProgress:
    counted = [decision for paper_id, decision in decisions.items() if paper_id in eligible]
    return StageProgress(
        stage=stage,
        eligible=len(eligible),
        decided=len(counted),
        pending=len(eligible) - len(counted),
        included=counted.count(Decision.INCLUDE),
        excluded=counted.count(Decision.EXCLUDE),
        maybe=counted.count(Decision.MAYBE),
    )


def _in_force(
    repository: ReviewsRepository, review_id: str, stage: ScreeningStage
) -> dict[str, Decision]:
    # Oldest first, so a paper's latest decision in force wins.
    return {d.paper_id: d.decision for d in repository.current_decisions(review_id, stage)}


def _passed(decisions: dict[str, Decision], to_next: Iterable[Decision]) -> set[str]:
    wanted = set(to_next)
    return {paper_id for paper_id, decision in decisions.items() if decision in wanted}


def overview(db: Database, review_id: str) -> ReviewOverview:
    """The review panel's counts, derived from records and the decisions in force."""
    with db.session() as session:
        repository = ReviewsRepository(session)
        if repository.get_review(review_id) is None:
            raise _not_found(review_id)
        records = {record.paper_id for record in repository.records(review_id)}
        title_abstract = _in_force(repository, review_id, ScreeningStage.TITLE_ABSTRACT)
        full_text = _in_force(repository, review_id, ScreeningStage.FULL_TEXT)
    to_full_text = _passed(title_abstract, (Decision.INCLUDE, Decision.MAYBE))
    return ReviewOverview(
        review_id=review_id,
        records=len(records),
        stages=[
            _progress(ScreeningStage.TITLE_ABSTRACT, records, title_abstract),
            _progress(ScreeningStage.FULL_TEXT, to_full_text, full_text),
        ],
    )


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
            raise _not_found(review_id)
        wanted = set(paper_ids)
        if missing := wanted - PaperService(session).existing_ids(wanted):
            raise TezError(ErrorCode.PAPER_NOT_FOUND, {"paper_ids": sorted(missing)}, status=404)
        present = {record.paper_id for record in repository.records(review_id)}
        new = wanted - present
        for paper_id in sorted(new):
            repository.add_record(review_id, paper_id, RecordOrigin.DATABASE, search_id)
    return SelectionResult(added=len(new), already_present=len(wanted) - len(new))
