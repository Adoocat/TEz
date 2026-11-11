"""What a parser hands back: the records it could read and a report on the entries it could not.

A broken entry never stops an import. It becomes an `EntryIssue` with a stable code, so the
user sees which entry (by line and key) was skipped and why, and fixes the file if it matters.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from tez.modules.search.schemas import NormalizedRecord


class ImportFormat(StrEnum):
    BIBTEX = "bibtex"
    RIS = "ris"


class IssueCode(StrEnum):
    """Why an entry was skipped. The frontend turns each into a translated sentence."""

    UNPARSEABLE = "import.entry_unparseable"
    NO_TITLE = "import.entry_no_title"
    DUPLICATE_KEY = "import.entry_duplicate_key"
    TRUNCATED = "import.entry_truncated"
    STRAY_TEXT = "import.stray_text"


class RecordWarning(StrEnum):
    """A record was read, but a field the user would expect is missing or unusable."""

    NO_AUTHORS = "no_authors"
    NO_YEAR = "no_year"
    NO_IDENTIFIER = "no_identifier"
    BAD_YEAR = "bad_year"
    BAD_LINK = "bad_link"


@dataclass(frozen=True)
class EntryIssue:
    code: IssueCode
    # 1-based line where the entry starts; None when the parser cannot tell.
    line: int | None = None
    # The BibTeX key or RIS reference id, when the entry has one.
    key: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class ParsedEntry:
    record: NormalizedRecord
    line: int | None
    key: str | None
    warnings: tuple[RecordWarning, ...] = ()


@dataclass
class ParsedFile:
    format: ImportFormat
    entries: list[ParsedEntry] = field(default_factory=list[ParsedEntry])
    issues: list[EntryIssue] = field(default_factory=list[EntryIssue])

    @property
    def records(self) -> list[NormalizedRecord]:
        return [entry.record for entry in self.entries]

    @property
    def total(self) -> int:
        """Entries the file holds: read or skipped. Stray text is not an entry."""
        skipped = sum(issue.code is not IssueCode.STRAY_TEXT for issue in self.issues)
        return len(self.entries) + skipped

    def add(self, fields: dict[str, Any], *, line: int | None, key: str | None) -> None:
        """Validate one mapped entry and keep it, or report why it cannot be kept."""
        if not fields.get("title"):
            self.issues.append(EntryIssue(IssueCode.NO_TITLE, line, key))
            return
        raw_year = fields.get("year")
        if raw_year is not None and not isinstance(raw_year, int):
            fields = {**fields, "year": None}
        try:
            record = NormalizedRecord.model_validate(fields)
        except ValidationError as exc:
            detail = "; ".join(str(e["loc"][0]) for e in exc.errors() if e["loc"])
            self.issues.append(EntryIssue(IssueCode.UNPARSEABLE, line, key, detail or None))
            return
        self.entries.append(ParsedEntry(record, line, key, _warnings(fields, record, raw_year)))


def _warnings(
    fields: dict[str, Any], record: NormalizedRecord, raw_year: Any
) -> tuple[RecordWarning, ...]:
    found: list[RecordWarning] = []
    if not record.authors:
        found.append(RecordWarning.NO_AUTHORS)
    if record.year is None:
        found.append(RecordWarning.NO_YEAR if raw_year is None else RecordWarning.BAD_YEAR)
    if not record.identifiers:
        found.append(RecordWarning.NO_IDENTIFIER)
    if fields.get("url") and record.url is None:
        found.append(RecordWarning.BAD_LINK)
    return tuple(found)


def parse_year(value: str | None) -> int | str | None:
    """The year from "2021", "2021///", "2020/05/01" or "2019-03"; the raw text if none."""
    if value is None:
        return None
    text = value.strip()
    head = text[:4]
    if head.isdigit():
        return int(head)
    return text or None


def join_pages(start: str | None, end: str | None) -> str | None:
    if start and end and start != end:
        return f"{start}-{end}"
    return start or end or None
