"""Reading searches back for the API. Every count is derived, never stored (CLAUDE.md rule 4)."""

import json

from tez.core.db import Database
from tez.core.errors import ErrorDetail
from tez.modules.library.models import IdentifierScheme
from tez.modules.library.paper_service import PaperCard, PaperService
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.search.models import SearchRun
from tez.modules.search.repository import SearchRepository
from tez.modules.search.schemas import (
    ResultSource,
    RunView,
    SearchOverview,
    SearchResultRow,
)


def review_exists(db: Database, review_id: str) -> bool:
    with db.session() as session:
        return ReviewsRepository(session).get_review(review_id) is not None


def _error(run: SearchRun) -> ErrorDetail | None:
    return ErrorDetail(**json.loads(run.error)) if run.error else None


def _run_view(run: SearchRun) -> RunView:
    return RunView(
        source=run.source,
        status=run.status,
        translated_query=run.translated_query,
        executed_at=run.executed_at,
        total_reported=run.total_reported,
        retrieved_count=run.retrieved_count,
        error=_error(run),
    )


def overview(db: Database, search_id: str) -> SearchOverview | None:
    with db.session() as session:
        repository = SearchRepository(session)
        runs = repository.runs_of_search(search_id)
        if not runs:
            return None
        query = repository.query_of(runs[0])
        paper_ids = repository.paper_ids_of_search(search_id)
    retrieved = sum(run.retrieved_count for run in runs)
    unique = len(set(paper_ids))
    return SearchOverview(
        search_id=search_id,
        review_id=runs[0].review_id,
        query=query.query_text if query else "",
        runs=[_run_view(run) for run in runs],
        retrieved=retrieved,
        unique=unique,
        duplicates=retrieved - unique,
    )


def _result_row(card: PaperCard, sources: list[ResultSource]) -> SearchResultRow:
    paper = card.paper
    return SearchResultRow(
        paper_id=paper.id,
        title=paper.title,
        first_author=card.first_author.display_name if card.first_author else None,
        author_count=card.author_count,
        year=paper.year,
        venue=paper.venue,
        venue_type=paper.venue_type,
        abstract=paper.abstract,
        citation_count=paper.citation_count,
        doi=card.identifiers.get(IdentifierScheme.DOI),
        arxiv_id=card.identifiers.get(IdentifierScheme.ARXIV),
        url=paper.url,
        oa_url=paper.oa_url,
        language=paper.language,
        is_retracted=paper.retraction_status.value != "none",
        sources=sources,
    )


def result_rows(db: Database, search_id: str) -> list[SearchResultRow]:
    """One row per paper, in the order sources returned them: a paper's best rank first."""
    with db.session() as session:
        repository = SearchRepository(session)
        by_paper: dict[str, list[ResultSource]] = {}
        for run in repository.runs_of_search(search_id):
            for result in repository.results(run.id):
                by_paper.setdefault(result.paper_id, []).append(
                    ResultSource(
                        source=run.source,
                        rank=result.rank,
                        match_method=result.match_method,
                        match_score=result.match_score,
                    )
                )
        cards = PaperService(session).cards(by_paper)
        rows = [_result_row(cards[pid], sources) for pid, sources in by_paper.items()]
    rows.sort(key=lambda row: min(s.rank for s in row.sources))
    return rows
