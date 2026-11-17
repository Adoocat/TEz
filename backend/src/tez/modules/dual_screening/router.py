from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.dual_screening import service
from tez.modules.dual_screening.fileformat import DecisionFile
from tez.modules.dual_screening.schemas import DecisionImport, ImportReport
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

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
