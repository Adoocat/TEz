from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.anchors import service
from tez.modules.anchors.schemas import AnchorCreate, AnchorView
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

router = APIRouter(tags=["anchors"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.post("/attachments/{attachment_id}/anchors", status_code=201)
def create_anchor(attachment_id: str, body: AnchorCreate, library: LibraryDep) -> AnchorView:
    """Remember a place in a PDF. The same passage twice is the same anchor."""
    return service.add(library.db, attachment_id, body)


@router.get("/attachments/{attachment_id}/anchors")
def attachment_anchors(attachment_id: str, library: LibraryDep) -> list[AnchorView]:
    return service.of_attachment(library.db, attachment_id)


@router.get("/anchors/{anchor_id}")
def get_anchor(anchor_id: str, library: LibraryDep) -> AnchorView:
    return service.get(library.db, anchor_id)
