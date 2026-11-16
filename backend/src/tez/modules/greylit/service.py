"""Grey literature by hand (Task 37, ADR 0025).

A record entered by hand is stored like a one-record import: matched against the library
(so the same thesis found later by a database search is a duplicate, not a second paper),
logged as a `search_run` whose method is its PRISMA box, and taken into the review as a
manual record, ready for screening.
"""

import json
from datetime import UTC, datetime, time
from pathlib import Path

from tez.core.db import Database, utcnow
from tez.core.errors import ErrorCode, TezError
from tez.modules.greylit.schemas import (
    GreyBox,
    GreyEntry,
    GreyKind,
    GreyRecordAdded,
    GreyRecordCreate,
)
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.library.paper_service import PaperService
from tez.modules.reviews import service as reviews_service
from tez.modules.reviews.models import RecordOrigin
from tez.modules.search import queries as search_queries
from tez.modules.search.models import GREY_METHODS, RunMethod
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor
from tez.modules.search.service import ImportRun, store_imported

_BOX_OF_KIND: dict[GreyKind, GreyBox] = {
    GreyKind.THESIS: RunMethod.THESIS,
    GreyKind.REPORT: RunMethod.ORGANISATION,
    GreyKind.REGISTER_RECORD: RunMethod.REGISTER,
    GreyKind.WEB_PAGE: RunMethod.WEBSITE,
}
_VENUE_OF_KIND = {
    GreyKind.THESIS: VenueType.THESIS,
    GreyKind.REPORT: VenueType.REPORT,
    GreyKind.REGISTER_RECORD: VenueType.OTHER,
    GreyKind.WEB_PAGE: VenueType.OTHER,
}


def _author(name: str) -> RecordAuthor:
    """'Family, Given' or 'Given Family', as people type them."""
    if "," in name:
        family, given = (part.strip() for part in name.split(",", 1))
        return RecordAuthor(
            display_name=f"{given} {family}".strip(), family=family, given=given or None
        )
    return RecordAuthor(display_name=name, family=name.rsplit(" ", 1)[-1])


def _record(entry: GreyRecordCreate) -> NormalizedRecord:
    identifiers = {IdentifierScheme.DOI: entry.doi.lower()} if entry.doi else {}
    return NormalizedRecord(
        title=entry.title,
        authors=tuple(_author(name) for name in entry.authors),
        year=entry.year,
        identifiers=identifiers,
        abstract=entry.abstract or None,
        venue=entry.institution or None,
        venue_type=_VENUE_OF_KIND[entry.kind],
        thesis_type=entry.thesis_type if entry.kind is GreyKind.THESIS else None,
        url=entry.url or None,
    )


def add_record(
    db: Database, library_path: Path, review_id: str, entry: GreyRecordCreate
) -> GreyRecordAdded:
    if not reviews_service.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
    box = entry.found_via or _BOX_OF_KIND[entry.kind]
    executed_at = (
        datetime.combine(entry.found_at, time(12), tzinfo=UTC) if entry.found_at else utcnow()
    )
    run = ImportRun(
        review_id=review_id,
        source=entry.source,
        executed_at=executed_at,
        file_name="",
        # The entry as typed is the run's snapshot, like an exported file for an import.
        raw_text=json.dumps(entry.model_dump(mode="json"), ensure_ascii=False, indent=2),
        total_reported=1,
        skipped=0,
        method=box,
    )
    stored = store_imported(db, library_path, [_record(entry)], run)
    [paper_id] = stored.paper_ids
    assert stored.search_id is not None
    selection = reviews_service.add_papers(
        db, review_id, [paper_id], stored.search_id, origin=RecordOrigin.MANUAL
    )
    return GreyRecordAdded(
        paper_id=paper_id,
        search_id=stored.search_id,
        found_via=box,
        matched_existing=stored.new_papers == 0,
        added_to_review=selection.added == 1,
    )


def entries(db: Database, review_id: str) -> list[GreyEntry]:
    """The review's grey-literature runs, newest first, with their records' titles."""
    if not reviews_service.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
    runs = search_queries.runs_by_method(db, review_id, GREY_METHODS)
    with db.session() as session:
        cards = PaperService(session).cards({p for run in runs for p in run.paper_ids})
        titles = {paper_id: card.paper.title for paper_id, card in cards.items()}
    return [
        GreyEntry(
            search_id=run.search_id or run.id,
            found_via=run.method,
            source=run.source,
            executed_at=run.executed_at,
            file_name=run.file_name or None,
            records=len(run.paper_ids),
            titles=[titles[p] for p in run.paper_ids if p in titles],
        )
        for run in reversed(runs)
    ]
