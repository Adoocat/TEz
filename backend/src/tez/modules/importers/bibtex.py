"""BibTeX exports (IEEE Xplore, ACM DL, Scopus, Google Scholar, DBLP) to `NormalizedRecord`s.

Names are split before LaTeX is decoded, so a braced corporate author ("{IEEE Team}") stays one
name, and only then is each part decoded ("{\\c{c}}" to "ç", "{\\i}" to "ı").
"""

import logging
import re
from typing import Any, cast

from bibtexparser.entrypoint import parse_string
from bibtexparser.middlewares import NameParts, SeparateCoAuthors, SplitNameParts
from bibtexparser.model import DuplicateBlockKeyBlock, Entry, ParsingFailedBlock
from pylatexenc.latex2text import LatexNodes2Text  # pyright: ignore[reportMissingTypeStubs]

from tez.modules.importers.parsing import (
    EntryIssue,
    ImportFormat,
    IssueCode,
    ParsedFile,
    parse_year,
)
from tez.modules.library.models import IdentifierScheme, ThesisType, VenueType
from tez.modules.library.thesis import thesis_type_from_text

logger = logging.getLogger(__name__)

_TYPES = {
    "article": VenueType.JOURNAL,
    "inproceedings": VenueType.CONFERENCE,
    "conference": VenueType.CONFERENCE,
    "proceedings": VenueType.CONFERENCE,
    "book": VenueType.BOOK,
    "inbook": VenueType.CHAPTER,
    "incollection": VenueType.CHAPTER,
    "phdthesis": VenueType.THESIS,
    "mastersthesis": VenueType.THESIS,
    "thesis": VenueType.THESIS,
    "techreport": VenueType.REPORT,
    "report": VenueType.REPORT,
    "unpublished": VenueType.OTHER,
    "misc": VenueType.OTHER,
    "online": VenueType.OTHER,
}
_THESIS_TYPES: dict[str, ThesisType | None] = {
    "mastersthesis": ThesisType.MASTERS,
    "phdthesis": ThesisType.DOCTORAL,
    "thesis": None,
}
_VENUE_FIELDS = ("journal", "journaltitle", "booktitle", "school", "institution", "publisher")
_DASHES = re.compile(r"\s*[-" + "\N{EN DASH}\N{EM DASH}" + r"]+\s*")
# pylatexenc has no type hints.
_LATEX = cast(Any, LatexNodes2Text(math_mode="text", strict_latex_spaces=True))


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        decoded = str(_LATEX.latex_to_text(value))
    except Exception:  # pylatexenc raises plain exceptions on odd input; keep the raw text.
        logger.warning("latex not decoded", extra={"value": value[:80]}, exc_info=True)
        decoded = value.replace("{", "").replace("}", "")
    return " ".join(decoded.split()) or None


def _author(name: NameParts) -> dict[str, Any] | None:
    given = _text(" ".join(name.first))
    family = _text(" ".join([*name.von, *name.last]))
    suffix = _text(" ".join(name.jr))
    if family and suffix:
        family = f"{family} {suffix}"
    display = " ".join(part for part in (given, family) if part)
    if not display:
        return None
    return {"display_name": display, "family": family, "given": given}


def _authors(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    authors = (_author(name) for name in value if isinstance(name, NameParts))  # pyright: ignore[reportUnknownVariableType]
    return [author for author in authors if author is not None]


def _venue_type(entry: Entry, fields: dict[str, Any]) -> VenueType:
    if _arxiv_id(fields) is not None and entry.entry_type.lower() in {"misc", "online", "article"}:
        journal = _text(fields.get("journal")) or ""
        if not journal or journal.lower().startswith("arxiv"):
            return VenueType.PREPRINT
    return _TYPES.get(entry.entry_type.lower(), VenueType.OTHER)


def _thesis_type(entry: Entry, fields: dict[str, Any]) -> ThesisType | None:
    """@mastersthesis / @phdthesis, or BibLaTeX's @thesis with a `type` field."""
    kind = entry.entry_type.lower()
    if kind not in _THESIS_TYPES:
        return None
    return _THESIS_TYPES[kind] or thesis_type_from_text(_text(fields.get("type")))


def _arxiv_id(fields: dict[str, Any]) -> str | None:
    eprint = _text(fields.get("eprint"))
    prefix = (_text(fields.get("archiveprefix")) or _text(fields.get("eprinttype")) or "").lower()
    if eprint and prefix == "arxiv":
        return eprint
    journal = _text(fields.get("journal")) or ""
    match = re.search(r"arxiv[:\s]*(\d{4}\.\d{4,5})", journal, re.IGNORECASE)
    return match.group(1) if match else None


def _identifiers(fields: dict[str, Any]) -> dict[IdentifierScheme, str]:
    found: dict[IdentifierScheme, str] = {}
    if doi := _text(fields.get("doi")):
        found[IdentifierScheme.DOI] = doi
    if arxiv := _arxiv_id(fields):
        found[IdentifierScheme.ARXIV] = arxiv
    if isbn := _text(fields.get("isbn")):
        found[IdentifierScheme.ISBN] = isbn.split(",")[0]
    return found


def _url(fields: dict[str, Any]) -> str | None:
    url = _text(fields.get("url"))
    # Some exporters put several links in one field.
    return url.split()[0] if url else None


def _pages(fields: dict[str, Any]) -> str | None:
    pages = _text(fields.get("pages"))
    return _DASHES.sub("-", pages) if pages else None


def _record_fields(entry: Entry) -> dict[str, Any]:
    fields = {key.lower(): value for key, value in entry.fields_dict.items()}
    raw = {key: field.value for key, field in fields.items()}
    venue = next((v for name in _VENUE_FIELDS if (v := _text(raw.get(name)))), None)
    return {
        "title": _text(raw.get("title")),
        "authors": _authors(raw.get("author")),
        "year": parse_year(_text(raw.get("year")) or _text(raw.get("date"))),
        "identifiers": _identifiers(raw),
        "abstract": _text(raw.get("abstract")),
        "venue": venue,
        "venue_type": _venue_type(entry, raw),
        "thesis_type": _thesis_type(entry, raw),
        "volume": _text(raw.get("volume")),
        "issue": _text(raw.get("number")) or _text(raw.get("issue")),
        "pages": _pages(raw),
        "language": _text(raw.get("language")),
        "url": _url(raw),
    }


def parse_bibtex(text: str) -> ParsedFile:
    parsed = ParsedFile(ImportFormat.BIBTEX)
    library = parse_string(text, append_middleware=[SeparateCoAuthors(), SplitNameParts()])
    for block in library.blocks:
        line = block.start_line + 1 if block.start_line is not None else None
        if isinstance(block, Entry):
            parsed.add(_record_fields(block), line=line, key=block.key)
        elif isinstance(block, DuplicateBlockKeyBlock):
            # The first entry with this key was read; a second one is reported, not merged.
            parsed.issues.append(EntryIssue(IssueCode.DUPLICATE_KEY, line, block.key))
        elif isinstance(block, ParsingFailedBlock):
            key = _key_of(block.raw or "")
            parsed.issues.append(EntryIssue(IssueCode.UNPARSEABLE, line, key))
    return parsed


def _key_of(raw: str) -> str | None:
    match = re.match(r"\s*@\w+\s*[{(]\s*([^,\s]+)\s*,", raw)
    return match.group(1) if match else None
