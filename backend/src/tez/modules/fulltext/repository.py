from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tez.modules.fulltext.extraction import PageText
from tez.modules.fulltext.models import TextChunk


class FulltextRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace(self, attachment_id: str, pages: Sequence[PageText]) -> None:
        """Store these pages as the whole text of the attachment."""
        self.session.execute(delete(TextChunk).where(TextChunk.attachment_id == attachment_id))
        self.session.add_all(
            TextChunk(
                attachment_id=attachment_id,
                page_index=page.index,
                ord=order,
                text=page.text,
                char_start=0,
                char_end=len(page.text),
            )
            for order, page in enumerate(pages)
        )
        self.session.flush()

    def pages(self, attachment_id: str) -> list[TextChunk]:
        return list(
            self.session.scalars(
                select(TextChunk)
                .where(TextChunk.attachment_id == attachment_id)
                .order_by(TextChunk.ord)
            )
        )
