from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.dual_screening import service
from tez.modules.dual_screening.fileformat import DecisionFile
from tez.modules.dual_screening.schemas import (
    AgreementView,
    ConflictList,
    DecisionImport,
    ImportReport,
    Reconciliation,
)
from tez.modules.library.router import get_library
from tez.modules.library.service import Library
from tez.modules.reviews.models import ScreeningStage
from tez.modules.screening.schemas import DecisionView

router = APIRouter(prefix="/reviews/{review_id}/decisions", tags=["dual screening"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.get("/export")
def export_decisions(review_id: str, reviewer: str, library: LibraryDep) -> DecisionFile:
    """The owner's decisions in force as a decision file, under the name `reviewer`."""
    return service.export_decisions(library.db, review_id, reviewer)


@router.post("/import")
def import_decisions(review_id: str, body: DecisionImport, library: LibraryDep) -> ImportReport:
    """A colleague's decision file: matched records get their decisions, appended under the
    file's reviewer name; the rest is reported. Importing the same file again adds nothing."""
    return service.import_decisions(library.db, review_id, body.content)


@router.get("/reviewers")
def list_reviewers(review_id: str, library: LibraryDep) -> list[str]:
    """Everyone who has decided in the review, the owner first."""
    return service.reviewers(library.db, review_id)


@router.get("/agreement")
def get_agreement(
    review_id: str, library: LibraryDep, reviewer: str | None = None
) -> AgreementView:
    """Agreement between the owner and a colleague per stage: percent, Cohen's kappa and the
    conflicts still open. Without `reviewer`, the first colleague by name."""
    return service.agreement(library.db, review_id, reviewer)


@router.get("/conflicts/{stage}")
def get_conflicts(
    review_id: str, stage: ScreeningStage, library: LibraryDep, reviewer: str | None = None
) -> ConflictList:
    """The stage's open conflicts, both decisions side by side."""
    return service.conflicts(library.db, review_id, stage, reviewer)


@router.post("/conflicts/{stage}/reconcile")
def reconcile(
    review_id: str, stage: ScreeningStage, body: Reconciliation, library: LibraryDep
) -> DecisionView:
    """Resolve a conflict: the agreed decision is a new `consensus` row; the reviewers' own
    decisions stay as they are."""
    return service.reconcile(library.db, review_id, stage, body)
