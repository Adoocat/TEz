"""RIS exports (IEEE Xplore, Scopus, Web of Science, ACM DL) to `NormalizedRecord`s.

The file is cut into records here, at each `TY  -` line, and each record is parsed on its own:
rispy reads a whole file at once and silently drops text it does not understand, which would
hide a damaged export from the user.
"""

import logging
import re
from typing import Any, cast

import rispy  # pyright: ignore[reportMissingTypeStubs]

from tez.modules.importers.parsing import (
    EntryIssue,
    ImportFormat,
    IssueCode,
    ParsedFile,
    join_pages,
    parse_year,
)
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.library.thesis import thesis_type_from_text

logger = logging.getLogger(__name__)

_START = re.compile(r"^\s*TY  -", re.MULTILINE)
_END = re.compile(r"^\s*ER  -.*$", re.MULTILINE)
_TYPES = {
    "JOUR": VenueType.JOURNAL,
    "JFULL": VenueType.JOURNAL,
    "MGZN": VenueType.JOURNAL,
    "EJOUR": VenueType.JOURNAL,
    "CONF": VenueType.CONFERENCE,
    "CPAPER": VenueType.CONFERENCE,
    "BOOK": VenueType.BOOK,
    "EBOOK": VenueType.BOOK,
    "CHAP": VenueType.CHAPTER,
    "ECHAP": VenueType.CHAPTER,
    "THES": VenueType.THESIS,
    "RPRT": VenueType.REPORT,
    "UNPB": VenueType.PREPRINT,
}
_TITLE_TAGS = ("title", "primary_title", "translated_title")
_YEAR_TAGS = ("year", "publication_year", "date")
_VENUE_TAGS = ("secondary_title", "journal_name", "alternate_title3", "alternate_title1")
_AUTHOR_TAGS = ("authors", "first_authors")


def _first(record: dict[str, Any], *tags: str) -> str | None:
    for tag in tags:
        value = record.get(tag)
        if isinstance(value, list):
            value = next((v for v in cast(list[Any], value) if isinstance(v, str) and v), None)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return None


def _author(name: str) -> dict[str, Any] | None:
    name = " ".join(name.split())
    if not name:
        return None
    if "," in name:
        family, given = (part.strip() for part in name.split(",", 1))
        display = f"{given} {family}".strip() if given else family
        return {"display_name": display, "family": family or None, "given": given or None}
    return {"display_name": name}


def _authors(record: dict[str, Any]) -> list[dict[str, Any]]:
    for tag in _AUTHOR_TAGS:
        names = record.get(tag)
        if isinstance(names, list) and names:
            authors = (_author(n) for n in cast(list[Any], names) if isinstance(n, str))
            return [a for a in authors if a is not None]
    return []


def _identifiers(record: dict[str, Any]) -> dict[IdentifierScheme, str]:
    found: dict[IdentifierScheme, str] = {}
    if doi := _first(record, "doi"):
        found[IdentifierScheme.DOI] = doi
    isbn = _first(record, "issn") if record.get("type_of_reference") in {"BOOK", "CHAP"} else None
    if isbn:
        found[IdentifierScheme.ISBN] = isbn
    return found


def _url(record: dict[str, Any]) -> str | None:
    url = _first(record, "urls", "url", "link_to_pdf")
    return url.split()[0] if url else None


def _record_fields(record: dict[str, Any]) -> dict[str, Any]:
    kind = str(record.get("type_of_reference", "")).upper()
    return {
        "title": _first(record, *_TITLE_TAGS),
        "authors": _authors(record),
        "year": parse_year(_first(record, *_YEAR_TAGS)),
        "identifiers": _identifiers(record),
        "abstract": _first(record, "abstract", "notes_abstract"),
        "venue": _first(record, *_VENUE_TAGS),
        "venue_type": _TYPES.get(kind, VenueType.OTHER),
        # M3, "type of work": the degree of a thesis.
        "thesis_type": thesis_type_from_text(_first(record, "type_of_work"))
        if kind == "THES"
        else None,
        "volume": _first(record, "volume"),
        "issue": _first(record, "number"),
        "pages": join_pages(_first(record, "start_page"), _first(record, "end_page")),
        "language": _first(record, "language"),
        "url": _url(record),
    }


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def parse_ris(text: str) -> ParsedFile:
    parsed = ParsedFile(ImportFormat.RIS)
    starts = [match.start() for match in _START.finditer(text)]
    leading = text[: starts[0]] if starts else text
    if leading.strip():
        parsed.issues.append(EntryIssue(IssueCode.STRAY_TEXT, _first_text_line(text, 0)))
    for index, start in enumerate(starts):
        stop = starts[index + 1] if index + 1 < len(starts) else len(text)
        _parse_chunk(parsed, text, start, stop)
    return parsed


def _first_text_line(text: str, offset: int) -> int:
    stripped = len(text[offset:]) - len(text[offset:].lstrip())
    return _line_of(text, offset + stripped)


def _parse_chunk(parsed: ParsedFile, text: str, start: int, stop: int) -> None:
    line = _line_of(text, start)
    chunk = text[start:stop]
    end = _END.search(chunk)
    if end is None:
        # A record cut short (a truncated download) may have lost fields: it is reported and
        # skipped. It is still parsed, for its reference id.
        body = chunk.rstrip() + "\nER  - \n"
    else:
        body = chunk[: end.end()] + "\n"
        if chunk[end.end() :].strip():
            parsed.issues.append(
                EntryIssue(IssueCode.STRAY_TEXT, _first_text_line(text, start + end.end()))
            )
    try:
        records = cast(list[Any], cast(Any, rispy).loads(body))
    except Exception as exc:  # rispy raises bare IOError/ValueError on malformed tags.
        logger.info("ris record not parsed", extra={"line": line}, exc_info=True)
        parsed.issues.append(EntryIssue(IssueCode.UNPARSEABLE, line, None, type(exc).__name__))
        return
    if len(records) != 1:
        parsed.issues.append(EntryIssue(IssueCode.UNPARSEABLE, line, None))
        return
    record = cast(dict[str, Any], records[0])
    key = _first(record, "id", "reference_id")
    if end is None:
        parsed.issues.append(EntryIssue(IssueCode.TRUNCATED, line, key))
        return
    parsed.add(_record_fields(record), line=line, key=key)
