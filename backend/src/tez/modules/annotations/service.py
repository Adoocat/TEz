"""Highlights, marked areas and their comments (plan, Task 47)."""

from typing import cast

from sqlalchemy.orm import Session

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.anchors import service as anchors_service
from tez.modules.anchors.models import AnchorKind
from tez.modules.anchors.schemas import AnchorView
from tez.modules.annotations.models import Annotation, AnnotationKind
from tez.modules.annotations.repository import AnnotationsRepository
from tez.modules.annotations.schemas import (
    AnnotationCreate,
    AnnotationPatch,
    AnnotationView,
    HighlightColor,
)
from tez.modules.files import service as files_service


def _view(annotation: Annotation, anchor: AnchorView) -> AnnotationView:
    return AnnotationView(
        id=annotation.id,
        kind=annotation.kind,
        color=cast(HighlightColor, annotation.color),
        comment=annotation.comment_md,
        anchor=anchor,
        created_at=annotation.created_at,
        updated_at=annotation.updated_at,
    )


def _one(session: Session, annotation: Annotation) -> AnnotationView:
    anchors = anchors_service.by_id(session, [annotation.anchor_id])
    return _view(annotation, anchors[annotation.anchor_id])


def _get(session: Session, annotation_id: str) -> Annotation:
    annotation = AnnotationsRepository(session).get(annotation_id)
    if annotation is None:
        params = {"annotation_id": annotation_id}
        raise TezError(ErrorCode.ANNOTATION_NOT_FOUND, params, status=404)
    return annotation


def create(db: Database, attachment_id: str, body: AnnotationCreate) -> AnnotationView:
    """Mark a place. A passage marked again changes its colour and keeps its comment."""
    with db.write_session() as session:
        anchor = anchors_service.create(session, attachment_id, body.anchor)
        repository = AnnotationsRepository(session)
        annotation = repository.by_anchor(anchor.id)
        if annotation is None:
            area = body.anchor.kind is AnchorKind.AREA
            annotation = repository.add(
                Annotation(
                    paper_id=files_service.file_facts(session, attachment_id).paper_id,
                    anchor_id=anchor.id,
                    kind=AnnotationKind.AREA if area else AnnotationKind.HIGHLIGHT,
                    color=body.color,
                    comment_md=body.comment.strip(),
                )
            )
        else:
            annotation.color = body.color
            annotation.comment_md = body.comment.strip() or annotation.comment_md
            session.flush()
        return _one(session, annotation)


def of_attachment(db: Database, attachment_id: str) -> list[AnnotationView]:
    """In reading order: by page, then from the top."""
    files_service.get_attachment(db, attachment_id)
    with db.session() as session:
        annotations = AnnotationsRepository(session).of_attachment(attachment_id)
        anchors = anchors_service.by_id(session, [a.anchor_id for a in annotations])
        found = [_view(a, anchors[a.anchor_id]) for a in annotations]
    found.sort(key=lambda a: (a.anchor.page, -a.anchor.rects[0][3], a.anchor.rects[0][0]))
    return found


def update(db: Database, annotation_id: str, body: AnnotationPatch) -> AnnotationView:
    with db.write_session() as session:
        annotation = _get(session, annotation_id)
        if body.color is not None:
            annotation.color = body.color
        if body.comment is not None:
            annotation.comment_md = body.comment.strip()
        session.flush()
        return _one(session, annotation)


def delete(db: Database, annotation_id: str) -> None:
    """Removes the mark. Its anchor stays: a note or a matrix cell may point at it."""
    with db.write_session() as session:
        AnnotationsRepository(session).delete(_get(session, annotation_id))
