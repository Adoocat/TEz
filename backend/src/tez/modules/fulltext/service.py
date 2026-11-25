"""The text inside PDFs (plan, Task 43): read in the worker, kept page by page."""

import logging

from tez.modules.files import service as files_service
from tez.modules.files.models import TextStatus
from tez.modules.fulltext.extraction import extract_pages
from tez.modules.fulltext.repository import FulltextRepository
from tez.modules.jobs.registry import JobContext

logger = logging.getLogger(__name__)


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
