from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from starlette.concurrency import run_in_threadpool

from tez.core.errors import ErrorCode, TezError
from tez.modules.files import open_access, service
from tez.modules.files.schemas import (
    MAX_PDF_BYTES,
    AttachmentView,
    OpenAccessQueued,
    OpenAccessRequest,
    PdfAdded,
    PdfPathResult,
    PdfPaths,
)
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

router = APIRouter(tags=["files"])

LibraryDep = Annotated[Library, Depends(get_library)]

_PDF_BODY = {
    "requestBody": {
        "required": True,
        "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
    }
}


@router.post("/pdfs", status_code=201, openapi_extra=_PDF_BODY)
async def upload_pdf(
    request: Request,
    library: LibraryDep,
    file_name: Annotated[str, Query(min_length=1, max_length=255)],
    paper_id: str | None = None,
) -> PdfAdded:
    """Add a PDF sent as the raw request body. Without `paper_id` it becomes a new paper in
    the inbox. The same file twice is `duplicate` and changes nothing."""
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_PDF_BYTES:
        params = {"file_name": file_name, "size": int(declared)}
        raise TezError(ErrorCode.PDF_TOO_LARGE, params, status=413)
    data = await request.body()
    return await run_in_threadpool(
        service.add_pdf, library.db, library.path, data, file_name, paper_id=paper_id
    )


@router.post("/pdfs/from-paths")
def add_pdfs_from_paths(body: PdfPaths, library: LibraryDep) -> list[PdfPathResult]:
    """Add PDFs by their paths on this computer; each file succeeds or fails on its own."""
    return service.add_pdfs_from_paths(library.db, library.path, body.paths, paper_id=body.paper_id)


@router.get("/papers/{paper_id}/attachments")
def paper_attachments(paper_id: str, library: LibraryDep) -> list[AttachmentView]:
    return service.attachments_of(library.db, paper_id)


@router.get("/attachments/{attachment_id}")
def get_attachment(attachment_id: str, library: LibraryDep) -> AttachmentView:
    return service.get_attachment(library.db, attachment_id)


@router.post("/pdfs/open-access", status_code=202)
def find_open_access_pdfs(body: OpenAccessRequest, library: LibraryDep) -> OpenAccessQueued:
    """Look for free PDFs (arXiv, Unpaywall, the source's link) in the background, one job
    per paper. The papers are kept in the library."""
    queued = open_access.queue_fetches(library.db, body.paper_ids)
    return OpenAccessQueued(
        job_ids=queued.job_ids,
        already_have_pdf=queued.already_have_pdf,
        no_source=queued.no_source,
    )
