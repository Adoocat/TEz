from sqlalchemy import select
from sqlalchemy.orm import Session

from tez.modules.anchors.models import Anchor
from tez.modules.annotations.models import Annotation


class AnnotationsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, annotation: Annotation) -> Annotation:
        self.session.add(annotation)
        self.session.flush()
        return annotation

    def get(self, annotation_id: str) -> Annotation | None:
        return self.session.get(Annotation, annotation_id)

    def by_anchor(self, anchor_id: str) -> Annotation | None:
        return self.session.scalar(select(Annotation).where(Annotation.anchor_id == anchor_id))

    def of_attachment(self, attachment_id: str) -> list[Annotation]:
        return list(
            self.session.scalars(
                select(Annotation)
                .join(Anchor, Anchor.id == Annotation.anchor_id)
                .where(Anchor.attachment_id == attachment_id)
            )
        )

    def delete(self, annotation: Annotation) -> None:
        self.session.delete(annotation)
        self.session.flush()
