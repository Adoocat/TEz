from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from tez.core.errors import ErrorCode, TezError
from tez.modules.library import organize
from tez.modules.library.paper_service import PaperService
from tez.modules.library.schemas import (
    ChangeCount,
    CollectionCreate,
    CollectionPatch,
    CollectionView,
    LibraryInfo,
    LibraryPaperRow,
    PaperIds,
    PaperSelection,
    ReadingStatusChange,
    SelectionResult,
    TagCreate,
    TagPatch,
    TagView,
)
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


LibraryDep = Annotated[Library, Depends(get_library)]


@router.get("/papers")
def list_papers(
    library: LibraryDep, collection_id: str | None = None, tag_id: str | None = None
) -> list[LibraryPaperRow]:
    """The library's papers (not search candidates, not the trash), newest first."""
    return organize.list_papers(library.db, collection_id=collection_id, tag_id=tag_id)


@router.patch("/papers/reading-status")
def set_reading_status(body: ReadingStatusChange, library: LibraryDep) -> ChangeCount:
    return organize.set_reading_status(library.db, body.paper_ids, body.reading_status)


@router.get("/collections")
def list_collections(library: LibraryDep) -> list[CollectionView]:
    """The whole tree, parents before children, with each collection's paper count."""
    return organize.list_collections(library.db)


@router.post("/collections", status_code=201)
def create_collection(body: CollectionCreate, library: LibraryDep) -> CollectionView:
    return organize.create_collection(library.db, body.name, body.parent_id)


@router.patch("/collections/{collection_id}")
def update_collection(
    collection_id: str, body: CollectionPatch, library: LibraryDep
) -> CollectionView:
    """Rename and/or move; moving under itself or a descendant is `collection.cycle`."""
    changes = body.model_dump(include=body.model_fields_set)
    return organize.update_collection(library.db, collection_id, changes)


@router.delete("/collections/{collection_id}", status_code=204)
def delete_collection(collection_id: str, library: LibraryDep) -> Response:
    """Deletes its sub-collections too. Papers stay in the library."""
    organize.delete_collection(library.db, collection_id)
    return Response(status_code=204)


@router.post("/collections/{collection_id}/papers")
def add_to_collection(collection_id: str, body: PaperIds, library: LibraryDep) -> ChangeCount:
    return organize.add_to_collection(library.db, collection_id, body.paper_ids)


@router.post("/collections/{collection_id}/papers/remove")
def remove_from_collection(collection_id: str, body: PaperIds, library: LibraryDep) -> ChangeCount:
    return organize.remove_from_collection(library.db, collection_id, body.paper_ids)


@router.get("/tags")
def list_tags(library: LibraryDep) -> list[TagView]:
    return organize.list_tags(library.db)


@router.post("/tags", status_code=201)
def create_tag(body: TagCreate, library: LibraryDep) -> TagView:
    return organize.create_tag(library.db, body.name, body.color)


@router.patch("/tags/{tag_id}")
def update_tag(tag_id: str, body: TagPatch, library: LibraryDep) -> TagView:
    return organize.update_tag(library.db, tag_id, body.model_dump(include=body.model_fields_set))


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: str, library: LibraryDep) -> Response:
    organize.delete_tag(library.db, tag_id)
    return Response(status_code=204)


@router.post("/tags/{tag_id}/papers")
def tag_papers(tag_id: str, body: PaperIds, library: LibraryDep) -> ChangeCount:
    return organize.tag_papers(library.db, tag_id, body.paper_ids)


@router.post("/tags/{tag_id}/papers/remove")
def untag_papers(tag_id: str, body: PaperIds, library: LibraryDep) -> ChangeCount:
    return organize.untag_papers(library.db, tag_id, body.paper_ids)
