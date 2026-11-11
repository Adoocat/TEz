"""Adding PDFs to the library (plan, Task 16) and inspecting them in the worker.

A new PDF is stored under its hash, gets an `attachment` row and, unless it belongs to a paper
already, a new paper in the inbox. The API never opens the PDF itself: a `pdf.inspect` job in
the worker counts its pages and checks for a text layer, so a file that crashes PDFium takes
down only the worker. A broken file is marked `failed`, with a reason, and nothing else stops.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path, PurePath

from sqlalchemy.exc import IntegrityError

from tez.core.db import Database
from tez.core.errors import ErrorCode, ErrorDetail, TezError
from tez.modules.files import storage
from tez.modules.files.inspection import inspect_pdf
from tez.modules.files.models import Attachment, TextStatus
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
MANUAL_SOURCE = "manual"


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
    if len(data) > MAX_PDF_BYTES:
        params = {"file_name": file_name, "size": len(data)}
        raise TezError(ErrorCode.PDF_TOO_LARGE, params, status=413)
    if not storage.looks_like_pdf(data):
        raise TezError(ErrorCode.PDF_NOT_A_PDF, {"file_name": file_name}, status=422)
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
        return [view(a) for a in FilesRepository(session).for_paper(paper_id)]


def get_attachment(db: Database, attachment_id: str) -> AttachmentView:
    with db.session() as session:
        attachment = FilesRepository(session).get(attachment_id)
        if attachment is None:
            params = {"attachment_id": attachment_id}
            raise TezError(ErrorCode.ATTACHMENT_NOT_FOUND, params, status=404)
        return view(attachment)


# --- worker side ----------------------------------------------------------------------


def _mark(
    db: Database,
    attachment_id: str,
    status: TextStatus,
    *,
    page_count: int | None = None,
    error: TezError | None = None,
) -> None:
    with db.write_session() as session:
        attachment = FilesRepository(session).get(attachment_id)
        if attachment is None:
            return
        attachment.text_status = status
        if page_count is not None:
            attachment.page_count = page_count
        attachment.error = (
            json.dumps({"code": error.code.value, "params": error.params}) if error else None
        )


def inspect_attachment(payload: dict[str, object], ctx: JobContext) -> None:
    """The `pdf.inspect` job: page count and text layer, or the reason the file is broken."""
    attachment_id = str(payload["attachment_id"])
    with ctx.db.session() as session:
        attachment = FilesRepository(session).get(attachment_id)
        if attachment is None:
            logger.warning("attachment gone before inspection", extra={"id": attachment_id})
            return
        path = ctx.library_path / attachment.rel_path
    if ctx.last_attempt:
        # If PDFium takes this process down now, the file stays marked as the cause and is
        # skipped from then on (plan: three failures mark the file and move on).
        crashed = TezError(ErrorCode.PDF_CRASHED, {"attempts": ctx.attempt})
        _mark(ctx.db, attachment_id, TextStatus.FAILED, error=crashed)
    if not path.is_file():
        missing = TezError(ErrorCode.PDF_MISSING, {"path": attachment.rel_path})
        _mark(ctx.db, attachment_id, TextStatus.FAILED, error=missing)
        return
    try:
        found = inspect_pdf(path)
    except TezError as error:
        logger.info("pdf unreadable", extra={"id": attachment_id, "params": error.params})
        _mark(ctx.db, attachment_id, TextStatus.FAILED, error=error)
        return
    status = TextStatus.OK if found.has_text else TextStatus.NEEDS_OCR
    _mark(ctx.db, attachment_id, status, page_count=found.page_count)
    ctx.report(1.0)
