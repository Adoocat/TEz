"""Adding PDFs to the library (plan, Task 16) and inspecting them in the worker.

A new PDF is stored under its hash, gets an `attachment` row and, unless it belongs to a paper
already, a new paper in the inbox. The API never opens the PDF itself: a `pdf.inspect` job in
the worker counts its pages and checks for a text layer, so a file that crashes PDFium takes
down only the worker. A broken file is marked `failed`, with a reason, and nothing else stops.
"""

import json
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePath

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tez.core.db import Database
from tez.core.errors import ErrorCode, ErrorDetail, TezError
from tez.modules.files import storage
from tez.modules.files.inspection import inspect_pdf
from tez.modules.files.models import Attachment, AttachmentKind, TextStatus
from tez.modules.files.repository import FilesRepository
from tez.modules.files.schemas import (
    MAX_PDF_BYTES,
    AttachmentView,
    PdfAdded,
    PdfPathResult,
)
from tez.modules.jobs import service as jobs_service
from tez.modules.jobs.registry import JobContext
from tez.modules.library.paper_service import PaperService

logger = logging.getLogger(__name__)

INSPECT_JOB = "pdf.inspect"
EXTRACT_JOB = "pdf.extract_text"
# Raised when the extractor changes: files read by an older one are read again (Task 43).
TEXT_VERSION = 1
# Reading every page can wait for what the user is watching (new files, fetches).
_EXTRACT_PRIORITY = -10
MANUAL_SOURCE = "manual"
# SQLite allows a limited number of query parameters; long id lists go in batches.
_BATCH = 500


def _title_from(file_name: str) -> str:
    """A stand-in title until metadata is known: "smith_2024-code-review.pdf" -> words."""
    stem = PurePath(file_name).stem
    words = " ".join(stem.replace("_", " ").replace("-", " ").split())
    return words or file_name


def _error(text: str | None) -> ErrorDetail | None:
    return ErrorDetail.model_validate(json.loads(text)) if text else None


def view(attachment: Attachment) -> AttachmentView:
    return AttachmentView(
        id=attachment.id,
        paper_id=attachment.paper_id,
        kind=attachment.kind,
        file_name=attachment.file_name,
        sha256=attachment.sha256,
        size=attachment.size,
        page_count=attachment.page_count,
        text_status=attachment.text_status,
        error=_error(attachment.error),
        source=attachment.source,
        created_at=attachment.created_at,
    )


@dataclass(frozen=True)
class _Existing:
    paper_id: str
    attachment_id: str


def _existing(db: Database, sha256: str) -> _Existing | None:
    with db.session() as session:
        found = FilesRepository(session).find_by_sha256(sha256)
        return _Existing(found.paper_id, found.id) if found else None


def _check_pdf(data: bytes, file_name: str) -> None:
    if len(data) > MAX_PDF_BYTES:
        params = {"file_name": file_name, "size": len(data)}
        raise TezError(ErrorCode.PDF_TOO_LARGE, params, status=413)
    if not storage.looks_like_pdf(data):
        raise TezError(ErrorCode.PDF_NOT_A_PDF, {"file_name": file_name}, status=422)


def add_pdf(
    db: Database,
    library_path: Path,
    data: bytes,
    file_name: str,
    *,
    paper_id: str | None = None,
    source: str = MANUAL_SOURCE,
) -> PdfAdded:
    """Store a PDF once. The same bytes a second time change nothing (`duplicate`)."""
    _check_pdf(data, file_name)
    sha256 = storage.sha256_of(data)
    if (existing := _existing(db, sha256)) is not None:
        return _duplicate(existing, file_name)

    relative = storage.store(library_path, data, sha256)
    try:
        with db.write_session() as session:
            papers = PaperService(session)
            if paper_id is None:
                paper = papers.add(_title_from(file_name), identifiers={}, authors=[])
                papers.keep([paper.id])
                papers.put_in_inbox(paper.id)
                owner = paper.id
            else:
                if not papers.existing_ids([paper_id]):
                    raise TezError(ErrorCode.PAPER_NOT_FOUND, {"paper_ids": [paper_id]}, status=404)
                owner = paper_id
            attachment = FilesRepository(session).add_attachment(
                owner,
                rel_path=relative,
                sha256=sha256,
                source=source,
                file_name=file_name,
                size=len(data),
            )
            job_id = jobs_service.enqueue(
                session, INSPECT_JOB, {"attachment_id": attachment.id}, dedupe_key=attachment.id
            )
    except IntegrityError:
        # Another request stored the same bytes between our check and our insert.
        existing = _existing(db, sha256)
        if existing is None:
            raise
        return _duplicate(existing, file_name)
    logger.info("pdf added", extra={"attachment_id": attachment.id, "size": len(data)})
    return PdfAdded(
        status="added",
        paper_id=owner,
        attachment_id=attachment.id,
        job_id=job_id,
        file_name=file_name,
    )


def _duplicate(existing: _Existing, file_name: str) -> PdfAdded:
    return PdfAdded(
        status="duplicate",
        paper_id=existing.paper_id,
        attachment_id=existing.attachment_id,
        job_id=None,
        file_name=file_name,
    )


def add_pdf_from_path(
    db: Database, library_path: Path, path: Path, *, paper_id: str | None = None
) -> PdfAdded:
    """A file on this computer: the desktop app's drops and `tez <file.pdf>`."""
    try:
        size = path.stat().st_size
        if size > MAX_PDF_BYTES:
            params = {"file_name": path.name, "size": size}
            raise TezError(ErrorCode.PDF_TOO_LARGE, params, status=413)
        data = path.read_bytes()
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError, PermissionError) as exc:
        raise TezError(ErrorCode.PDF_FILE_NOT_FOUND, {"path": str(path)}, status=404) from exc
    return add_pdf(db, library_path, data, path.name, paper_id=paper_id)


def add_pdfs_from_paths(
    db: Database, library_path: Path, paths: list[str], *, paper_id: str | None = None
) -> list[PdfPathResult]:
    """Each file on its own: one missing or broken file does not stop the others."""
    results: list[PdfPathResult] = []
    for text in paths:
        try:
            added = add_pdf_from_path(db, library_path, Path(text), paper_id=paper_id)
        except TezError as error:
            detail = ErrorDetail(code=error.code.value, params=error.params)
            results.append(PdfPathResult(path=text, error=detail))
        else:
            results.append(PdfPathResult(path=text, added=added))
    return results


def attachments_of(db: Database, paper_id: str) -> list[AttachmentView]:
    with db.session() as session:
        return attachments_in(session, paper_id)


def attachments_in(session: Session, paper_id: str) -> list[AttachmentView]:
    return [view(a) for a in FilesRepository(session).for_paper(paper_id)]


def get_attachment(db: Database, attachment_id: str) -> AttachmentView:
    with db.session() as session:
        attachment = FilesRepository(session).get(attachment_id)
        if attachment is None:
            params = {"attachment_id": attachment_id}
            raise TezError(ErrorCode.ATTACHMENT_NOT_FOUND, params, status=404)
        return view(attachment)


@dataclass(frozen=True)
class FileFacts:
    """What other modules need to know about a stored file."""

    paper_id: str
    sha256: str
    page_count: int | None


def file_facts(session: Session, attachment_id: str) -> FileFacts:
    attachment = FilesRepository(session).get(attachment_id)
    if attachment is None:
        params = {"attachment_id": attachment_id}
        raise TezError(ErrorCode.ATTACHMENT_NOT_FOUND, params, status=404)
    return FileFacts(attachment.paper_id, attachment.sha256, attachment.page_count)


def text_is_current(session: Session, attachment_id: str) -> bool:
    """Whether the stored text is this file's (not missing, not a replaced file's)."""
    attachment = FilesRepository(session).get(attachment_id)
    return attachment is not None and attachment.text_version is not None


def replace_file(
    db: Database, library_path: Path, attachment_id: str, data: bytes, file_name: str
) -> AttachmentView:
    """Another version of the same document (a preprint's published PDF, a corrected scan).

    The attachment keeps its id, so everything that points at it stays; its text is read again
    and its anchors look for their places in the new file (Task 46). The old file stays on disk.
    """
    _check_pdf(data, file_name)
    sha256 = storage.sha256_of(data)
    if (existing := _existing(db, sha256)) is not None:
        if existing.attachment_id == attachment_id:
            return get_attachment(db, attachment_id)
        params = {"file_name": file_name, "paper_id": existing.paper_id}
        raise TezError(ErrorCode.ATTACHMENT_FILE_IN_USE, params, status=409)
    get_attachment(db, attachment_id)
    relative = storage.store(library_path, data, sha256)
    with db.write_session() as session:
        attachment = FilesRepository(session).get(attachment_id)
        if attachment is None:
            params = {"attachment_id": attachment_id}
            raise TezError(ErrorCode.ATTACHMENT_NOT_FOUND, params, status=404)
        attachment.rel_path = relative
        attachment.sha256 = sha256
        attachment.file_name = file_name
        attachment.size = len(data)
        attachment.page_count = None
        attachment.text_status = TextStatus.PENDING
        attachment.text_version = None
        attachment.error = None
        session.flush()
        jobs_service.enqueue(
            session, INSPECT_JOB, {"attachment_id": attachment_id}, dedupe_key=attachment_id
        )
        logger.info("pdf replaced", extra={"attachment_id": attachment_id, "size": len(data)})
        return view(attachment)


# --- worker side ----------------------------------------------------------------------


def set_text_status(
    session: Session,
    attachment_id: str,
    status: TextStatus,
    *,
    page_count: int | None = None,
    text_version: int | None = None,
    error: TezError | None = None,
) -> bool:
    """What is known about a file's text now. False if the attachment is gone."""
    attachment = FilesRepository(session).get(attachment_id)
    if attachment is None:
        return False
    attachment.text_status = status
    if page_count is not None:
        attachment.page_count = page_count
    if text_version is not None:
        attachment.text_version = text_version
    attachment.error = (
        json.dumps({"code": error.code.value, "params": error.params}) if error else None
    )
    return True


def _mark_failed(db: Database, attachment_id: str, error: TezError) -> None:
    with db.write_session() as session:
        set_text_status(session, attachment_id, TextStatus.FAILED, error=error)


def open_in_worker[T](
    attachment_id: str, ctx: JobContext, read: Callable[[Path], T | None]
) -> T | None:
    """Run `read` on an attachment's file, marking the file when it is missing, unreadable or
    crashes this process. None when there was nothing to read."""
    with ctx.db.session() as session:
        attachment = FilesRepository(session).get(attachment_id)
        if attachment is None:
            logger.warning("attachment gone before its job", extra={"id": attachment_id})
            return None
        rel_path = attachment.rel_path
    if ctx.last_attempt:
        # If PDFium takes this process down now, the file stays marked as the cause and is
        # skipped from then on (plan: three failures mark the file and move on).
        crashed = TezError(ErrorCode.PDF_CRASHED, {"attempts": ctx.attempt})
        _mark_failed(ctx.db, attachment_id, crashed)
    path = ctx.library_path / rel_path
    if not path.is_file():
        _mark_failed(ctx.db, attachment_id, TezError(ErrorCode.PDF_MISSING, {"path": rel_path}))
        return None
    try:
        return read(path)
    except TezError as error:
        logger.info("pdf unreadable", extra={"id": attachment_id, "params": error.params})
        _mark_failed(ctx.db, attachment_id, error)
        return None


def inspect_attachment(payload: dict[str, object], ctx: JobContext) -> None:
    """The `pdf.inspect` job: page count and text layer, or the reason the file is broken.
    A file that opens has its text read next (`pdf.extract_text`)."""
    attachment_id = str(payload["attachment_id"])
    found = open_in_worker(attachment_id, ctx, inspect_pdf)
    if found is None:
        return
    status = TextStatus.OK if found.has_text else TextStatus.NEEDS_OCR
    with ctx.db.write_session() as session:
        if set_text_status(session, attachment_id, status, page_count=found.page_count):
            queue_extraction(session, attachment_id)
    ctx.report(1.0)


def queue_extraction(session: Session, attachment_id: str) -> str:
    return jobs_service.enqueue(
        session,
        EXTRACT_JOB,
        {"attachment_id": attachment_id},
        dedupe_key=f"text:{attachment_id}",
        priority=_EXTRACT_PRIORITY,
    )


def queue_missing_extractions(session: Session) -> int:
    """Queue every file that opens but whose text was never read, or by an older extractor."""
    found = FilesRepository(session).without_text(TEXT_VERSION)
    for attachment_id in found:
        queue_extraction(session, attachment_id)
    return len(found)


def pdf_states(session: Session, paper_ids: Iterable[str]) -> dict[str, TextStatus]:
    """Each paper's best PDF state, for lists: a readable file wins over a failed one."""
    rank = {TextStatus.OK: 0, TextStatus.NEEDS_OCR: 1, TextStatus.PENDING: 2, TextStatus.FAILED: 3}
    states: dict[str, TextStatus] = {}
    wanted = list(paper_ids)
    for start in range(0, len(wanted), _BATCH):
        batch = wanted[start : start + _BATCH]
        rows = session.execute(
            select(Attachment.paper_id, Attachment.text_status).where(
                Attachment.paper_id.in_(batch), Attachment.kind == AttachmentKind.PDF
            )
        )
        for paper_id, status in rows:
            known = states.get(paper_id)
            if known is None or rank[status] < rank[known]:
                states[paper_id] = status
    return states


def file_of(db: Database, library_path: Path, attachment_id: str) -> tuple[Path, AttachmentView]:
    """Where an attachment's file is on disk; `pdf.missing` if it is not there any more."""
    found = get_attachment(db, attachment_id)
    with db.session() as session:
        attachment = FilesRepository(session).get(attachment_id)
        assert attachment is not None
        path = library_path / attachment.rel_path
    if not path.is_file():
        raise TezError(ErrorCode.PDF_MISSING, {"path": attachment.rel_path}, status=404)
    return path, found
