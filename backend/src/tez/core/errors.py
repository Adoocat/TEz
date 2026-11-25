"""Error model: the API returns codes and parameters, never user-facing text.

Every error response has the shape `{"error": {"code": "<area>.<name>", "params": {...}}}`;
the frontend turns the code into a translated message.
"""

import logging
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    AUTH_INVALID_TOKEN = "auth.invalid_token"
    REQUEST_INVALID = "request.invalid"
    HTTP_NOT_FOUND = "http.not_found"
    HTTP_METHOD_NOT_ALLOWED = "http.method_not_allowed"
    HTTP_ERROR = "http.error"
    INTERNAL_UNEXPECTED = "internal.unexpected"
    LIBRARY_NOT_FOUND = "library.not_found"
    LIBRARY_NOT_EMPTY = "library.not_empty"
    LIBRARY_LOCKED = "library.locked"
    LIBRARY_TOO_NEW = "library.too_new"
    LIBRARY_NOT_OPEN = "library.not_open"
    COLLECTION_CYCLE = "collection.cycle"
    COLLECTION_NOT_FOUND = "collection.not_found"
    COLLECTION_SYSTEM = "collection.system"
    COLLECTION_NAME_TAKEN = "collection.name_taken"
    TAG_NOT_FOUND = "tag.not_found"
    TAG_NAME_TAKEN = "tag.name_taken"
    SCREENING_INVALID_CORRECTION = "screening.invalid_correction"
    SCREENING_CRITERION_NOT_FOUND = "screening.criterion_not_found"
    SCREENING_CRITERION_IN_USE = "screening.criterion_in_use"
    SCREENING_CRITERION_CODE_TAKEN = "screening.criterion_code_taken"
    SCREENING_CRITERIA_ORDER_MISMATCH = "screening.criteria_order_mismatch"
    SCREENING_RECORD_NOT_FOUND = "screening.record_not_found"
    SCREENING_REASON_REQUIRED = "screening.reason_required"
    SCREENING_INVALID_CRITERION = "screening.invalid_criterion"
    SCREENING_INVALID_DECISION = "screening.invalid_decision"
    SCREENING_STAGE_NOT_REACHED = "screening.stage_not_reached"
    SCREENING_DECISION_NOT_FOUND = "screening.decision_not_found"
    SCREENING_UNDO_STALE = "screening.undo_stale"
    JOB_NOT_FOUND = "job.not_found"
    SECRETS_UNAVAILABLE = "secrets.unavailable"
    REVIEW_NOT_FOUND = "review.not_found"
    PAPER_NOT_FOUND = "paper.not_found"
    CITEKEY_TAKEN = "citekey.taken"
    CITEKEY_INVALID = "citekey.invalid"
    SEARCH_NOT_FOUND = "search.not_found"
    SEARCH_FILTER_UNSUPPORTED = "search.filter_unsupported"
    EXTERNAL_SEARCH_NOT_FOUND = "external_search.not_found"
    SOURCE_UNKNOWN = "source.unknown"
    SOURCE_RATE_LIMITED = "source.rate_limited"
    SOURCE_TIMEOUT = "source.timeout"
    SOURCE_NETWORK = "source.network"
    SOURCE_UNAVAILABLE = "source.unavailable"
    SOURCE_REJECTED = "source.rejected"
    SOURCE_BAD_RESPONSE = "source.bad_response"
    SOURCE_QUERY_UNSUPPORTED = "source.query_unsupported"
    SOURCE_KEY_REQUIRED = "source.key_required"
    SOURCE_TOO_LARGE = "source.too_large"
    SOURCE_EMAIL_REQUIRED = "source.email_required"
    SNOWBALL_SEED_NOT_IN_REVIEW = "snowball.seed_not_in_review"
    SNOWBALL_SEED_NOT_INCLUDED = "snowball.seed_not_included"
    SNOWBALL_SEED_UNIDENTIFIED = "snowball.seed_unidentified"
    SNOWBALL_SEED_NOT_FOUND = "snowball.seed_not_found"
    IMPORT_UNKNOWN_FORMAT = "import.unknown_format"
    IMPORT_EMPTY = "import.empty"
    IMPORT_INVALID_CONTENT = "import.invalid_content"
    IMPORT_FILE_NOT_FOUND = "import.file_not_found"
    IMPORT_ENTRIES_SKIPPED = "import.entries_skipped"
    IMPORT_PRESET_UNAVAILABLE = "import.preset_unavailable"
    ATTACHMENT_FILE_IN_USE = "attachment.file_in_use"
    ANCHOR_NOT_FOUND = "anchor.not_found"
    ANCHOR_NO_SUCH_PAGE = "anchor.no_such_page"
    PDF_NOT_A_PDF = "pdf.not_a_pdf"
    PDF_TOO_LARGE = "pdf.too_large"
    PDF_FILE_NOT_FOUND = "pdf.file_not_found"
    PDF_UNREADABLE = "pdf.unreadable"
    PDF_ENCRYPTED = "pdf.encrypted"
    PDF_CRASHED = "pdf.crashed"
    PDF_MISSING = "pdf.missing"
    ATTACHMENT_NOT_FOUND = "attachment.not_found"
    PDF_NO_OPEN_ACCESS = "pdf.no_open_access"
    BACKUP_DAMAGED = "backup.damaged"
    BACKUP_UNSUPPORTED = "backup.unsupported"
    EXPORT_ONE_SCOPE = "export.one_scope"
    QUALITY_TEMPLATE_UNKNOWN = "quality.template_unknown"
    QUALITY_QUESTION_NOT_FOUND = "quality.question_not_found"
    QUALITY_QUESTION_IN_USE = "quality.question_in_use"
    QUALITY_SCALE_VALUE_IN_USE = "quality.scale_value_in_use"
    QUALITY_ANSWER_INVALID = "quality.answer_invalid"
    QUALITY_PAPER_NOT_INCLUDED = "quality.paper_not_included"
    QUALITY_ORDER_MISMATCH = "quality.order_mismatch"
    CLI_REVIEW_REQUIRED = "cli.review_required"
    CLI_NO_REVIEW = "cli.no_review"
    CLI_LIBRARY_BUSY = "cli.library_busy"
    CLI_API_UNREACHABLE = "cli.api_unreachable"
    DECISIONS_INVALID_FILE = "decisions.invalid_file"
    DECISIONS_UNSUPPORTED_VERSION = "decisions.unsupported_version"
    DECISIONS_RESERVED_REVIEWER = "decisions.reserved_reviewer"


class TezError(Exception):
    """An expected failure with a stable code. Raise it from services; the API maps it."""

    def __init__(
        self,
        code: ErrorCode,
        params: Mapping[str, Any] | None = None,
        *,
        status: int = 400,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.params: dict[str, Any] = dict(params or {})
        self.status = status


class ErrorDetail(BaseModel):
    code: str = Field(examples=["auth.invalid_token"])
    params: dict[str, Any] = Field(default_factory=dict[str, Any])


class ErrorResponse(BaseModel):
    error: ErrorDetail


# Shared OpenAPI declaration, so the generated client knows the error shape.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Missing or invalid token"},
    422: {"model": ErrorResponse, "description": "Invalid request"},
    500: {"model": ErrorResponse, "description": "Unexpected error"},
}


def error_response(
    code: ErrorCode,
    status: int,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code.value, params=dict(params or {})))
    return JSONResponse(jsonable_encoder(body), status_code=status, headers=headers)


_HTTP_CODES = {404: ErrorCode.HTTP_NOT_FOUND, 405: ErrorCode.HTTP_METHOD_NOT_ALLOWED}


async def _tez_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, TezError)
    return error_response(exc.code, exc.status, exc.params)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = [{"loc": list(e.get("loc", ())), "type": e.get("type", "")} for e in exc.errors()]
    return error_response(ErrorCode.REQUEST_INVALID, 422, {"fields": fields})


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_CODES.get(exc.status_code, ErrorCode.HTTP_ERROR)
    params: dict[str, Any] = {} if code is not ErrorCode.HTTP_ERROR else {"status": exc.status_code}
    return error_response(code, exc.status_code, params, exc.headers)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(TezError, _tez_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
