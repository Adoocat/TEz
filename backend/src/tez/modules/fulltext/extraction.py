"""Read the text of every page with PDFium. Worker process only: PDFium is native code and a
hostile file can crash it (plan, "Mimari").

The text of a page keeps one character per PDFium character (ADR 0030), so nothing is joined,
dropped or normalized here; `readable` makes text for people and for the search index.
"""

import logging
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pypdfium2.raw as _raw  # pyright: ignore[reportMissingTypeStubs]

from tez.modules.files.inspection import PdfiumError, open_document

logger = logging.getLogger(__name__)

raw = cast(Any, _raw)

# A page of dense text holds under 10 000 characters; a broken one can claim millions.
MAX_PAGE_CHARS = 200_000

SOFT_HYPHEN = "­"
# PDFium marks the hyphen it found at the end of a line (a word broken in two) like this.
_LINE_HYPHENS = (0x02, 0xFFFE)
# Fonts without a Unicode map give raw T1 codes, which are never valid text (ADR 0030).
_T1_CODES = {
    0x19: "ı",
    0x1B: "ﬀ",  # ff
    0x1C: "ﬁ",  # fi
    0x1D: "ﬂ",  # fl
    0x1E: "ﬃ",  # ffi
    0x1F: "ﬄ",  # ffl
}
_BROKEN_WORD = re.compile(rf"{SOFT_HYPHEN}[ \t]*\n+[ \t]*")
_SPACES = re.compile(r"[^\S\n]+")
_LINES = re.compile(r" ?\n[ \n]*")


@dataclass(frozen=True)
class PageText:
    index: int
    text: str


def clean_char(code: int) -> str:
    """Exactly one storable character for a PDFium character code."""
    if code in _LINE_HYPHENS:
        return SOFT_HYPHEN
    if (known := _T1_CODES.get(code)) is not None:
        return known
    if code in (0x09, 0x0A, 0x0D):
        return chr(code)
    if code < 0x20:
        return " "
    if 0xD800 <= code <= 0xDFFF or code > 0x10FFFF:
        return "�"  # half of a surrogate pair cannot be stored as UTF-8
    return chr(code)


def readable(text: str) -> str:
    """The text as a person reads it: words broken over lines joined, ligatures spelled out,
    one space between words, one newline between lines."""
    text = unicodedata.normalize("NFKC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = _BROKEN_WORD.sub("", text).replace(SOFT_HYPHEN, "")
    return _LINES.sub("\n", _SPACES.sub(" ", text)).strip()


def extract_pages(
    path: Path, *, keep_going: Callable[[float], bool] = lambda _: True
) -> list[PageText] | None:
    """Every page's text. None if `keep_going(fraction done)` said to stop.

    Raises `pdf.unreadable` or `pdf.encrypted` when the file does not open; a single page
    PDFium cannot read is empty and logged.
    """
    document = open_document(path)
    try:
        count = len(document)
        pages: list[PageText] = []
        for index in range(count):
            if not keep_going(index / count):
                return None
            try:
                text = _page_text(document, index)
            except PdfiumError as exc:
                logger.warning("page has no readable text", extra={"page": index, "why": str(exc)})
                text = ""
            pages.append(PageText(index, text))
        return pages
    finally:
        document.close()


def _page_text(document: Any, index: int) -> str:
    page = document[index]
    try:
        # PDFium orders text by the displayed page; a rotated one comes out scrambled (ADR 0030).
        # This changes the page in memory only, and boxes are in unrotated space either way.
        page.set_rotation(0)
        text_page = page.get_textpage()
        try:
            count = max(raw.FPDFText_CountChars(text_page), 0)
            if count > MAX_PAGE_CHARS:
                logger.warning("page text cut short", extra={"page": index, "chars": count})
                count = MAX_PAGE_CHARS
            return "".join(clean_char(raw.FPDFText_GetUnicode(text_page, i)) for i in range(count))
        finally:
            text_page.close()
    finally:
        page.close()
