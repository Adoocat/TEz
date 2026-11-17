"""Which papers an export holds, as BibTeX, RIS or a formatted bibliography (`tez export`,
design 5.10).

The scope is a review (every paper taken into it, or only its included studies), a collection,
chosen papers, or the whole library. Papers are taken in the order of their citation keys, so
the same library gives the same file. A paper without a key (a review record never kept in the
library) gets one for this file only.
"""

from collections.abc import Sequence
from enum import StrEnum

from sqlalchemy import select

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.export import csl
from tez.modules.export.schemas import (
    BibliographyEntry,
    BibliographyResult,
    ExportResult,
    SearchStrategy,
    StrategyRow,
)
from tez.modules.export.writers import ExportAuthor, ExportPaper, to_bibtex, to_ris
from tez.modules.library import citekeys
from tez.modules.library.models import CollectionPaper, IdentifierScheme, Paper
from tez.modules.library.paper_service import PaperCard, PaperService
from tez.modules.reviews import service as reviews_service
from tez.modules.reviews.models import ScreeningStage
from tez.modules.screening.service import ScreeningService
from tez.modules.search import queries as search_queries
from tez.modules.search.models import RunMethod
from tez.modules.search.queries import RunFacts


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


def _papers(
    db: Database,
    *,
    review_id: str | None,
    included_only: bool,
    collection_id: str | None,
    paper_ids: Sequence[str] | None,
) -> list[ExportPaper]:
    """The papers in scope, sorted by citation key. At most one of review, collection and
    papers; none means the whole library."""
    if sum(scope is not None for scope in (review_id, collection_id, paper_ids)) > 1:
        raise TezError(ErrorCode.EXPORT_ONE_SCOPE, status=422)
    if review_id is not None and not reviews_service.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
    if review_id is not None and not included_only:
        wanted: set[str] | None = reviews_service.paper_ids_in_review(db, review_id)
    else:
        wanted = set(paper_ids) if paper_ids is not None else None
    with db.session() as session:
        if review_id is not None and included_only:
            # The review's included studies: included at full text (Task 31's decisions).
            wanted = set(ScreeningService(session).included(review_id, ScreeningStage.FULL_TEXT))
        papers = PaperService(session)
        if wanted is not None:
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
        return sorted(
            (_paper(card, keys[card.paper.id]) for card in cards), key=lambda p: p.citekey
        )


def export(
    db: Database,
    export_format: ExportFormat,
    *,
    review_id: str | None = None,
    included_only: bool = False,
    collection_id: str | None = None,
    paper_ids: Sequence[str] | None = None,
) -> ExportResult:
    """BibTeX or RIS. A review's scope is every paper taken into it, or with `included_only`
    its included studies."""
    items = _papers(
        db,
        review_id=review_id,
        included_only=included_only,
        collection_id=collection_id,
        paper_ids=paper_ids,
    )
    content = to_bibtex(items) if export_format is ExportFormat.BIBTEX else to_ris(items)
    return ExportResult(
        format=export_format.value,
        count=len(items),
        content=content,
        citekeys=[item.citekey for item in items],
    )


def _strategy_row(run: RunFacts) -> StrategyRow:
    return StrategyRow(
        run_id=run.id,
        source=run.source,
        method=run.method,
        snowball_round=run.snowball_round,
        executed_at=run.executed_at,
        query=run.translated_query,
        file_name=run.file_name,
        total_reported=run.total_reported,
        retrieved=len(run.paper_ids),
        status=run.status,
    )


def search_strategy(db: Database, review_id: str) -> SearchStrategy:
    """Every search run of the review, oldest first, for the methods chapter: one row per
    source asked, file imported or snowballing step."""
    if not reviews_service.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
    runs = search_queries.runs_by_method(db, review_id, list(RunMethod))
    return SearchStrategy(review_id=review_id, rows=[_strategy_row(run) for run in runs])


def bibliography(
    db: Database,
    style: csl.CslStyle,
    locale: csl.CslLocale,
    *,
    review_id: str | None = None,
    collection_id: str | None = None,
    paper_ids: Sequence[str] | None = None,
) -> BibliographyResult:
    """A formatted bibliography. A review's scope is its included studies."""
    items = _papers(
        db,
        review_id=review_id,
        included_only=True,
        collection_id=collection_id,
        paper_ids=paper_ids,
    )
    entries = [
        BibliographyEntry(citekey=entry.citekey, html=entry.html, text=entry.text)
        for entry in csl.render(style, locale, items)
    ]
    return BibliographyResult(
        style=style,
        locale=locale,
        count=len(entries),
        entries=entries,
        text="\n".join(entry.text for entry in entries),
        html="".join(f"<p>{entry.html}</p>" for entry in entries),
    )
