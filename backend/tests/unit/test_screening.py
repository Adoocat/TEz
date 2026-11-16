"""Task 31: screening rules and the derived state (service level).

Acceptance: the hard cases (undo, correction, trying to skip a stage, exclude without a
reason) and the stage queues; the API and the timing are in test_screening_api.py.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import func, select

from tez.core.errors import ErrorCode, TezError
from tez.modules.library.repository import LibraryRepository
from tez.modules.library.service import Library, open_library
from tez.modules.reviews.models import (
    CriterionKind,
    Decision,
    RecordOrigin,
    ReviewMethod,
    ScreeningDecision,
    ScreeningStage,
)
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.screening.schemas import RecordState
from tez.modules.screening.service import LOCAL_REVIEWER, ScreeningService

TA = ScreeningStage.TITLE_ABSTRACT
FT = ScreeningStage.FULL_TEXT


@dataclass
class World:
    library: Library
    review: str
    other_review: str
    a: str
    b: str
    outsider: str
    criteria: dict[str, str]  # code -> id; "X1" belongs to the other review

    def run[T](self, work: Callable[[ScreeningService], T]) -> T:
        with self.library.db.write_session() as session:
            return work(ScreeningService(session))

    def read[T](self, work: Callable[[ScreeningService], T]) -> T:
        with self.library.db.session() as session:
            return work(ScreeningService(session))

    def decide(
        self,
        stage: ScreeningStage,
        decision: Decision,
        criterion: str | None = None,
        *,
        paper: str | None = None,
        note: str | None = None,
        reviewer: str = LOCAL_REVIEWER,
    ) -> str:
        criterion_id = self.criteria[criterion] if criterion else None
        return self.run(
            lambda s: (
                s.decide(
                    self.review,
                    paper or self.a,
                    stage,
                    decision,
                    criterion_id=criterion_id,
                    note=note,
                    reviewer=reviewer,
                ).id
            )
        )

    def undo(self, stage: ScreeningStage, decision_id: str) -> str:
        return self.run(lambda s: s.undo(self.review, stage, decision_id).id)

    def state(self, stage: ScreeningStage, paper: str | None = None) -> RecordState | None:
        """The record's state, or None when it is not in the stage's queue."""
        entries = self.read(lambda s: s.entries(self.review, stage))
        return next((e.state for e in entries if e.paper_id == (paper or self.a)), None)

    def rows(self) -> int:
        with self.library.db.session() as session:
            return session.scalar(select(func.count()).select_from(ScreeningDecision)) or 0


@pytest.fixture
def world(tmp_path: Path) -> Iterator[World]:
    library = open_library(tmp_path / "lib", create=True)
    with library.db.write_session() as session:
        papers = LibraryRepository(session)
        a = papers.add_paper("Paper A").id
        b = papers.add_paper("Paper B").id
        outsider = papers.add_paper("Not in the review").id
        reviews = ReviewsRepository(session)
        review = reviews.add_review("SLR", method=ReviewMethod.PRISMA2020).id
        other = reviews.add_review("Other", method=ReviewMethod.PRISMA2020).id
        for paper in (a, b):
            reviews.add_record(review, paper, RecordOrigin.DATABASE)
        criteria = {
            "I1": reviews.add_criterion(review, CriterionKind.INCLUSION, "I1", "On topic").id,
            "E1": reviews.add_criterion(review, CriterionKind.EXCLUSION, "E1", "Off topic", TA).id,
            "E2": reviews.add_criterion(review, CriterionKind.EXCLUSION, "E2", "No data", FT).id,
            "E3": reviews.add_criterion(review, CriterionKind.EXCLUSION, "E3", "Not English").id,
            "X1": reviews.add_criterion(other, CriterionKind.EXCLUSION, "X1", "Elsewhere").id,
        }
    yield World(library, review, other, a, b, outsider, criteria)
    library.close()


def error_code(call: Callable[[], object]) -> ErrorCode:
    with pytest.raises(TezError) as caught:
        call()
    return caught.value.code


# --- hard cases: decisions that are refused and write nothing --------------------------


@pytest.mark.parametrize(
    ("setup", "stage", "decision", "criterion", "expected"),
    [
        # exclude without a reason
        ([], TA, Decision.EXCLUDE, None, ErrorCode.SCREENING_REASON_REQUIRED),
        # a reason that does not fit: wrong kind, wrong stage, another review's, not needed
        ([], TA, Decision.EXCLUDE, "I1", ErrorCode.SCREENING_INVALID_CRITERION),
        ([], TA, Decision.EXCLUDE, "E2", ErrorCode.SCREENING_INVALID_CRITERION),
        ([], TA, Decision.EXCLUDE, "X1", ErrorCode.SCREENING_INVALID_CRITERION),
        ([], TA, Decision.INCLUDE, "E1", ErrorCode.SCREENING_INVALID_CRITERION),
        ([], TA, Decision.MAYBE, "E3", ErrorCode.SCREENING_INVALID_CRITERION),
        # "not retrieved" is a full-text outcome; undecided is only written by undo
        ([], TA, Decision.NOT_RETRIEVED, None, ErrorCode.SCREENING_INVALID_DECISION),
        ([], TA, Decision.UNDECIDED, None, ErrorCode.SCREENING_INVALID_DECISION),
        # skipping a stage: full text before title-abstract sent the record there
        ([], FT, Decision.INCLUDE, None, ErrorCode.SCREENING_STAGE_NOT_REACHED),
        ([(TA, Decision.EXCLUDE, "E1")], FT, Decision.INCLUDE, None,
         ErrorCode.SCREENING_STAGE_NOT_REACHED),
        # a full-text-only reason at full text is fine, but exclude still needs one there
        ([(TA, Decision.INCLUDE, None)], FT, Decision.EXCLUDE, None,
         ErrorCode.SCREENING_REASON_REQUIRED),
        ([(TA, Decision.INCLUDE, None)], FT, Decision.EXCLUDE, "E1",
         ErrorCode.SCREENING_INVALID_CRITERION),
    ],
)  # fmt: skip
def test_a_refused_decision_writes_nothing(
    world: World,
    setup: list[tuple[ScreeningStage, Decision, str | None]],
    stage: ScreeningStage,
    decision: Decision,
    criterion: str | None,
    expected: ErrorCode,
) -> None:
    for step in setup:
        world.decide(*step)
    before = world.rows()

    assert error_code(lambda: world.decide(stage, decision, criterion)) is expected
    assert world.rows() == before


def test_only_records_in_the_review_can_be_decided(world: World) -> None:
    code = error_code(lambda: world.decide(TA, Decision.INCLUDE, paper=world.outsider))
    assert code is ErrorCode.SCREENING_RECORD_NOT_FOUND


def test_an_unknown_review_is_not_found(world: World) -> None:
    def decide(s: ScreeningService) -> object:
        return s.decide("nope", world.a, TA, Decision.INCLUDE)

    assert error_code(lambda: world.run(decide)) is ErrorCode.REVIEW_NOT_FOUND


# --- hard cases: corrections and undo are new rows -------------------------------------


def test_a_correction_is_a_new_row_that_supersedes_the_last(world: World) -> None:
    first = world.decide(TA, Decision.INCLUDE)
    second = world.decide(TA, Decision.EXCLUDE, "E1")

    history = world.read(lambda s: s.history(world.review, world.a))
    assert [(row.id, row.decision, row.supersedes_id) for row in history] == [
        (first, Decision.INCLUDE, None),
        (second, Decision.EXCLUDE, first),
    ]
    assert world.state(TA) is RecordState.EXCLUDE


def test_deciding_what_is_already_in_force_writes_nothing(world: World) -> None:
    first = world.decide(TA, Decision.EXCLUDE, "E1", note="survey")
    again = world.decide(TA, Decision.EXCLUDE, "E1", note="survey")
    other_note = world.decide(TA, Decision.EXCLUDE, "E1", note="a survey paper")

    assert again == first
    assert other_note != first
    assert world.rows() == 2


def test_undoing_the_first_decision_leaves_the_record_undecided(world: World) -> None:
    first = world.decide(TA, Decision.INCLUDE)
    undone = world.undo(TA, first)

    history = world.read(lambda s: s.history(world.review, world.a))
    assert [(row.id, row.decision, row.supersedes_id) for row in history] == [
        (first, Decision.INCLUDE, None),
        (undone, Decision.UNDECIDED, first),
    ]
    assert world.state(TA) is RecordState.UNDECIDED
    assert world.read(lambda s: s.current(world.review, TA)) == {}


def test_undoing_a_correction_restores_the_decision_before_it(world: World) -> None:
    world.decide(TA, Decision.INCLUDE, "I1", note="core")
    correction = world.decide(TA, Decision.EXCLUDE, "E1")

    world.undo(TA, correction)

    current = world.read(lambda s: s.current(world.review, TA))[world.a]
    assert (current.decision, current.criterion_id, current.note) == (
        Decision.INCLUDE,
        world.criteria["I1"],
        "core",
    )


def test_undo_walks_back_one_decision_at_a_time(world: World) -> None:
    first = world.decide(TA, Decision.INCLUDE)
    second = world.decide(TA, Decision.EXCLUDE, "E1")

    world.undo(TA, second)
    assert world.state(TA) is RecordState.INCLUDE
    world.undo(TA, first)
    assert world.state(TA) is RecordState.UNDECIDED
    assert world.rows() == 4


def test_undoing_a_decision_that_was_since_replaced_is_refused(world: World) -> None:
    first = world.decide(TA, Decision.INCLUDE)
    world.decide(TA, Decision.MAYBE)
    before = world.rows()

    assert error_code(lambda: world.undo(TA, first)) is ErrorCode.SCREENING_UNDO_STALE
    assert world.rows() == before


def test_undo_needs_a_decision_of_this_review_and_stage(world: World) -> None:
    decision = world.decide(TA, Decision.INCLUDE)

    assert error_code(lambda: world.undo(FT, decision)) is ErrorCode.SCREENING_DECISION_NOT_FOUND
    assert error_code(lambda: world.undo(TA, "missing")) is ErrorCode.SCREENING_DECISION_NOT_FOUND


def test_after_undo_the_record_can_be_decided_again(world: World) -> None:
    world.undo(TA, world.decide(TA, Decision.INCLUDE))
    world.decide(TA, Decision.MAYBE)

    assert world.state(TA) is RecordState.MAYBE


# --- stages and the derived queues -----------------------------------------------------


def test_title_abstract_include_and_maybe_move_on_to_full_text(world: World) -> None:
    assert world.read(lambda s: s.queue(world.review, FT)) == []

    world.decide(TA, Decision.MAYBE, paper=world.b)
    world.decide(TA, Decision.INCLUDE, paper=world.a)

    # The order is the review's, not the order of the decisions.
    assert world.read(lambda s: s.queue(world.review, FT)) == [world.a, world.b]
    assert world.state(FT) is RecordState.UNDECIDED


def test_full_text_outcomes_and_the_included_studies(world: World) -> None:
    world.decide(TA, Decision.INCLUDE, paper=world.a)
    world.decide(TA, Decision.INCLUDE, paper=world.b)
    world.decide(FT, Decision.INCLUDE, "I1", paper=world.a)
    world.decide(FT, Decision.NOT_RETRIEVED, paper=world.b)

    assert world.read(lambda s: s.included(world.review, FT)) == [world.a]
    assert world.state(FT, world.b) is RecordState.NOT_RETRIEVED


def test_a_title_abstract_correction_takes_the_record_out_of_full_text(world: World) -> None:
    world.decide(TA, Decision.INCLUDE)
    world.decide(FT, Decision.INCLUDE)
    assert world.read(lambda s: s.included(world.review, FT)) == [world.a]

    world.decide(TA, Decision.EXCLUDE, "E1")

    assert world.read(lambda s: s.queue(world.review, FT)) == []
    assert world.read(lambda s: s.included(world.review, FT)) == []
    # Nothing was deleted: the full-text decision is still in the history.
    assert len(world.read(lambda s: s.history(world.review, world.a))) == 3


def test_the_queue_order_is_stable_whatever_is_decided(world: World) -> None:
    order = world.read(lambda s: s.queue(world.review, TA))
    world.decide(TA, Decision.EXCLUDE, "E3", paper=world.b)
    world.decide(TA, Decision.INCLUDE, paper=world.a)

    assert world.read(lambda s: s.queue(world.review, TA)) == order == [world.a, world.b]


def test_each_reviewer_has_their_own_chain_and_queue(world: World) -> None:
    world.decide(TA, Decision.INCLUDE, reviewer="ayse")
    world.decide(TA, Decision.EXCLUDE, "E1")

    # The colleague's include does not open full text for the owner, but does for her.
    assert world.read(lambda s: s.queue(world.review, FT)) == []
    assert world.read(lambda s: s.queue(world.review, FT, "ayse")) == [world.a]
    world.decide(FT, Decision.INCLUDE, reviewer="ayse")

    history = world.read(lambda s: s.history(world.review, world.a))
    assert all(row.supersedes_id is None for row in history[:2])
    assert world.read(lambda s: s.reviewers(world.review)) == ["ayse", LOCAL_REVIEWER]
    assert world.read(lambda s: s.current(world.review, TA, "ayse"))[world.a].decision is (
        Decision.INCLUDE
    )
