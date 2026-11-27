from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.library.router import get_library
from tez.modules.library.service import Library
from tez.modules.structure import service
from tez.modules.structure.schemas import GrobidStatus, StructureQueued, StructureView

router = APIRouter(tags=["structure"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.get("/grobid")
def grobid_status(library: LibraryDep) -> GrobidStatus:
    """Whether a GROBID address is set; while not, the app shows nothing that needs it."""
    return GrobidStatus(configured=service.configured_url(library.db) is not None)


@router.post("/attachments/{attachment_id}/structure", status_code=202)
def read_structure(attachment_id: str, library: LibraryDep) -> StructureQueued:
    """Have GROBID read the file's sections and references (a worker job)."""
    return service.queue_read(library.db, attachment_id)


@router.get("/attachments/{attachment_id}/structure")
def get_structure(attachment_id: str, library: LibraryDep) -> StructureView:
    return service.structure(library.db, attachment_id)
