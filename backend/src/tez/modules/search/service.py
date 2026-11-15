"""Federated search: ask every source at once and record what each one said (plan, Task 13).

Each source's answer is written as soon as it arrives, in its own transaction, so one source
failing, or the process stopping, cannot lose what the others returned. A failure is recorded
too, as a run with an error: the systematic record must show that a source was asked.
"""

import asyncio
import gzip
import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tez.core.db import Database, utcnow
from tez.core.errors import ErrorCode, TezError
from tez.modules.library.models import IdentifierScheme
from tez.modules.library.paper_service import PaperCard, PaperService
from tez.modules.library.repository import AuthorInput
from tez.modules.search.dedup import (
    Candidate,
    PaperIndex,
    candidate_from,
    family_name,
    is_preprint_type,
    normalized_identifiers,
)
from tez.modules.search.models import InitiatedVia, MatchMethod, RunStatus, SearchRun
from tez.modules.search.providers.base import ProviderResult, SearchProvider, SearchRequest
from tez.modules.search.repository import ResultInput, SearchRepository
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor, SourceState
from tez.shared.ids import new_id

logger = logging.getLogger(__name__)

SNAPSHOT_FOLDER = "snapshots"


@dataclass(frozen=True)
class SourceUpdate:
    source: str
    state: SourceState
    retrieved: int | None = None
    total_reported: int | None = None
    wait_seconds: float | None = None
    error_code: str | None = None


Listener = Callable[[SourceUpdate], None]


def _ignore(_: SourceUpdate) -> None:
    pass


def _candidate(card: PaperCard) -> Candidate:
    first = card.first_author
    author = RecordAuthor(display_name=first.display_name, family=first.family) if first else None
    return Candidate(
        paper_id=card.paper.id,
        identifiers=card.identifiers,
        title_norm=card.paper.title_norm,
        year=card.paper.year,
        first_author=family_name(author) if author else None,
        is_preprint=is_preprint_type(card.paper.venue_type, card.identifiers),
    )


def _paper_fields(record: NormalizedRecord) -> dict[str, Any]:
    return {
        "abstract": record.abstract,
        "year": record.year,
        "venue": record.venue,
        "venue_type": record.venue_type,
        "thesis_type": record.thesis_type,
        "volume": record.volume,
        "issue": record.issue,
        "pages": record.pages,
        "language": record.language,
        "url": record.url,
        "oa_url": record.oa_url,
        "citation_count": record.citation_count,
        "is_retracted": record.is_retracted,
    }


def _authors(record: NormalizedRecord) -> list[AuthorInput]:
    return [
        AuthorInput(
            display_name=a.display_name,
            family=a.family,
            given=a.given,
            orcid=a.orcid,
            affiliation_raw=a.affiliation,
        )
        for a in record.authors
    ]


def _store_records(
    papers: PaperService, index: PaperIndex, records: Sequence[NormalizedRecord]
) -> list[ResultInput]:
    """Match each record, creating or enriching papers. Identifiers are stored normalized."""
    results: list[ResultInput] = []
    for record in records:
        match = index.match(record)
        identifiers = normalized_identifiers(record)
        if match.paper_id is None:
            paper_id = _create_paper(papers, index, record, identifiers, match.version_of)
            results.append(ResultInput(paper_id, MatchMethod.NEW))
            continue
        _enrich(papers, index, match.paper_id, record, identifiers)
        results.append(ResultInput(match.paper_id, match.method, match.score))
    return results


def _create_paper(
    papers: PaperService,
    index: PaperIndex,
    record: NormalizedRecord,
    identifiers: dict[IdentifierScheme, str],
    version_of: str | None,
) -> str:
    # An identifier may already belong to another paper when the record matched nothing by DOI
    # but the source holds several ids; the unique constraint must not lose the whole run.
    free = {s: v for s, v in identifiers.items() if not index.knows(s, v)}
    paper = papers.add(
        record.title, identifiers=free, authors=_authors(record), **_paper_fields(record)
    )
    candidate = candidate_from(paper.id, record)
    index.add(candidate)
    if version_of is not None:
        if candidate.is_preprint:
            papers.link_versions(paper.id, version_of)
        else:
            papers.link_versions(version_of, paper.id)
    return paper.id


def _enrich(
    papers: PaperService,
    index: PaperIndex,
    paper_id: str,
    record: NormalizedRecord,
    identifiers: dict[IdentifierScheme, str],
) -> None:
    free = {s: v for s, v in identifiers.items() if not index.knows(s, v)}
    papers.fill_missing(paper_id, identifiers=free, **_paper_fields(record))
    index.add_identifiers(paper_id, free)


def _write_snapshot(
    library_path: Path, result: ProviderResult, executed_at: datetime
) -> str | None:
    """Keep the raw answer, for reproducibility. Failing to write it must not lose the run."""
    if not result.raw_pages:
        return None
    document = {
        "source": result.source,
        "translated_query": result.translated_query,
        "executed_at": executed_at.isoformat(),
        "pages": result.raw_pages,
    }
    return _write_snapshot_document(library_path, document)


def _write_snapshot_document(library_path: Path, document: dict[str, Any]) -> str | None:
    relative = Path(SNAPSHOT_FOLDER) / f"{new_id()}.json.gz"
    try:
        with gzip.open(library_path / relative, "wt", encoding="utf-8") as file:
            json.dump(document, file, ensure_ascii=False)
    except OSError as exc:
        source = document.get("source")
        logger.warning("snapshot not written", extra={"source": source, "error": repr(exc)})
        return None
    return relative.as_posix()


def _error_text(error: TezError | None) -> str | None:
    if error is None:
        return None
    return json.dumps({"code": error.code.value, "params": error.params}, default=str)


@dataclass(frozen=True)
class _Recorded:
    retrieved: int
    status: RunStatus
    result: ProviderResult


@dataclass(frozen=True)
class _Plan:
    search_id: str
    review_id: str
    query_id: str | None
    initiated_via: InitiatedVia


def _write_run(
    session: Session,
    plan: _Plan,
    result: ProviderResult,
    executed_at: datetime,
    snapshot: str | None,
    index: PaperIndex,
) -> SearchRun:
    results = _store_records(PaperService(session), index, result.records)
    return SearchRepository(session).add_run(
        plan.review_id,
        search_id=plan.search_id,
        source=result.source,
        executed_at=executed_at,
        initiated_via=plan.initiated_via,
        status=result.status,
        results=results,
        query_id=plan.query_id,
        translated_query=result.translated_query,
        total_reported=result.total_reported,
        error=_error_text(result.error),
        snapshot_path=snapshot,
    )


def _record(
    db: Database,
    library_path: Path,
    plan: _Plan,
    result: ProviderResult,
    executed_at: datetime,
    index: PaperIndex,
) -> _Recorded:
    snapshot = _write_snapshot(library_path, result, executed_at)
    try:
        with db.write_session() as session:
            run = _write_run(session, plan, result, executed_at, snapshot, index)
            return _Recorded(run.retrieved_count, run.status, result)
    except SQLAlchemyError:
        logger.exception("search results not stored", extra={"source": result.source})
    # Nothing of that transaction remains, so the index must forget its papers too. The run
    # itself must still be on record.
    with db.session() as session:
        index.reload(_candidate(card) for card in PaperService(session).all_cards())
    failure = TezError(ErrorCode.INTERNAL_UNEXPECTED, {"source": result.source})
    failed = ProviderResult(
        source=result.source,
        translated_query=result.translated_query,
        total_reported=result.total_reported,
        error=failure,
    )
    with db.write_session() as session:
        _write_run(session, plan, failed, executed_at, snapshot, index)
    return _Recorded(0, RunStatus.ERROR, failed)


_STATES = {
    RunStatus.OK: SourceState.DONE,
    RunStatus.PARTIAL: SourceState.PARTIAL,
    RunStatus.ERROR: SourceState.FAILED,
}


async def _ask(
    provider: SearchProvider, request: SearchRequest, listener: Listener
) -> tuple[ProviderResult, datetime]:
    """One source's answer. Whatever goes wrong in there stays in there."""
    name = provider.name
    executed_at = utcnow()
    listener(SourceUpdate(name, SourceState.SEARCHING))

    def on_wait(seconds: float) -> None:
        listener(SourceUpdate(name, SourceState.RATE_LIMITED, wait_seconds=seconds))

    try:
        return await provider.search(request, on_wait=on_wait), executed_at
    except Exception as exc:  # A bug in one source must not stop the others.
        logger.exception("source crashed", extra={"source": name})
        error = TezError(ErrorCode.INTERNAL_UNEXPECTED, {"source": name, "error": repr(exc)})
        return ProviderResult(name, request.query, error=error), executed_at


def _prepare(
    db: Database, review_id: str, request: SearchRequest, search_id: str, via: InitiatedVia
) -> tuple[_Plan, PaperIndex]:
    filters: dict[str, Any] = {"year_from": request.year_from, "year_to": request.year_to}
    if request.theses_only:
        filters["theses_only"] = True
    with db.write_session() as session:
        query = SearchRepository(session).find_or_add_query(review_id, request.query, filters)
        plan = _Plan(search_id, review_id, query.id, via)
        index = PaperIndex(_candidate(card) for card in PaperService(session).all_cards())
    return plan, index


async def run_search(
    db: Database,
    library_path: Path,
    review_id: str,
    request: SearchRequest,
    providers: Sequence[SearchProvider],
    *,
    search_id: str | None = None,
    initiated_via: InitiatedVia = InitiatedVia.GUI,
    listener: Listener = _ignore,
) -> str:
    """Ask all `providers` in parallel and record each answer. Returns the search id."""
    search_id = search_id or new_id()
    for provider in providers:
        listener(SourceUpdate(provider.name, SourceState.WAITING))
    plan, index = await asyncio.to_thread(
        _prepare, db, review_id, request, search_id, initiated_via
    )
    pending = [asyncio.create_task(_ask(p, request, listener)) for p in providers]
    try:
        # One at a time: papers made from one source's answer must be matched by the next.
        for finished in asyncio.as_completed(pending):
            result, executed_at = await finished
            recorded = await asyncio.to_thread(
                _record, db, library_path, plan, result, executed_at, index
            )
            final = recorded.result
            listener(
                SourceUpdate(
                    final.source,
                    _STATES[recorded.status],
                    retrieved=recorded.retrieved,
                    total_reported=final.total_reported,
                    error_code=final.error.code.value if final.error else None,
                )
            )
    finally:
        for task in pending:
            task.cancel()
    return search_id


# --- imported search results (Task 15) -----------------------------------------------

_IN_FILE = "file:"


@dataclass(frozen=True)
class PreviewMatch:
    """What importing one record would do, worked out without writing anything."""

    method: MatchMethod
    # The known paper it matches; None when it is new or repeats an earlier record of the file.
    paper_id: str | None = None
    in_library: bool = False
    # Index of the earlier record of the same file that this one repeats.
    repeats: int | None = None


def preview_matches(db: Database, records: Sequence[NormalizedRecord]) -> list[PreviewMatch]:
    """Match records the way an import would: against known papers, then each other."""
    with db.session() as session:
        cards = PaperService(session).all_cards()
    index = PaperIndex(_candidate(card) for card in cards)
    kept = {card.paper.id for card in cards if card.paper.library_added_at is not None}
    matches: list[PreviewMatch] = []
    for position, record in enumerate(records):
        match = index.match(record)
        if match.paper_id is None:
            index.add(candidate_from(f"{_IN_FILE}{position}", record))
            matches.append(PreviewMatch(MatchMethod.NEW))
        elif match.paper_id.startswith(_IN_FILE):
            earlier = int(match.paper_id.removeprefix(_IN_FILE))
            matches.append(PreviewMatch(match.method, repeats=earlier))
        else:
            in_library = match.paper_id in kept
            matches.append(PreviewMatch(match.method, match.paper_id, in_library))
    return matches


@dataclass(frozen=True)
class ImportRun:
    """How an import is logged as a search: where the export came from and when."""

    review_id: str
    source: str
    executed_at: datetime
    file_name: str
    raw_text: str
    total_reported: int
    skipped: int
    query: str | None = None
    # The saved external search this import is a run of (Task 27).
    query_id: str | None = None
    initiated_via: InitiatedVia = InitiatedVia.GUI


@dataclass(frozen=True)
class ImportedRecords:
    # One per record, in file order; a repeated record repeats its paper.
    paper_ids: list[str]
    new_papers: int
    search_id: str | None = None


def store_imported(
    db: Database,
    library_path: Path,
    records: Sequence[NormalizedRecord],
    run: ImportRun | None = None,
) -> ImportedRecords:
    """Match imported records like a source's answer, and log them as a search run if asked.

    One transaction: an import is one file, so it is recorded whole or not at all.
    """
    search_id = new_id() if run is not None else None
    snapshot = _import_snapshot(library_path, run) if run is not None else None
    with db.write_session() as session:
        papers = PaperService(session)
        index = PaperIndex(_candidate(card) for card in papers.all_cards())
        results = _store_records(papers, index, records)
        if run is not None:
            error = None
            if run.skipped:
                error = TezError(ErrorCode.IMPORT_ENTRIES_SKIPPED, {"skipped": run.skipped})
            SearchRepository(session).add_run(
                run.review_id,
                search_id=search_id,
                source=run.source,
                executed_at=run.executed_at,
                initiated_via=run.initiated_via,
                status=RunStatus.PARTIAL if error else RunStatus.OK,
                results=results,
                query_id=run.query_id,
                translated_query=run.query,
                total_reported=run.total_reported,
                error=_error_text(error),
                snapshot_path=snapshot,
                file_name=run.file_name,
            )
    return ImportedRecords(
        paper_ids=[result.paper_id for result in results],
        new_papers=sum(result.match_method is MatchMethod.NEW for result in results),
        search_id=search_id,
    )


def _import_snapshot(library_path: Path, run: ImportRun) -> str | None:
    """The exported file as it was, so the run can be checked against it later."""
    document = {
        "source": run.source,
        "file_name": run.file_name,
        "query": run.query,
        "executed_at": run.executed_at.isoformat(),
        "imported_at": utcnow().isoformat(),
        "content": run.raw_text,
    }
    return _write_snapshot_document(library_path, document)
