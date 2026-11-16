from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.greylit import service
from tez.modules.greylit.schemas import GreyEntry, GreyRecordAdded, GreyRecordCreate
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

router = APIRouter(prefix="/reviews/{review_id}/grey-literature", tags=["grey literature"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.post("", status_code=201)
def add_record(review_id: str, body: GreyRecordCreate, library: LibraryDep) -> GreyRecordAdded:
    """Add a thesis, report, register record or web page found by other methods. It is
    matched against the library, logged for PRISMA and taken into the review."""
    return service.add_record(library.db, library.path, review_id, body)


@router.get("")
def list_entries(review_id: str, library: LibraryDep) -> list[GreyEntry]:
    """The review's grey literature: records by hand and imports marked as other methods."""
    return service.entries(library.db, review_id)
