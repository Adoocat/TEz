from sqlalchemy import select
from sqlalchemy.orm import Session

from tez.modules.anchors.models import Anchor, AnchorKind


class AnchorsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, anchor: Anchor) -> Anchor:
        self.session.add(anchor)
        self.session.flush()
        return anchor

    def get(self, anchor_id: str) -> Anchor | None:
        return self.session.get(Anchor, anchor_id)

    def many(self, anchor_ids: list[str]) -> list[Anchor]:
        return list(self.session.scalars(select(Anchor).where(Anchor.id.in_(anchor_ids))))

    def of_attachment(self, attachment_id: str) -> list[Anchor]:
        return list(
            self.session.scalars(
                select(Anchor)
                .where(Anchor.attachment_id == attachment_id)
                .order_by(Anchor.page_index, Anchor.char_start, Anchor.created_at)
            )
        )

    def same_text(
        self, attachment_id: str, file_sha256: str, page_index: int, start: int, end: int
    ) -> Anchor | None:
        """The anchor of exactly this passage, if there is one already."""
        return self.session.scalar(
            select(Anchor).where(
                Anchor.attachment_id == attachment_id,
                Anchor.file_sha256 == file_sha256,
                Anchor.kind == AnchorKind.TEXT,
                Anchor.page_index == page_index,
                Anchor.char_start == start,
                Anchor.char_end == end,
            )
        )
