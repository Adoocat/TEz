"""The text inside PDFs: read in the worker, kept page by page (Task 43), searched (Task 44)."""

import logging
import time

from tez.core.db import Database
from tez.modules.files import service as files_service
from tez.modules.files.models import TextStatus
from tez.modules.fulltext import search_index
from tez.modules.fulltext.extraction import extract_pages
from tez.modules.fulltext.repository import FulltextRepository
from tez.modules.fulltext.schemas import (
    FulltextPage,
    FulltextPaper,
    FulltextQuery,
    FulltextResults,
    SnippetPart,
)
from tez.modules.jobs.registry import JobContext
from tez.modules.library.paper_service import PaperService

logger = logging.getLogger(__name__)

# Pages shown per paper; `page_hits` says how many there are.
_PAGES_PER_PAPER = 3


def extract_text(payload: dict[str, object], ctx: JobContext) -> None:
    """The `pdf.extract_text` job. Running it again replaces the text, never adds to it."""
    attachment_id = str(payload["attachment_id"])

    def keep_going(done: float) -> bool:
        ctx.report(done)
        return not ctx.cancelled

    pages = files_service.open_in_worker(
        attachment_id, ctx, lambda path: extract_pages(path, keep_going=keep_going)
    )
    if pages is None:
        return
    has_text = any(page.text.strip() for page in pages)
    with ctx.db.write_session() as session:
        known = files_service.set_text_status(
            session,
            attachment_id,
            TextStatus.OK if has_text else TextStatus.NEEDS_OCR,
            page_count=len(pages),
            text_version=files_service.TEXT_VERSION,
        )
        if known:
            FulltextRepository(session).replace(attachment_id, pages)
    ctx.report(1.0)
    logger.info("pdf text read", extra={"id": attachment_id, "pages": len(pages)})


def search(db: Database, query: FulltextQuery) -> FulltextResults:
    """Papers by their best matching page, each with its best pages and a passage of each."""
    started = time.perf_counter()
    terms = search_index.parse(query.q)
    if not terms:
        return FulltextResults(
            papers=[], total_papers=0, total_pages=0, truncated=False, elapsed_ms=0.0
        )
    with db.session() as session:
        service = PaperService(session)
        wanted = service.library_ids()
        if query.paper_ids is not None:
            wanted &= set(query.paper_ids)
        found = search_index.find_pages(session.connection(), terms, wanted)
        by_paper: dict[str, list[tuple[int, str, int]]] = {}
        for row, paper_id, attachment_id, page_index in found:
            by_paper.setdefault(paper_id, []).append((row, attachment_id, page_index))
        # Dictionaries keep insertion order: the paper with the best page comes first.
        shown = list(by_paper)[: query.limit]
        rows = [row for paper_id in shown for row, _, _ in by_paper[paper_id][:_PAGES_PER_PAPER]]
        texts = FulltextRepository(session).texts(rows)
        cards = service.cards(shown)
        papers: list[FulltextPaper] = []
        for paper_id in shown:
            hits = by_paper[paper_id]
            card = cards[paper_id]
            papers.append(
                FulltextPaper(
                    paper_id=paper_id,
                    title=card.paper.title,
                    first_author=card.first_author.display_name if card.first_author else None,
                    author_count=card.author_count,
                    year=card.paper.year,
                    page_hits=len(hits),
                    pages=[
                        FulltextPage(
                            attachment_id=attachment_id,
                            page=page_index + 1,
                            snippet=[
                                SnippetPart(text=part.text, hit=part.hit)
                                for part in search_index.snippet(texts[row], terms)
                            ],
                        )
                        for row, attachment_id, page_index in hits[:_PAGES_PER_PAPER]
                    ],
                )
            )
    return FulltextResults(
        papers=papers,
        total_papers=len(by_paper),
        total_pages=len(found),
        truncated=len(found) >= search_index.MAX_PAGES,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
    )
