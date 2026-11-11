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
    SCREENING_INVALID_CORRECTION = "screening.invalid_correction"
    JOB_NOT_FOUND = "job.not_found"
    SECRETS_UNAVAILABLE = "secrets.unavailable"
    REVIEW_NOT_FOUND = "review.not_found"
    PAPER_NOT_FOUND = "paper.not_found"
    SEARCH_NOT_FOUND = "search.not_found"
    SOURCE_UNKNOWN = "source.unknown"
    SOURCE_RATE_LIMITED = "source.rate_limited"
    SOURCE_TIMEOUT = "source.timeout"
    SOURCE_NETWORK = "source.network"
    SOURCE_UNAVAILABLE = "source.unavailable"
    SOURCE_REJECTED = "source.rejected"
    SOURCE_BAD_RESPONSE = "source.bad_response"
    SOURCE_QUERY_UNSUPPORTED = "source.query_unsupported"
    SOURCE_KEY_REQUIRED = "source.key_required"
    IMPORT_UNKNOWN_FORMAT = "import.unknown_format"
    IMPORT_EMPTY = "import.empty"
    IMPORT_INVALID_CONTENT = "import.invalid_content"
    IMPORT_ENTRIES_SKIPPED = "import.entries_skipped"


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
