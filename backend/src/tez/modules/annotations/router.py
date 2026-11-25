from typing import Annotated

from fastapi import APIRouter, Depends, Response

from tez.modules.annotations import service
from tez.modules.annotations.schemas import AnnotationCreate, AnnotationPatch, AnnotationView
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

router = APIRouter(tags=["annotations"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.post("/attachments/{attachment_id}/annotations", status_code=201)
def create_annotation(
    attachment_id: str, body: AnnotationCreate, library: LibraryDep
) -> AnnotationView:
    """Highlight a passage or mark an area. The same passage again changes its colour."""
    return service.create(library.db, attachment_id, body)


@router.get("/attachments/{attachment_id}/annotations")
def attachment_annotations(attachment_id: str, library: LibraryDep) -> list[AnnotationView]:
    return service.of_attachment(library.db, attachment_id)


@router.patch("/annotations/{annotation_id}")
def update_annotation(
    annotation_id: str, body: AnnotationPatch, library: LibraryDep
) -> AnnotationView:
    return service.update(library.db, annotation_id, body)


@router.delete("/annotations/{annotation_id}", status_code=204)
def delete_annotation(annotation_id: str, library: LibraryDep) -> Response:
    service.delete(library.db, annotation_id)
    return Response(status_code=204)
