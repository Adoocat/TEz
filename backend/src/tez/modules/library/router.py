from typing import Annotated

from fastapi import APIRouter, Depends, Request

from tez.core.errors import ErrorCode, TezError
from tez.modules.library.schemas import LibraryInfo
from tez.modules.library.service import Library

router = APIRouter(tags=["library"])


def get_library(request: Request) -> Library:
    """The library this process has open; `library.not_open` (409) if none."""
    library: Library | None = request.app.state.library
    if library is None:
        raise TezError(ErrorCode.LIBRARY_NOT_OPEN, status=409)
    return library


@router.get("/library")
def library_info(library: Annotated[Library, Depends(get_library)]) -> LibraryInfo:
    return library.info()
