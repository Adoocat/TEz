from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tez.core.errors import ErrorDetail
from tez.modules.files.models import AttachmentKind, TextStatus

# A 300-page scanned thesis is rarely over 100 MB; this leaves room and still bounds memory.
MAX_PDF_BYTES = 300 * 1024 * 1024


class AttachmentView(BaseModel):
    id: str
    paper_id: str
    kind: AttachmentKind
    file_name: str | None
    sha256: str
    size: int | None
    page_count: int | None
    # pending: not inspected yet; ok: has text; needs_ocr: scanned; failed: see `error`.
    text_status: TextStatus
    error: ErrorDetail | None
    source: str | None
    created_at: datetime


PdfAddStatus = Literal["added", "duplicate"]


class PdfAdded(BaseModel):
    status: PdfAddStatus
    paper_id: str
    attachment_id: str
    # The inspection job; None for a duplicate, which was inspected the first time.
    job_id: str | None
    file_name: str


class PdfPaths(BaseModel):
    """Files on this computer: the desktop app's drops, `tez <file.pdf>`, the CLI."""

    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(min_length=1, max_length=1000)
    paper_id: str | None = None


class PdfPathResult(BaseModel):
    path: str
    added: PdfAdded | None = None
    error: ErrorDetail | None = None


class OpenAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_ids: list[str] = Field(min_length=1, max_length=5000)


class OpenAccessQueued(BaseModel):
    # One background job per paper; follow them on /jobs/events.
    job_ids: list[str]
    already_have_pdf: int
    # No DOI, arXiv id or open-access link: nowhere to look.
    no_source: int
