"""Saved external searches: a database without an open API, and the query run on its site.

The user runs the query at the database, exports the results and imports the file (Task 15).
Each import is one more `search_run` of the saved search, so PRISMA counts every one of
them, and an import can say how many of its records no earlier import found (Task 27).
"""

from collections.abc import Sequence

from sqlalchemy.orm import Session

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.reviews import service as reviews_service
from tez.modules.search.models import SearchQuery
from tez.modules.search.repository import SearchRepository
from tez.modules.search.schemas import ExternalSearchCreate, ExternalSearchView, SinceLastImport


def _view(repository: SearchRepository, query: SearchQuery) -> ExternalSearchView:
    runs = repository.runs_of_query(query.id)
    last = runs[-1] if runs else None
    return ExternalSearchView(
        id=query.id,
        review_id=query.review_id,
        name=query.name,
        source=query.external_source or "",
        query=query.query_text,
        created_at=query.created_at,
        imports=len(runs),
        last_searched_at=last.executed_at if last else None,
        last_retrieved=last.retrieved_count if last else None,
    )


def save(db: Database, body: ExternalSearchCreate) -> ExternalSearchView:
    """Save the search; the same database and query in a review stay one saved search."""
    if not reviews_service.review_exists(db, body.review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": body.review_id}, status=404)
    with db.write_session() as session:
        repository = SearchRepository(session)
        for query in repository.external_queries(body.review_id):
            if query.external_source == body.source and query.query_text == body.query:
                return _view(repository, query)
        query = repository.add_query(
            body.review_id, body.name or body.query, body.query, external_source=body.source
        )
        return _view(repository, query)


def list_saved(db: Database, review_id: str) -> list[ExternalSearchView]:
    with db.session() as session:
        repository = SearchRepository(session)
        return [_view(repository, query) for query in repository.external_queries(review_id)]


def _get(session: Session, saved_search_id: str, review_id: str | None) -> SearchQuery:
    query = SearchRepository(session).get_query(saved_search_id)
    if (
        query is None
        or query.external_source is None
        or (review_id is not None and query.review_id != review_id)
    ):
        params = {"saved_search_id": saved_search_id}
        raise TezError(ErrorCode.EXTERNAL_SEARCH_NOT_FOUND, params, status=404)
    return query


class EarlierImports:
    """What the earlier imports of a saved search found, to compare a new import with."""

    def __init__(self, db: Database, saved_search_id: str, review_id: str | None = None) -> None:
        with db.session() as session:
            query = _get(session, saved_search_id, review_id)
            repository = SearchRepository(session)
            runs = repository.runs_of_query(query.id)
            self.review_id = query.review_id
            self.source = query.external_source or ""
            self.query = query.query_text
            self._last = runs[-1].executed_at if runs else None
            self._found = repository.paper_ids_of_query(query.id)

    def compare(self, paper_ids: Sequence[str | None]) -> SinceLastImport | None:
        """`paper_ids`: one per record, a repeat within the file left out; None for a paper
        the library does not know yet."""
        if self._last is None:
            return None
        known = {pid for pid in paper_ids if pid is not None}
        unknown = sum(pid is None for pid in paper_ids)
        return SinceLastImport(last_searched_at=self._last, new=len(known - self._found) + unknown)
