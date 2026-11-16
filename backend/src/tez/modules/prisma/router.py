from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.library.router import get_library
from tez.modules.library.service import Library
from tez.modules.prisma import service
from tez.modules.prisma.schemas import PrismaCounts

router = APIRouter(prefix="/reviews/{review_id}/prisma", tags=["prisma"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.get("")
def get_counts(review_id: str, library: LibraryDep) -> PrismaCounts:
    """Every box of the PRISMA 2020 flow diagram, derived now from the review's records."""
    return service.counts(library.db, review_id)
