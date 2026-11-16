"""Reading searches back for the API. Every count is derived, never stored (CLAUDE.md rule 4)."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from tez.core.db import Database
from tez.core.errors import ErrorDetail
from tez.modules.library.models import IdentifierScheme
from tez.modules.library.paper_service import PaperCard, PaperService
from tez.modules.reviews.service import paper_ids_in_review
from tez.modules.search.models import RunMethod, RunStatus, SearchRun
from tez.modules.search.repository import SearchRepository
from tez.modules.search.schemas import (
    ResultSource,
    RunView,
    SearchOverview,
    SearchResultRow,
)


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


def _overview(session: Session, search_id: str) -> SearchOverview | None:
    repository = SearchRepository(session)
    runs = repository.runs_of_search(search_id)
    if not runs:
        return None
    first = runs[0]
    query = repository.query_of(first)
    paper_ids = set(repository.paper_ids_of_search(search_id))
    retrieved = sum(run.retrieved_count for run in runs)
    return SearchOverview(
        search_id=search_id,
        review_id=first.review_id,
        query=query.query_text if query else (first.translated_query or ""),
        file_name=first.file_name,
        filters=query.filters_json if query else None,
        initiated_via=first.initiated_via,
        started_at=first.executed_at,
        runs=[_run_view(run) for run in runs],
        retrieved=retrieved,
        unique=len(paper_ids),
        duplicates=retrieved - len(paper_ids),
        in_library=sum(
            card.paper.library_added_at is not None
            for card in PaperService(session).cards(paper_ids).values()
        ),
    )


def overview(db: Database, search_id: str) -> SearchOverview | None:
    with db.session() as session:
        return _overview(session, search_id)


def history(db: Database, review_id: str) -> list[SearchOverview]:
    with db.session() as session:
        found = (_overview(session, i) for i in SearchRepository(session).search_ids(review_id))
        return [item for item in found if item is not None]


def _result_row(
    card: PaperCard, sources: list[ResultSource], *, in_review: bool
) -> SearchResultRow:
    paper = card.paper
    return SearchResultRow(
        paper_id=paper.id,
        title=paper.title,
        first_author=card.first_author.display_name if card.first_author else None,
        author_count=card.author_count,
        year=paper.year,
        venue=paper.venue,
        venue_type=paper.venue_type,
        thesis_type=paper.thesis_type,
        abstract=paper.abstract,
        citation_count=paper.citation_count,
        doi=card.identifiers.get(IdentifierScheme.DOI),
        arxiv_id=card.identifiers.get(IdentifierScheme.ARXIV),
        url=paper.url,
        oa_url=paper.oa_url,
        language=paper.language,
        is_retracted=paper.retraction_status.value != "none",
        in_library=paper.library_added_at is not None,
        in_review=in_review,
        sources=sources,
    )


def result_rows(db: Database, search_id: str) -> list[SearchResultRow]:
    """One row per paper, in the order sources returned them: a paper's best rank first."""
    with db.session() as session:
        repository = SearchRepository(session)
        by_paper: dict[str, list[ResultSource]] = {}
        runs = repository.runs_of_search(search_id)
        for run in runs:
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
        in_review = paper_ids_in_review(db, runs[0].review_id) if runs else set[str]()
        rows = [
            _result_row(cards[pid], sources, in_review=pid in in_review)
            for pid, sources in by_paper.items()
        ]
    rows.sort(key=lambda row: min(s.rank for s in row.sources))
    return rows


@dataclass(frozen=True)
class RunFacts:
    """A recorded run and the papers it found, for modules that count them (PRISMA)."""

    id: str
    search_id: str | None
    source: str
    method: RunMethod
    snowball_round: int | None
    seed_paper_id: str | None
    status: RunStatus
    error: ErrorDetail | None
    executed_at: datetime
    translated_query: str | None
    total_reported: int | None
    # In rank order; a paper the source sent twice is here twice.
    paper_ids: tuple[str, ...]


def runs_by_method(db: Database, review_id: str, methods: Sequence[RunMethod]) -> list[RunFacts]:
    """The review's runs of the given kinds, oldest first."""
    with db.session() as session:
        repository = SearchRepository(session)
        runs = repository.runs_by_method(review_id, methods)
        papers = repository.result_papers([run.id for run in runs])
        return [
            RunFacts(
                id=run.id,
                search_id=run.search_id,
                source=run.source,
                method=run.method,
                snowball_round=run.snowball_round,
                seed_paper_id=run.seed_paper_id,
                status=run.status,
                error=_error(run),
                executed_at=run.executed_at,
                translated_query=run.translated_query,
                total_reported=run.total_reported,
                paper_ids=tuple(papers[run.id]),
            )
            for run in runs
        ]
