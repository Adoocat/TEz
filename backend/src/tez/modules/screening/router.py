from typing import Annotated

from fastapi import APIRouter, Depends, Query

from tez.modules.library.router import get_library
from tez.modules.library.service import Library
from tez.modules.reviews import service as reviews_service
from tez.modules.reviews.models import Decision, ScreeningStage
from tez.modules.reviews.schemas import StageCriterion
from tez.modules.screening import service
from tez.modules.screening.schemas import (
    DecisionCreate,
    DecisionView,
    QueueFilter,
    ScreeningQueue,
    ScreeningRecord,
    UndoRequest,
)
from tez.modules.screening.service import Direction

router = APIRouter(prefix="/reviews/{review_id}/screening", tags=["screening"])

LibraryDep = Annotated[Library, Depends(get_library)]
FilterQuery = Annotated[QueueFilter, Query(alias="filter")]


@router.get("/{stage}")
def get_queue(
    review_id: str,
    stage: ScreeningStage,
    library: LibraryDep,
    wanted: FilterQuery = QueueFilter.ALL,
) -> ScreeningQueue:
    """The stage's queue in its stable order, with counts per state (counts ignore the filter)."""
    return service.queue_view(library.db, review_id, stage, wanted)


@router.get("/{stage}/criteria")
def get_criteria(
    review_id: str, stage: ScreeningStage, library: LibraryDep
) -> list[StageCriterion]:
    """The criteria the stage's screening shows, in key order, with their highlight terms."""
    return reviews_service.criteria_for_stage(library.db, review_id, stage)


@router.get("/{stage}/records/{paper_id}")
def get_record(
    review_id: str, stage: ScreeningStage, paper_id: str, library: LibraryDep
) -> ScreeningRecord:
    return service.record_view(library.db, review_id, stage, paper_id)


@router.get("/{stage}/step")
def step(
    review_id: str,
    stage: ScreeningStage,
    library: LibraryDep,
    origin: str | None = None,
    direction: Direction = Direction.NEXT,
    wanted: FilterQuery = QueueFilter.ALL,
) -> ScreeningRecord | None:
    """The next (or previous) record from `origin` that matches the filter, wrapping around;
    null when no other record matches."""
    return service.step(
        library.db, review_id, stage, origin=origin, direction=direction, wanted=wanted
    )


@router.post("/{stage}/decisions", status_code=201)
def decide(
    review_id: str, stage: ScreeningStage, body: DecisionCreate, library: LibraryDep
) -> DecisionView:
    """Decide on a record. It replaces the current decision as a new row (append-only)."""
    return service.decide(
        library.db,
        review_id,
        stage,
        body.paper_id,
        Decision(body.decision.value),
        criterion_id=body.criterion_id,
        note=body.note,
    )


@router.post("/{stage}/undo", status_code=201)
def undo(
    review_id: str, stage: ScreeningStage, body: UndoRequest, library: LibraryDep
) -> DecisionView:
    """Take a decision back by restoring the state before it, as a new row."""
    return service.undo(library.db, review_id, stage, body.decision_id)


@router.get("/history/{paper_id}")
def history(review_id: str, paper_id: str, library: LibraryDep) -> list[DecisionView]:
    return service.history(library.db, review_id, paper_id)
