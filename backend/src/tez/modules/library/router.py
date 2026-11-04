from typing import Annotated

from fastapi import APIRouter, Depends, Request

from tez.core.errors import ErrorCode, TezError
from tez.modules.library.paper_service import PaperService
from tez.modules.library.schemas import LibraryInfo, PaperSelection, SelectionResult
from tez.modules.library.service import Library

router = APIRouter(tags=["library"])


def get_library(request: Request) -> Library:
    """The library this process has open; `library.not_open` (409) if none."""
    library: Library | None = request.app.state.library
    if library is None:
        raise TezError(ErrorCode.LIBRARY_NOT_OPEN, status=409)
    return library


@router.post("/library/papers")
def keep_papers(
    body: PaperSelection, library: Annotated[Library, Depends(get_library)]
) -> SelectionResult:
    """Put papers a search found into the library. Keeping one twice changes nothing."""
    with library.db.write_session() as session:
        added, present = PaperService(session).keep(body.paper_ids)
    return SelectionResult(added=added, already_present=present)


@router.get("/library")
def library_info(library: Annotated[Library, Depends(get_library)]) -> LibraryInfo:
    return library.info()
