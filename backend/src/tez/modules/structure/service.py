"""A paper's structure from GROBID (Task 56, ADR 0037).

Optional: with no GROBID address in the settings, nothing here runs and the app hides it. A
reading is a worker job; it sends the PDF to GROBID on this computer, keeps the sections and
the references (matched to library papers by DOI, then by folded title), and records a failure
instead of raising it into the reader.
"""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tez.core.db import Database, utcnow
from tez.core.errors import ErrorCode, TezError
from tez.modules.files import service as files_service
from tez.modules.jobs import service as jobs_service
from tez.modules.jobs.registry import JobContext
from tez.modules.library.paper_service import PaperService
from tez.modules.settings import service as settings_service
from tez.modules.structure import grobid, tei
from tez.modules.structure.models import DocumentSection, ReferenceEntry, StructureRead
from tez.modules.structure.schemas import (
    ReferenceView,
    SectionView,
    StructureQueued,
    StructureView,
)

log = logging.getLogger(__name__)

READ_JOB = "grobid.read"
# Behind text extraction, ahead of nothing urgent.
_PRIORITY = -5
_RETRY_AFTER = timedelta(seconds=0)


def configured_url(db: Database) -> str | None:
    return settings_service.read_settings(db).grobid_url


def _require_grobid(db: Database) -> str:
    url = configured_url(db)
    if url is None:
        raise TezError(ErrorCode.GROBID_OFF, status=409)
    return url


def queue_read(db: Database, attachment_id: str) -> StructureQueued:
    _require_grobid(db)
    files_service.get_attachment(db, attachment_id)
    with db.write_session() as session:
        job_id = jobs_service.enqueue(
            session,
            READ_JOB,
            {"attachment_id": attachment_id},
            dedupe_key=f"grobid:{attachment_id}",
            priority=_PRIORITY,
            max_attempts=1,
        )
    return StructureQueued(job_id=job_id)


def structure(db: Database, attachment_id: str) -> StructureView:
    files_service.get_attachment(db, attachment_id)
    with db.session() as session:
        read = session.scalars(
            select(StructureRead).where(StructureRead.attachment_id == attachment_id)
        ).one_or_none()
        sections = session.scalars(
            select(DocumentSection)
            .where(DocumentSection.attachment_id == attachment_id)
            .order_by(DocumentSection.ord)
        )
        references = session.scalars(
            select(ReferenceEntry)
            .where(ReferenceEntry.attachment_id == attachment_id)
            .order_by(ReferenceEntry.ord)
        )
        return StructureView(
            read_at=read.read_at if read else None,
            error=read.error if read else None,
            sections=[
                SectionView(
                    type=s.type, heading=s.heading, page_start=s.page_start, page_end=s.page_end
                )
                for s in sections
            ],
            references=[_reference_view(r) for r in references],
        )


def _reference_view(entry: ReferenceEntry) -> ReferenceView:
    parsed: dict[str, Any] = entry.parsed_json
    return ReferenceView(
        ord=entry.ord,
        raw_text=entry.raw_text,
        title=parsed.get("title"),
        authors=list(parsed.get("authors") or []),
        year=parsed.get("year"),
        doi=parsed.get("doi"),
        page=parsed.get("page"),
        matched_paper_id=entry.matched_paper_id,
    )


def _record(session: Session, attachment_id: str, error: str | None) -> None:
    read = session.scalars(
        select(StructureRead).where(StructureRead.attachment_id == attachment_id)
    ).one_or_none()
    if read is None:
        read = StructureRead(attachment_id=attachment_id)
        session.add(read)
    read.error = error
    if error is None:
        read.read_at = utcnow()
    session.flush()


def _store(session: Session, attachment_id: str, found: tei.Structure) -> None:
    session.execute(delete(DocumentSection).where(DocumentSection.attachment_id == attachment_id))
    session.execute(delete(ReferenceEntry).where(ReferenceEntry.attachment_id == attachment_id))
    for ord_, section in enumerate(found.sections):
        session.add(
            DocumentSection(
                attachment_id=attachment_id,
                ord=ord_,
                type=section.type,
                heading=section.heading[:500],
                page_start=section.page_start,
                page_end=section.page_end,
            )
        )
    papers = PaperService(session)
    for ord_, reference in enumerate(found.references):
        matched = papers.match(reference.doi, reference.title)
        session.add(
            ReferenceEntry(
                attachment_id=attachment_id,
                ord=ord_,
                raw_text=reference.raw_text[:4000],
                parsed_json={
                    "title": reference.title,
                    "authors": reference.authors,
                    "year": reference.year,
                    "doi": reference.doi,
                    "page": reference.page,
                },
                matched_paper_id=matched[0] if matched else None,
                match_score=matched[1] if matched else None,
            )
        )
    session.flush()


def read_structure(payload: dict[str, object], ctx: JobContext) -> None:
    """The `grobid.read` job. A failure is recorded on the file for the reader to show."""
    attachment_id = str(payload["attachment_id"])
    url = configured_url(ctx.db)
    with ctx.db.session() as session:
        rel_path = files_service.rel_path(session, attachment_id)
    if url is None or rel_path is None:
        return
    try:
        pdf = (ctx.library_path / rel_path).read_bytes()
        found = tei.parse(grobid.client_for(url).process(pdf))
    except TezError as error:
        log.info("grobid could not read a file", extra={"id": attachment_id, "code": error.code})
        with ctx.db.write_session() as session:
            _record(session, attachment_id, error.code.value)
        return
    except (OSError, ValueError):
        log.warning("grobid reading failed", extra={"id": attachment_id}, exc_info=True)
        with ctx.db.write_session() as session:
            _record(session, attachment_id, ErrorCode.GROBID_FAILED.value)
        return
    with ctx.db.write_session() as session:
        _store(session, attachment_id, found)
        _record(session, attachment_id, None)
    ctx.report(1.0)
