from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from tez.modules.search.models import (
    InitiatedVia,
    MatchMethod,
    RunStatus,
    SearchQuery,
    SearchResult,
    SearchRun,
)


@dataclass(frozen=True)
class ResultInput:
    paper_id: str
    match_method: MatchMethod
    match_score: float | None = None


class SearchRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_query(
        self,
        review_id: str,
        name: str,
        query_text: str,
        filters_json: dict[str, Any] | None = None,
    ) -> SearchQuery:
        query = SearchQuery(
            review_id=review_id, name=name, query_text=query_text, filters_json=filters_json
        )
        self.session.add(query)
        self.session.flush()
        return query

    def find_or_add_query(
        self, review_id: str, query_text: str, filters_json: dict[str, Any] | None
    ) -> SearchQuery:
        """The same query with the same filters in a review stays one row."""
        for query in self.queries(review_id):
            if query.query_text == query_text and query.filters_json == filters_json:
                return query
        return self.add_query(review_id, query_text, query_text, filters_json)

    def queries(self, review_id: str) -> list[SearchQuery]:
        return list(
            self.session.scalars(
                select(SearchQuery)
                .where(SearchQuery.review_id == review_id)
                .order_by(SearchQuery.created_at, SearchQuery.id)
            )
        )

    def add_run(
        self,
        review_id: str,
        *,
        source: str,
        executed_at: datetime,
        initiated_via: InitiatedVia,
        status: RunStatus,
        results: Sequence[ResultInput],
        query_id: str | None = None,
        search_id: str | None = None,
        translated_query: str | None = None,
        total_reported: int | None = None,
        error: str | None = None,
        snapshot_path: str | None = None,
    ) -> SearchRun:
        """Write a finished run and its results at once; neither changes afterwards."""
        run = SearchRun(
            review_id=review_id,
            query_id=query_id,
            search_id=search_id,
            source=source,
            translated_query=translated_query,
            executed_at=executed_at,
            initiated_via=initiated_via,
            total_reported=total_reported,
            retrieved_count=len(results),
            status=status,
            error=error,
            snapshot_path=snapshot_path,
        )
        self.session.add(run)
        self.session.flush()
        self.session.add_all(
            SearchResult(
                run_id=run.id,
                rank=rank,
                paper_id=r.paper_id,
                match_method=r.match_method,
                match_score=r.match_score,
            )
            for rank, r in enumerate(results, start=1)
        )
        self.session.flush()
        return run

    def runs(self, review_id: str) -> list[SearchRun]:
        return list(
            self.session.scalars(
                select(SearchRun)
                .where(SearchRun.review_id == review_id)
                .order_by(SearchRun.executed_at, SearchRun.id)
            )
        )

    def runs_of_search(self, search_id: str) -> list[SearchRun]:
        return list(
            self.session.scalars(
                select(SearchRun)
                .where(SearchRun.search_id == search_id)
                .order_by(SearchRun.executed_at, SearchRun.id)
            )
        )

    def query_of(self, run: SearchRun) -> SearchQuery | None:
        return self.session.get(SearchQuery, run.query_id) if run.query_id else None

    def paper_ids_of_search(self, search_id: str) -> list[str]:
        return list(
            self.session.scalars(
                select(SearchResult.paper_id)
                .join(SearchRun, SearchResult.run_id == SearchRun.id)
                .where(SearchRun.search_id == search_id)
            )
        )

    def results(self, run_id: str) -> list[SearchResult]:
        return list(
            self.session.scalars(
                select(SearchResult)
                .where(SearchResult.run_id == run_id)
                .order_by(SearchResult.rank)
            )
        )
