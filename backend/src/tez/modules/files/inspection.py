"""Open a stored PDF with pypdfium2: page count, and whether it has a text layer.

This runs in the worker process only (`pdf.inspect` job). PDFium is native code: a hostile or
broken file can crash the process, and then only the worker goes down (plan, "Mimari").
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pypdfium2 as _pdfium  # pyright: ignore[reportMissingTypeStubs]

from tez.core.errors import ErrorCode, TezError

# pypdfium2 ships no type information; everything from it is treated as Any here.
pdfium = cast(Any, _pdfium)
PdfiumError: type[Exception] = pdfium.PdfiumError
_PASSWORD_ERROR = 4  # FPDF_ERR_PASSWORD

# Scanned PDFs have no text on any page; looking at the first few is enough to tell.
_PAGES_TO_PROBE = 3


@dataclass(frozen=True)
class Inspection:
    page_count: int
    has_text: bool


def inspect_pdf(path: Path) -> Inspection:
    """Raises `pdf.unreadable` or `pdf.encrypted` when PDFium cannot open the file."""
    document = open_document(path)
    try:
        page_count = len(document)
        probed = range(min(page_count, _PAGES_TO_PROBE))
        has_text = any(_has_text(document, index) for index in probed)
        return Inspection(page_count=page_count, has_text=has_text)
    except PdfiumError as exc:
        raise TezError(ErrorCode.PDF_UNREADABLE, {"reason": str(exc)}) from exc
    finally:
        document.close()


def open_document(path: Path) -> Any:
    """A PDFium document; a damaged or password-protected file is a `TezError`."""
    try:
        return pdfium.PdfDocument(path)
    except PdfiumError as exc:
        if getattr(exc, "err_code", None) == _PASSWORD_ERROR:
            raise TezError(ErrorCode.PDF_ENCRYPTED) from exc
        raise TezError(ErrorCode.PDF_UNREADABLE, {"reason": str(exc)}) from exc


def _has_text(document: Any, index: int) -> bool:
    page = document[index]
    try:
        text_page = page.get_textpage()
        try:
            return bool(text_page.get_text_range().strip())
        finally:
            text_page.close()
    finally:
        page.close()
