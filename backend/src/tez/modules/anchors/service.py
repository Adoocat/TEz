"""Places in PDFs: made from a selection, checked against the file's text, found again when the
file changes (plan, Task 46).

The API never opens a PDF. It checks the selected quote against the text Task 43 stored; boxes
for a moved passage come from PDFium in the worker (`check_anchors`, after the text is read).
"""

import logging
from collections.abc import Iterable, Sequence

from sqlalchemy.orm import Session

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.anchors.boxes import passage_rects
from tez.modules.anchors.models import Anchor, AnchorKind, AnchorState
from tez.modules.anchors.repository import AnchorsRepository
from tez.modules.anchors.schemas import AnchorCreate, AnchorPaper, AnchorStatus, AnchorView
from tez.modules.files import service as files_service
from tez.modules.fulltext import service as fulltext_service
from tez.modules.fulltext.extraction import readable
from tez.modules.jobs.registry import JobContext
from tez.modules.library.paper_service import PaperService
from tez.shared.passages import CONTEXT, Place, Quote, key_of, locate_on_page, relocate

logger = logging.getLogger(__name__)

# Characters kept around a quote: more than the letters compared, spaces and all.
_AROUND = 2 * CONTEXT


def _quote_of(anchor: Anchor) -> Quote:
    return Quote(anchor.quote_exact, anchor.quote_prefix, anchor.quote_suffix)


def _set_place(anchor: Anchor, text: str, place: Place) -> None:
    """Remember the passage as the file has it: its own words, and what stands around it."""
    anchor.state = AnchorState.VERIFIED
    anchor.char_start, anchor.char_end = place.start, place.end
    anchor.quote_exact = readable(text[place.start : place.end]).replace("\n", " ")
    before = text[max(0, place.start - _AROUND) : place.start]
    after = text[place.end : place.end + _AROUND]
    anchor.quote_prefix = readable(before).replace("\n", " ")
    anchor.quote_suffix = readable(after).replace("\n", " ")


def create(session: Session, attachment_id: str, body: AnchorCreate) -> Anchor:
    """An anchor for a selection; the same passage selected twice is the same anchor.

    A quote that is not in the stored text (not read yet, or read differently) is kept as the
    reader showed it, `unverified`; it is checked again when the text is read.
    """
    attachment = files_service.file_facts(session, attachment_id)
    if attachment.page_count is not None and body.page > attachment.page_count:
        params = {"page": body.page, "pages": attachment.page_count}
        raise TezError(ErrorCode.ANCHOR_NO_SUCH_PAGE, params, status=422)
    anchor = Anchor(
        attachment_id=attachment_id,
        file_sha256=attachment.sha256,
        kind=body.kind,
        state=AnchorState.VERIFIED if body.kind is AnchorKind.AREA else AnchorState.UNVERIFIED,
        page_index=body.page - 1,
        rects_json=[list(rect) for rect in body.rects],
        quote_exact=" ".join(body.quote.split()) if body.kind is AnchorKind.TEXT else "",
        quote_prefix=body.prefix if body.kind is AnchorKind.TEXT else "",
        quote_suffix=body.suffix if body.kind is AnchorKind.TEXT else "",
    )
    repository = AnchorsRepository(session)
    if body.kind is AnchorKind.TEXT:
        text = fulltext_service.page_text(session, attachment_id, anchor.page_index)
        place = None
        if text is not None:
            place = locate_on_page(text, _quote_of(anchor), occurrence=body.occurrence)
        if text is not None and place is not None:
            known = repository.same_text(
                attachment_id, anchor.file_sha256, anchor.page_index, place.start, place.end
            )
            if known is not None:
                return known
            _set_place(anchor, text, place)
        else:
            logger.info("selected text not found in the file's text", extra={"id": attachment_id})
    return repository.add(anchor)


def views(session: Session, anchors: Sequence[Anchor]) -> list[AnchorView]:
    facts = {
        attachment_id: files_service.file_facts(session, attachment_id)
        for attachment_id in {anchor.attachment_id for anchor in anchors}
    }
    cards = PaperService(session).cards({fact.paper_id for fact in facts.values()})
    found: list[AnchorView] = []
    for anchor in anchors:
        fact = facts[anchor.attachment_id]
        card = cards[fact.paper_id]
        status: AnchorStatus = anchor.state.value
        if anchor.state is not AnchorState.LOST and anchor.file_sha256 != fact.sha256:
            status = "checking"
        found.append(
            AnchorView(
                id=anchor.id,
                attachment_id=anchor.attachment_id,
                kind=anchor.kind,
                status=status,
                page=anchor.page_index + 1,
                rects=anchor.rects_json,
                quote=anchor.quote_exact,
                prefix=anchor.quote_prefix,
                suffix=anchor.quote_suffix,
                paper=AnchorPaper(
                    id=fact.paper_id,
                    title=card.paper.title,
                    first_author=card.first_author.display_name if card.first_author else None,
                    author_count=card.author_count,
                    year=card.paper.year,
                    citekey=card.paper.citekey,
                ),
            )
        )
    return found


def add(db: Database, attachment_id: str, body: AnchorCreate) -> AnchorView:
    with db.write_session() as session:
        anchor = create(session, attachment_id, body)
        return views(session, [anchor])[0]


def get(db: Database, anchor_id: str) -> AnchorView:
    with db.session() as session:
        anchor = AnchorsRepository(session).get(anchor_id)
        if anchor is None:
            raise TezError(ErrorCode.ANCHOR_NOT_FOUND, {"anchor_id": anchor_id}, status=404)
        return views(session, [anchor])[0]


def of_attachment(db: Database, attachment_id: str) -> list[AnchorView]:
    files_service.get_attachment(db, attachment_id)
    with db.session() as session:
        return views(session, AnchorsRepository(session).of_attachment(attachment_id))


def by_id(session: Session, anchor_ids: Iterable[str]) -> dict[str, AnchorView]:
    """For other modules: the anchors they point at."""
    found = AnchorsRepository(session).many(list(set(anchor_ids)))
    return {view.id: view for view in views(session, found)}


def ids_in_paper(session: Session, paper_id: str) -> list[str]:
    """Every anchor in a paper's files."""
    attachments = [a.id for a in files_service.attachments_in(session, paper_id)]
    repository = AnchorsRepository(session)
    return [anchor.id for a in attachments for anchor in repository.of_attachment(a)]


# --- worker side ----------------------------------------------------------------------


def read_text(payload: dict[str, object], ctx: JobContext) -> None:
    """The `pdf.extract_text` job: read the text, then check the anchors that stand on it."""
    fulltext_service.extract_text(payload, ctx)
    if not ctx.cancelled:
        check_anchors(str(payload["attachment_id"]), ctx)


def check_anchors(attachment_id: str, ctx: JobContext) -> None:
    """Bring a file's anchors in step with the text it has now."""
    with ctx.db.session() as session:
        texts = fulltext_service.page_texts(session, attachment_id)
        anchors = AnchorsRepository(session).of_attachment(attachment_id)
        if texts is None or not anchors:
            return
        sha256 = files_service.file_facts(session, attachment_id).sha256
        moved = [a for a in anchors if a.file_sha256 != sha256]
        places = {
            a.id: relocate(texts, _quote_of(a), home=a.page_index)
            for a in moved
            if a.kind is AnchorKind.TEXT
        }
    # Boxes come from the file itself, outside any transaction.
    rects: dict[str, list[list[float]]] = {}
    for anchor_id, place in places.items():
        if place is None:
            continue
        at = place
        boxes = files_service.open_in_worker(
            attachment_id, ctx, lambda path, at=at: passage_rects(path, at.index, at.start, at.end)
        )
        if boxes is None:
            return  # unreadable now: the file is marked, the anchors wait for the next reading
        rects[anchor_id] = boxes
    with ctx.db.write_session() as session:
        if files_service.file_facts(session, attachment_id).sha256 != sha256:
            return  # replaced again meanwhile; its own job checks
        for anchor in AnchorsRepository(session).of_attachment(attachment_id):
            if anchor.file_sha256 != sha256:
                _move(anchor, sha256, texts, places.get(anchor.id), rects.get(anchor.id))
            elif anchor.kind is AnchorKind.TEXT:
                _recheck(anchor, texts)
            else:
                anchor.state = AnchorState.VERIFIED  # the file it was drawn on is back


def _move(
    anchor: Anchor,
    sha256: str,
    texts: Sequence[str],
    place: Place | None,
    rects: list[list[float]] | None,
) -> None:
    """Into the new file, or nowhere: never to a place that only looks right."""
    if anchor.state is AnchorState.LOST and place is None:
        return
    if place is None or not rects:
        anchor.state = AnchorState.LOST
        anchor.char_start = anchor.char_end = None
        logger.info("anchor lost", extra={"anchor_id": anchor.id, "kind": anchor.kind.value})
        return
    anchor.file_sha256 = sha256
    anchor.page_index = place.index
    anchor.rects_json = rects
    _set_place(anchor, texts[place.index], place)


def _recheck(anchor: Anchor, texts: Sequence[str]) -> None:
    """The same file, read (again): the boxes hold, the positions may not."""
    if anchor.page_index >= len(texts):
        return
    text = texts[anchor.page_index]
    if anchor.char_start is not None and anchor.char_end is not None:
        here = text[anchor.char_start : anchor.char_end]
        if key_of(here).text == key_of(anchor.quote_exact).text:
            return
    place = locate_on_page(text, _quote_of(anchor))
    if place is not None:
        _set_place(anchor, text, place)
    else:
        anchor.state = AnchorState.UNVERIFIED
        anchor.char_start = anchor.char_end = None
