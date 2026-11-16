"""Screening: the rules for writing decisions and the state derived from them (Task 31).

Decisions are append-only (CLAUDE.md rule 3). Every new decision for a record, stage and
reviewer supersedes that reviewer's current one, so each forms one chain; a correction is
simply a new decision, and undo is a new row that restores the state before the decision it
takes back (`undecided` when there was none, ADR 0022).

Derived state, never stored:
- The title-abstract queue is every record in the review, in a stable order.
- The full-text queue is the records whose current title-abstract decision is include or
  maybe, in the same order.
- A record's state at a stage is its current decision there, or undecided.

Other modules use `ScreeningService` inside their own session, or the functions below that
take a `Database`. Everything defaults to the library owner's decisions (`LOCAL_REVIEWER`);
two-reviewer screening (Tasks 41-42) passes another `reviewer`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy.orm import Session

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.library.models import IdentifierScheme
from tez.modules.library.paper_service import PaperService
from tez.modules.reviews.models import (
    CriterionKind,
    Decision,
    ScreeningDecision,
    ScreeningStage,
)
from tez.modules.reviews.service import ReviewReader
from tez.modules.screening.repository import Head, ScreeningRepository
from tez.modules.screening.schemas import (
    DecisionView,
    QueueFilter,
    QueueItem,
    RecordState,
    ScreeningQueue,
    ScreeningRecord,
    StateCounts,
)

# The person who owns the library. Imported decisions carry a colleague's name instead.
LOCAL_REVIEWER = "owner"

# Title-abstract decisions that send a record on to full-text screening.
FULL_TEXT_ENTRY = frozenset({Decision.INCLUDE, Decision.MAYBE})

_CRITERION_KIND = {
    Decision.INCLUDE: CriterionKind.INCLUSION,
    Decision.EXCLUDE: CriterionKind.EXCLUSION,
}


class Direction(StrEnum):
    NEXT = "next"
    PREVIOUS = "previous"


@dataclass(frozen=True)
class CurrentDecision:
    decision_id: str
    paper_id: str
    decision: Decision
    criterion_id: str | None
    note: str | None
    decided_at: datetime


@dataclass(frozen=True)
class QueueEntry:
    paper_id: str
    position: int  # 1-based
    state: RecordState
    head: Head | None  # None, or an `undecided` row left by undo, means undecided


def _state(head: Head | None) -> RecordState:
    if head is None or head.decision is Decision.UNDECIDED:
        return RecordState.UNDECIDED
    return RecordState(head.decision.value)


def _matches(entry: QueueEntry, wanted: QueueFilter) -> bool:
    return wanted is QueueFilter.ALL or entry.state.value == wanted.value


def decision_view(row: ScreeningDecision) -> DecisionView:
    return DecisionView(
        id=row.id,
        paper_id=row.paper_id,
        stage=row.stage,
        decision=row.decision,
        criterion_id=row.criterion_id,
        note=row.note,
        reviewer=row.reviewer,
        supersedes_id=row.supersedes_id,
        created_at=row.created_at,
    )


class ScreeningService:
    """Screening inside a caller's session; writes need a write session."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = ScreeningRepository(session)
        self._reviews = ReviewReader(session)

    # --- reading ----------------------------------------------------------------------

    def require_review(self, review_id: str) -> None:
        if not self._reviews.exists(review_id):
            raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)

    def current(
        self, review_id: str, stage: ScreeningStage, reviewer: str = LOCAL_REVIEWER
    ) -> dict[str, CurrentDecision]:
        """Decisions in force per paper. Undecided records (never decided, or undone) are
        absent. A full-text decision is returned even if the record has since left the
        full-text queue; use `entries` or `included` for what counts."""
        return {
            paper_id: CurrentDecision(
                head.id, paper_id, head.decision, head.criterion_id, head.note, head.created_at
            )
            for paper_id, head in self._repository.heads(review_id, stage, reviewer).items()
            if head.decision is not Decision.UNDECIDED
        }

    def queue(
        self, review_id: str, stage: ScreeningStage, reviewer: str = LOCAL_REVIEWER
    ) -> list[str]:
        """Paper ids to screen at the stage, in their stable order."""
        papers = self._reviews.record_paper_ids(review_id)
        if stage is ScreeningStage.TITLE_ABSTRACT:
            return papers
        title_abstract = self._repository.heads(review_id, ScreeningStage.TITLE_ABSTRACT, reviewer)
        return [
            paper_id
            for paper_id in papers
            if (head := title_abstract.get(paper_id)) is not None
            and head.decision in FULL_TEXT_ENTRY
        ]

    def entries(
        self, review_id: str, stage: ScreeningStage, reviewer: str = LOCAL_REVIEWER
    ) -> list[QueueEntry]:
        """The stage's queue with each record's derived state."""
        heads = self._repository.heads(review_id, stage, reviewer)
        return [
            QueueEntry(paper_id, position, _state(heads.get(paper_id)), heads.get(paper_id))
            for position, paper_id in enumerate(self.queue(review_id, stage, reviewer), start=1)
        ]

    def included(
        self, review_id: str, stage: ScreeningStage, reviewer: str = LOCAL_REVIEWER
    ) -> list[str]:
        """Papers included at the stage, in queue order. At full text this is the review's
        included studies."""
        return [
            entry.paper_id
            for entry in self.entries(review_id, stage, reviewer)
            if entry.state is RecordState.INCLUDE
        ]

    def history(self, review_id: str, paper_id: str) -> list[ScreeningDecision]:
        """Every decision on a record, both stages and all reviewers, oldest first."""
        return self._repository.history(review_id, paper_id)

    def reviewers(self, review_id: str) -> list[str]:
        """Reviewers who have decided anything in the review."""
        return self._repository.reviewers(review_id)

    # --- writing ----------------------------------------------------------------------

    def decide(
        self,
        review_id: str,
        paper_id: str,
        stage: ScreeningStage,
        decision: Decision,
        *,
        criterion_id: str | None = None,
        note: str | None = None,
        reviewer: str = LOCAL_REVIEWER,
    ) -> ScreeningDecision:
        """Record a decision; it supersedes the reviewer's current one for the record and
        stage. Deciding exactly what is already in force writes nothing."""
        self._check_record(review_id, paper_id)
        if decision is Decision.UNDECIDED or (
            decision is Decision.NOT_RETRIEVED and stage is not ScreeningStage.FULL_TEXT
        ):
            raise TezError(
                ErrorCode.SCREENING_INVALID_DECISION,
                {"decision": decision.value, "stage": stage.value},
            )
        if stage is ScreeningStage.FULL_TEXT:
            self._check_reached_full_text(review_id, paper_id, reviewer)
        self._check_criterion(review_id, stage, decision, criterion_id)

        head = self._repository.heads(review_id, stage, reviewer, paper_id).get(paper_id)
        if head is not None and (head.decision, head.criterion_id, head.note) == (
            decision,
            criterion_id,
            note,
        ):
            current = self._repository.get(head.id)
            assert current is not None
            return current
        return self._repository.add(
            review_id,
            paper_id,
            stage,
            decision,
            criterion_id=criterion_id,
            note=note,
            reviewer=reviewer,
            supersedes_id=head.id if head else None,
        )

    def undo(self, review_id: str, stage: ScreeningStage, decision_id: str) -> ScreeningDecision:
        """Take a decision back: restore the state before it, as a new row.

        The record must still be in the state that decision set; otherwise someone decided
        since, and undoing would throw that away (`screening.undo_stale`)."""
        target = self._repository.get(decision_id)
        if target is None or (target.review_id, target.stage) != (review_id, stage):
            raise TezError(
                ErrorCode.SCREENING_DECISION_NOT_FOUND, {"decision_id": decision_id}, status=404
            )
        head = self._repository.heads(review_id, stage, target.reviewer, target.paper_id).get(
            target.paper_id
        )
        assert head is not None  # the chain contains target, so it has a head
        if (head.decision, head.criterion_id, head.note) != (
            target.decision,
            target.criterion_id,
            target.note,
        ):
            raise TezError(ErrorCode.SCREENING_UNDO_STALE, {"decision_id": decision_id}, status=409)
        before = self._repository.get(target.supersedes_id) if target.supersedes_id else None
        return self._repository.add(
            review_id,
            target.paper_id,
            stage,
            before.decision if before else Decision.UNDECIDED,
            criterion_id=before.criterion_id if before else None,
            note=before.note if before else None,
            reviewer=target.reviewer,
            supersedes_id=head.id,
        )

    # --- rules ------------------------------------------------------------------------

    def _check_record(self, review_id: str, paper_id: str) -> None:
        self.require_review(review_id)
        if not self._reviews.has_record(review_id, paper_id):
            raise TezError(
                ErrorCode.SCREENING_RECORD_NOT_FOUND,
                {"review_id": review_id, "paper_id": paper_id},
                status=404,
            )

    def _check_reached_full_text(self, review_id: str, paper_id: str, reviewer: str) -> None:
        heads = self._repository.heads(review_id, ScreeningStage.TITLE_ABSTRACT, reviewer, paper_id)
        head = heads.get(paper_id)
        if head is None or head.decision not in FULL_TEXT_ENTRY:
            raise TezError(
                ErrorCode.SCREENING_STAGE_NOT_REACHED,
                {"paper_id": paper_id, "stage": ScreeningStage.FULL_TEXT.value},
                status=409,
            )

    def _check_criterion(
        self,
        review_id: str,
        stage: ScreeningStage,
        decision: Decision,
        criterion_id: str | None,
    ) -> None:
        if criterion_id is None:
            if decision is Decision.EXCLUDE:
                raise TezError(ErrorCode.SCREENING_REASON_REQUIRED)
            return
        criterion = self._reviews.usable_criterion(review_id, criterion_id, stage)
        fits = (
            criterion is not None
            and decision in _CRITERION_KIND
            and criterion.kind is _CRITERION_KIND[decision]
        )
        if not fits:
            raise TezError(
                ErrorCode.SCREENING_INVALID_CRITERION,
                {"criterion_id": criterion_id, "decision": decision.value, "stage": stage.value},
            )


# --- the API's view, one session per call ---------------------------------------------


def _counts(entries: Sequence[QueueEntry]) -> StateCounts:
    by_state = {state: 0 for state in RecordState}
    for entry in entries:
        by_state[entry.state] += 1
    return StateCounts(
        total=len(entries),
        undecided=by_state[RecordState.UNDECIDED],
        include=by_state[RecordState.INCLUDE],
        exclude=by_state[RecordState.EXCLUDE],
        maybe=by_state[RecordState.MAYBE],
        not_retrieved=by_state[RecordState.NOT_RETRIEVED],
    )


def queue_view(
    db: Database, review_id: str, stage: ScreeningStage, wanted: QueueFilter
) -> ScreeningQueue:
    with db.session() as session:
        screening = ScreeningService(session)
        screening.require_review(review_id)
        entries = screening.entries(review_id, stage)
        shown = [entry for entry in entries if _matches(entry, wanted)]
        cards = PaperService(session).cards(entry.paper_id for entry in shown)
        items: list[QueueItem] = []
        for entry in shown:
            card = cards[entry.paper_id]
            items.append(
                QueueItem(
                    paper_id=entry.paper_id,
                    position=entry.position,
                    state=entry.state,
                    decision_id=entry.head.id if entry.head else None,
                    criterion_id=entry.head.criterion_id if entry.head else None,
                    title=card.paper.title,
                    year=card.paper.year,
                    venue=card.paper.venue,
                    first_author=card.first_author.display_name if card.first_author else None,
                    author_count=card.author_count,
                )
            )
        return ScreeningQueue(stage=stage, counts=_counts(entries), items=items)


def _record(
    session: Session, entry: QueueEntry, total: int, stage: ScreeningStage
) -> ScreeningRecord:
    card = PaperService(session).cards([entry.paper_id])[entry.paper_id]
    paper = card.paper
    decision = None
    if entry.head is not None:
        row = ScreeningRepository(session).get(entry.head.id)
        assert row is not None
        decision = decision_view(row)
    return ScreeningRecord(
        paper_id=paper.id,
        position=entry.position,
        total=total,
        state=entry.state,
        decision=decision,
        title=paper.title,
        abstract=paper.abstract,
        authors=[link.author.display_name for link in paper.authors],
        year=paper.year,
        venue=paper.venue,
        doi=card.identifiers.get(IdentifierScheme.DOI),
        retraction_status=paper.retraction_status,
    )


def record_view(
    db: Database, review_id: str, stage: ScreeningStage, paper_id: str
) -> ScreeningRecord:
    with db.session() as session:
        screening = ScreeningService(session)
        screening.require_review(review_id)
        entries = screening.entries(review_id, stage)
        for entry in entries:
            if entry.paper_id == paper_id:
                return _record(session, entry, len(entries), stage)
        raise TezError(
            ErrorCode.SCREENING_RECORD_NOT_FOUND,
            {"review_id": review_id, "paper_id": paper_id, "stage": stage.value},
            status=404,
        )


def step(
    db: Database,
    review_id: str,
    stage: ScreeningStage,
    *,
    origin: str | None,
    direction: Direction,
    wanted: QueueFilter,
) -> ScreeningRecord | None:
    """The record after (or before) `origin` that matches the filter, wrapping around the
    queue; without an origin, the first (or last) one. None when nothing else matches."""
    with db.session() as session:
        screening = ScreeningService(session)
        screening.require_review(review_id)
        entries = screening.entries(review_id, stage)
        ordered = list(reversed(entries)) if direction is Direction.PREVIOUS else entries
        start = next((i for i, e in enumerate(ordered) if e.paper_id == origin), None)
        if start is not None:
            ordered = ordered[start + 1 :] + ordered[:start]
        found = next((entry for entry in ordered if _matches(entry, wanted)), None)
        return _record(session, found, len(entries), stage) if found else None


def decide(
    db: Database,
    review_id: str,
    stage: ScreeningStage,
    paper_id: str,
    decision: Decision,
    *,
    criterion_id: str | None,
    note: str | None,
) -> DecisionView:
    with db.write_session() as session:
        row = ScreeningService(session).decide(
            review_id, paper_id, stage, decision, criterion_id=criterion_id, note=note or None
        )
        return decision_view(row)


def undo(db: Database, review_id: str, stage: ScreeningStage, decision_id: str) -> DecisionView:
    with db.write_session() as session:
        screening = ScreeningService(session)
        screening.require_review(review_id)
        return decision_view(screening.undo(review_id, stage, decision_id))


def history(db: Database, review_id: str, paper_id: str) -> list[DecisionView]:
    with db.session() as session:
        screening = ScreeningService(session)
        screening.require_review(review_id)
        return [decision_view(row) for row in screening.history(review_id, paper_id)]
