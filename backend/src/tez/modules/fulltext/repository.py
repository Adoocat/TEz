from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from tez.modules.fulltext import search_index
from tez.modules.fulltext.extraction import PageText
from tez.modules.fulltext.models import TextChunk


class FulltextRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace(self, attachment_id: str, pages: Sequence[PageText]) -> None:
        """Store these pages as the whole text of the attachment."""
        self.session.execute(delete(TextChunk).where(TextChunk.attachment_id == attachment_id))
        # A write session holds SQLite's only write lock, so the next number is ours.
        first = (self.session.scalar(select(func.max(TextChunk.search_row))) or 0) + 1
        chunks = [
            TextChunk(
                attachment_id=attachment_id,
                page_index=page.index,
                ord=order,
                text=page.text,
                char_start=0,
                char_end=len(page.text),
                search_row=first + order,
            )
            for order, page in enumerate(pages)
        ]
        self.session.add_all(chunks)
        self.session.flush()
        rows = [(chunk.search_row, chunk.text) for chunk in chunks]
        search_index.add(self.session.connection(), rows)

    def texts(self, search_rows: Sequence[int]) -> dict[int, str]:
        rows = self.session.execute(
            select(TextChunk.search_row, TextChunk.text).where(
                TextChunk.search_row.in_(search_rows)
            )
        )
        return {row: text for row, text in rows}

    def pages(self, attachment_id: str) -> list[TextChunk]:
        return list(
            self.session.scalars(
                select(TextChunk)
                .where(TextChunk.attachment_id == attachment_id)
                .order_by(TextChunk.ord)
            )
        )
