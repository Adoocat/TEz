"""Which papers an export holds, as BibTeX or RIS text (plan: `tez export`; design 5.10 later).

The scope is a review (every paper taken into it), a collection, or the whole library. Papers
are written in the order of their citation keys, so the same library gives the same file. A
paper without a key (a review record never kept in the library) gets one for this file only.
"""

from enum import StrEnum

from sqlalchemy import select

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.export.schemas import ExportResult
from tez.modules.export.writers import ExportAuthor, ExportPaper, to_bibtex, to_ris
from tez.modules.library import citekeys
from tez.modules.library.models import CollectionPaper, IdentifierScheme, Paper
from tez.modules.library.paper_service import PaperCard, PaperService
from tez.modules.reviews import service as reviews_service


class ExportFormat(StrEnum):
    BIBTEX = "bibtex"
    RIS = "ris"


def _paper(card: PaperCard, key: str) -> ExportPaper:
    paper = card.paper
    return ExportPaper(
        citekey=key,
        title=paper.title,
        authors=tuple(
            ExportAuthor(link.author.display_name, link.author.family, link.author.given)
            for link in paper.authors
        ),
        year=paper.year,
        venue=paper.venue,
        venue_type=paper.venue_type,
        thesis_type=paper.thesis_type,
        volume=paper.volume,
        issue=paper.issue,
        pages=paper.pages,
        doi=card.identifiers.get(IdentifierScheme.DOI),
        arxiv=card.identifiers.get(IdentifierScheme.ARXIV),
        isbn=card.identifiers.get(IdentifierScheme.ISBN),
        url=paper.url,
        abstract=paper.abstract,
        language=paper.language,
    )


def _keys(cards: list[PaperCard]) -> dict[str, str]:
    """Each paper's key: its own, or one made for this file that clashes with no other."""
    taken = {card.paper.citekey for card in cards if card.paper.citekey}
    keys: dict[str, str] = {}
    for card in cards:
        paper = card.paper
        if paper.citekey:
            keys[paper.id] = paper.citekey
            continue
        first = paper.authors[0].author if paper.authors else None
        base = citekeys.base_key(
            first.family or first.display_name if first else None, paper.year, paper.title
        )
        key, suffix = base, 0
        while key in taken:
            suffix += 1
            key = f"{base}{chr(ord('a') + suffix - 1)}" if suffix <= 26 else f"{base}{suffix}"
        taken.add(key)
        keys[paper.id] = key
    return keys


def export(
    db: Database,
    export_format: ExportFormat,
    *,
    review_id: str | None = None,
    collection_id: str | None = None,
) -> ExportResult:
    if review_id is not None and collection_id is not None:
        raise TezError(ErrorCode.EXPORT_ONE_SCOPE, status=422)
    wanted: set[str] = set()
    if review_id is not None:
        if not reviews_service.review_exists(db, review_id):
            raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
        wanted = reviews_service.paper_ids_in_review(db, review_id)
    with db.session() as session:
        papers = PaperService(session)
        if review_id is not None:
            cards = list(papers.cards(wanted).values())
        elif collection_id is not None:
            members = select(CollectionPaper.paper_id).where(
                CollectionPaper.collection_id == collection_id
            )
            cards = papers.cards_where(Paper.id.in_(members), Paper.deleted_at.is_(None))
        else:
            cards = papers.cards_where(
                Paper.library_added_at.is_not(None), Paper.deleted_at.is_(None)
            )
        keys = _keys(cards)
        items = sorted(
            (_paper(card, keys[card.paper.id]) for card in cards), key=lambda p: p.citekey
        )
    content = to_bibtex(items) if export_format is ExportFormat.BIBTEX else to_ris(items)
    return ExportResult(format=export_format.value, count=len(items), content=content)
