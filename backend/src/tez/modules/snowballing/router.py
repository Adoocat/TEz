from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.library.router import get_library
from tez.modules.library.service import Library
from tez.modules.snowballing import service
from tez.modules.snowballing.schemas import (
    SnowballRoundView,
    SnowballSeed,
    SnowballStart,
    SnowballStarted,
)

router = APIRouter(prefix="/reviews/{review_id}/snowball", tags=["snowballing"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.post("", status_code=202)
def start_round(review_id: str, body: SnowballStart, library: LibraryDep) -> SnowballStarted:
    """Queue a snowballing round from the given seed papers; the worker runs it as a job."""
    return service.start_round(
        library.db,
        review_id,
        body.paper_ids,
        body.directions,
        body.sources,
        limit=body.limit,
        initiated_via=body.initiated_via,
    )


@router.get("")
def list_rounds(review_id: str, library: LibraryDep) -> list[SnowballRoundView]:
    """The review's snowballing actions, newest first."""
    return service.rounds(library.db, review_id)


@router.get("/seeds")
def list_seeds(review_id: str, library: LibraryDep) -> list[SnowballSeed]:
    """The review's papers as candidate seeds."""
    return service.seeds(library.db, review_id)
