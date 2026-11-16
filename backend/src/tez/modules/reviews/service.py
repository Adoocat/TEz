"""Reviews for the API and for other modules, which do not reach the repository directly."""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from tez.core.db import Database, utcnow
from tez.core.errors import ErrorCode, TezError
from tez.modules.library.paper_service import PaperService
from tez.modules.library.schemas import SelectionResult
from tez.modules.reviews.models import (
    CriterionKind,
    Decision,
    RecordOrigin,
    Review,
    ReviewRecord,
    ScreeningCriterion,
    ScreeningStage,
)
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.reviews.schemas import (
    CriteriaOrder,
    CriterionCreate,
    CriterionShortcuts,
    CriterionUpdate,
    CriterionView,
    ReviewCreate,
    ReviewOverview,
    ReviewView,
    StageCriterion,
    StageProgress,
)
from tez.shared.text import fold

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
    # Oldest first, so a paper's latest decision in force wins. Only the owner's decisions
    # count, and an undo that left a record undecided is no decision (Task 31).
    return {
        d.paper_id: d.decision
        for d in repository.current_decisions(review_id, stage)
        if d.reviewer == "owner" and d.decision is not Decision.UNDECIDED
    }


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
    db: Database,
    review_id: str,
    paper_ids: Sequence[str],
    search_id: str | None,
    *,
    origin: RecordOrigin = RecordOrigin.DATABASE,
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
            repository.add_record(review_id, paper_id, origin, search_id)
    return SelectionResult(added=len(new), already_present=len(wanted) - len(new))


# --- screening criteria (Task 25) ------------------------------------------------------

SHORTCUT_KEYS = 9
_CODE_PREFIX = {CriterionKind.INCLUSION: "I", CriterionKind.EXCLUSION: "E"}


def _review_repository(session: Session, review_id: str) -> ReviewsRepository:
    repository = ReviewsRepository(session)
    if repository.get_review(review_id) is None:
        raise _not_found(review_id)
    return repository


def _criterion(
    repository: ReviewsRepository, review_id: str, criterion_id: str
) -> ScreeningCriterion:
    criterion = repository.get_criterion(review_id, criterion_id)
    if criterion is None:
        raise TezError(
            ErrorCode.SCREENING_CRITERION_NOT_FOUND, {"criterion_id": criterion_id}, status=404
        )
    return criterion


def _in_stage(criterion: ScreeningCriterion, stage: ScreeningStage) -> bool:
    return criterion.archived_at is None and criterion.stage in (None, stage)


def _shortcuts(criteria: Sequence[ScreeningCriterion], stage: ScreeningStage) -> dict[str, int]:
    """A stage's 1-9 keys: its active criteria in order, the first nine of them."""
    shown = [criterion.id for criterion in criteria if _in_stage(criterion, stage)]
    return {criterion_id: n for n, criterion_id in enumerate(shown[:SHORTCUT_KEYS], start=1)}


def _criterion_views(repository: ReviewsRepository, review_id: str) -> list[CriterionView]:
    criteria = repository.criteria(review_id)
    used = repository.used_criterion_ids(review_id)
    title_abstract = _shortcuts(criteria, ScreeningStage.TITLE_ABSTRACT)
    full_text = _shortcuts(criteria, ScreeningStage.FULL_TEXT)
    return [
        CriterionView(
            id=criterion.id,
            kind=criterion.kind,
            code=criterion.code,
            text=criterion.text,
            stage=criterion.stage,
            position=criterion.position,
            archived=criterion.archived_at is not None,
            used=criterion.id in used,
            shortcuts=CriterionShortcuts(
                title_abstract=title_abstract.get(criterion.id),
                full_text=full_text.get(criterion.id),
            ),
            keywords=list(criterion.keywords),
        )
        for criterion in criteria
    ]


def _view_of(views: list[CriterionView], criterion_id: str) -> CriterionView:
    return next(view for view in views if view.id == criterion_id)


def list_criteria(db: Database, review_id: str) -> list[CriterionView]:
    """All criteria of a review: active ones in order, then archived ones."""
    with db.session() as session:
        return _criterion_views(_review_repository(session, review_id), review_id)


def criteria_for_stage(db: Database, review_id: str, stage: ScreeningStage) -> list[StageCriterion]:
    """The active criteria a stage's screening shows, in key order (the first nine: 1-9)."""
    with db.session() as session:
        criteria = _review_repository(session, review_id).criteria(review_id)
        keys = _shortcuts(criteria, stage)
        return [
            StageCriterion(
                id=criterion.id,
                kind=criterion.kind,
                code=criterion.code,
                text=criterion.text,
                shortcut=keys.get(criterion.id),
                keywords=list(criterion.keywords),
            )
            for criterion in criteria
            if _in_stage(criterion, stage)
        ]


def _next_code(repository: ReviewsRepository, review_id: str, kind: CriterionKind) -> str:
    prefix = _CODE_PREFIX[kind]
    numbers = [
        int(criterion.code[len(prefix) :])
        for criterion in repository.criteria(review_id)
        if criterion.code.startswith(prefix) and criterion.code[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1}"


def _check_code(
    repository: ReviewsRepository, review_id: str, code: str, other_than: str | None = None
) -> None:
    if repository.code_taken(review_id, code, other_than=other_than):
        raise TezError(ErrorCode.SCREENING_CRITERION_CODE_TAKEN, {"code": code}, status=409)


def _in_use(criterion_id: str) -> TezError:
    return TezError(
        ErrorCode.SCREENING_CRITERION_IN_USE, {"criterion_id": criterion_id}, status=409
    )


def add_criterion(db: Database, review_id: str, body: CriterionCreate) -> CriterionView:
    with db.write_session() as session:
        repository = _review_repository(session, review_id)
        code = body.code or _next_code(repository, review_id, body.kind)
        _check_code(repository, review_id, code)
        criterion = repository.add_criterion(
            review_id, body.kind, code, body.text, body.stage, _distinct(body.keywords)
        )
        return _view_of(_criterion_views(repository, review_id), criterion.id)


def _distinct(keywords: Sequence[str]) -> list[str]:
    """Keywords once each, as first written; "Işık" and "ışık" are the same term."""
    seen: set[str] = set()
    kept: list[str] = []
    for keyword in keywords:
        if (key := fold(keyword)) not in seen:
            seen.add(key)
            kept.append(keyword)
    return kept


def _end_of_active(repository: ReviewsRepository, review_id: str) -> int:
    active = [c.position for c in repository.criteria(review_id) if c.archived_at is None]
    return max(active, default=-1) + 1


def update_criterion(
    db: Database, review_id: str, criterion_id: str, body: CriterionUpdate
) -> CriterionView:
    with db.write_session() as session:
        repository = _review_repository(session, review_id)
        criterion = _criterion(repository, review_id, criterion_id)
        if body.kind is not None and body.kind != criterion.kind:
            # The decisions citing it would change meaning (an exclusion reason that includes).
            if criterion_id in repository.used_criterion_ids(review_id):
                raise _in_use(criterion_id)
            criterion.kind = body.kind
        if body.code is not None and body.code != criterion.code:
            _check_code(repository, review_id, body.code, other_than=criterion_id)
            criterion.code = body.code
        if body.text is not None:
            criterion.text = body.text
        if "stage" in body.model_fields_set:
            criterion.stage = body.stage
        if body.keywords is not None:
            criterion.keywords = _distinct(body.keywords)
        if body.archived is not None and body.archived != (criterion.archived_at is not None):
            if body.archived:
                criterion.archived_at = utcnow()
            else:
                # Back after the active ones.
                criterion.position = _end_of_active(repository, review_id)
                criterion.archived_at = None
        session.flush()
        return _view_of(_criterion_views(repository, review_id), criterion_id)


def delete_criterion(db: Database, review_id: str, criterion_id: str) -> None:
    """Delete a criterion no decision cites; a cited one is archived instead."""
    with db.write_session() as session:
        repository = _review_repository(session, review_id)
        criterion = _criterion(repository, review_id, criterion_id)
        if criterion_id in repository.used_criterion_ids(review_id):
            raise _in_use(criterion_id)
        repository.delete_criterion(criterion)


def reorder_criteria(db: Database, review_id: str, body: CriteriaOrder) -> list[CriterionView]:
    """Put the active criteria in the given order; archived ones stay after them."""
    with db.write_session() as session:
        repository = _review_repository(session, review_id)
        criteria = repository.criteria(review_id)
        active = {c.id: c for c in criteria if c.archived_at is None}
        wanted = body.criterion_ids
        if len(wanted) != len(set(wanted)) or set(wanted) != set(active):
            raise TezError(
                ErrorCode.SCREENING_CRITERIA_ORDER_MISMATCH,
                {"criterion_ids": wanted},
                status=422,
            )
        archived = [c for c in criteria if c.archived_at is not None]
        for position, criterion in enumerate([*(active[i] for i in wanted), *archived]):
            criterion.position = position
        session.flush()
        return _criterion_views(repository, review_id)


# --- reads for screening (Task 31) -----------------------------------------------------


class ReviewReader:
    """Reads the screening module needs inside its own session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = ReviewsRepository(session)

    def exists(self, review_id: str) -> bool:
        return self._repository.get_review(review_id) is not None

    def record_paper_ids(self, review_id: str) -> list[str]:
        """The review's papers in a stable order: when they were taken in, then by id."""
        return list(
            self._session.scalars(
                select(ReviewRecord.paper_id)
                .where(ReviewRecord.review_id == review_id)
                .order_by(ReviewRecord.created_at, ReviewRecord.id)
            )
        )

    def has_record(self, review_id: str, paper_id: str) -> bool:
        found = self._session.scalar(
            select(ReviewRecord.id).where(
                ReviewRecord.review_id == review_id, ReviewRecord.paper_id == paper_id
            )
        )
        return found is not None

    def usable_criterion(
        self, review_id: str, criterion_id: str, stage: ScreeningStage
    ) -> ScreeningCriterion | None:
        """A criterion a new decision at the stage may cite: this review's, not archived."""
        criterion = self._repository.get_criterion(review_id, criterion_id)
        return criterion if criterion is not None and _in_stage(criterion, stage) else None


@dataclass(frozen=True)
class RecordFacts:
    paper_id: str
    origin: RecordOrigin
    origin_ref: str | None


def records(db: Database, review_id: str) -> list[RecordFacts]:
    """The papers taken into a review and how each got there, oldest first."""
    with db.session() as session:
        return [
            RecordFacts(record.paper_id, record.origin, record.origin_ref)
            for record in ReviewsRepository(session).records(review_id)
        ]


def add_found(
    db: Database, review_id: str, found: Sequence[tuple[str, str]], origin: RecordOrigin
) -> int:
    """Take in papers another method found, each with what led to it (`origin_ref`).

    A paper already in the review keeps its first origin; the first of repeats wins.
    Returns how many were new.
    """
    with db.write_session() as session:
        repository = ReviewsRepository(session)
        present = {record.paper_id for record in repository.records(review_id)}
        added = 0
        for paper_id, origin_ref in found:
            if paper_id in present:
                continue
            repository.add_record(review_id, paper_id, origin, origin_ref)
            present.add(paper_id)
            added += 1
    return added


# --- PRISMA diagram labels (Task 35) --------------------------------------------------------


def prisma_labels(db: Database, review_id: str) -> dict[str, str]:
    with db.session() as session:
        review = ReviewsRepository(session).get_review(review_id)
        if review is None:
            raise _not_found(review_id)
        return dict(review.prisma_labels)


def set_prisma_labels(db: Database, review_id: str, labels: dict[str, str]) -> dict[str, str]:
    """Replace the edited titles; a box left out shows its default title again."""
    with db.write_session() as session:
        review = ReviewsRepository(session).get_review(review_id)
        if review is None:
            raise _not_found(review_id)
        review.prisma_labels = dict(labels)
        return dict(review.prisma_labels)
