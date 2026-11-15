"""Import an exported results file: read it, preview it, then store it (plan, Task 15).

Imported records take the same road as a source's answer: `NormalizedRecord`, then
deduplication, then (if the user logs it) a `search_run` with the file kept as its snapshot.
That is how IEEE Xplore, ACM DL or Scopus, which have no open API, still enter the
systematic record and PRISMA.
"""

import base64
import binascii
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path, PurePath

from tez.core.db import Database, utcnow
from tez.core.errors import ErrorCode, TezError
from tez.modules.importers.bibtex import parse_bibtex
from tez.modules.importers.parsing import EntryIssue, ImportFormat, ParsedEntry, ParsedFile
from tez.modules.importers.ris import parse_ris
from tez.modules.importers.schemas import (
    SAMPLE_SIZE,
    ImportFile,
    ImportIssueView,
    ImportOutcome,
    ImportPreview,
    ImportRequest,
    PreviewRecord,
    PreviewStatus,
)
from tez.modules.library.models import IdentifierScheme
from tez.modules.library.paper_service import PaperService
from tez.modules.reviews import service as reviews_service
from tez.modules.search.external import EarlierImports
from tez.modules.search.models import InitiatedVia
from tez.modules.search.service import ImportRun, PreviewMatch, preview_matches, store_imported

logger = logging.getLogger(__name__)

_EXTENSIONS = {
    ".bib": ImportFormat.BIBTEX,
    ".bibtex": ImportFormat.BIBTEX,
    ".ris": ImportFormat.RIS,
}
_RIS_START = re.compile(r"^\s*TY  -", re.MULTILINE)
_BIBTEX_START = re.compile(r"^\s*@\w+\s*[{(]", re.MULTILINE)


def decode_base64(content: str) -> bytes:
    try:
        return base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise TezError(ErrorCode.IMPORT_INVALID_CONTENT, status=422) from exc


MAX_FILE_BYTES = 30 * 1024 * 1024


def read_input(file: ImportFile) -> bytes:
    """The file's bytes, from the request body or from disk."""
    if file.content_base64 is not None:
        return decode_base64(file.content_base64)
    path = Path(file.path or "")
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise TezError(ErrorCode.IMPORT_INVALID_CONTENT, {"path": str(path)}, status=422)
        return path.read_bytes()
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError, PermissionError) as exc:
        params = {"path": str(path)}
        raise TezError(ErrorCode.IMPORT_FILE_NOT_FOUND, params, status=404) from exc


def decode_text(data: bytes) -> str:
    """UTF-8 (with or without BOM), else Windows-1252, which older exporters still write."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        logger.info("import file is not UTF-8; reading it as Windows-1252")
    return data.decode("cp1252", errors="replace")


def detect_format(file_name: str, text: str) -> ImportFormat:
    """By extension first; by content for `.txt` and other names exporters choose."""
    suffix = PurePath(file_name).suffix.lower()
    if suffix in _EXTENSIONS:
        return _EXTENSIONS[suffix]
    ris, bibtex = _RIS_START.search(text), _BIBTEX_START.search(text)
    if ris and (bibtex is None or ris.start() < bibtex.start()):
        return ImportFormat.RIS
    if bibtex:
        return ImportFormat.BIBTEX
    raise TezError(ErrorCode.IMPORT_UNKNOWN_FORMAT, {"file_name": file_name}, status=422)


def parse_file(file_name: str, data: bytes) -> tuple[ParsedFile, str]:
    """The file's records and issues, and its text (kept as the run's snapshot)."""
    text = decode_text(data)
    match detect_format(file_name, text):
        case ImportFormat.BIBTEX:
            parsed = parse_bibtex(text)
        case ImportFormat.RIS:
            parsed = parse_ris(text)
    return parsed, text


def _issues(issues: list[EntryIssue]) -> list[ImportIssueView]:
    return [ImportIssueView(code=i.code, line=i.line, key=i.key, detail=i.detail) for i in issues]


def _status(match: PreviewMatch) -> PreviewStatus:
    if match.repeats is not None:
        return "repeated"
    if match.paper_id is None:
        return "new"
    return "in_library" if match.in_library else "known"


def _preview_record(entry: ParsedEntry, match: PreviewMatch) -> PreviewRecord:
    record = entry.record
    return PreviewRecord(
        line=entry.line,
        key=entry.key,
        title=record.title,
        first_author=record.authors[0].display_name if record.authors else None,
        author_count=len(record.authors),
        year=record.year,
        venue=record.venue,
        venue_type=record.venue_type,
        doi=record.identifiers.get(IdentifierScheme.DOI),
        warnings=list(entry.warnings),
        status=_status(match),
        match_method=match.method,
    )


def preview(
    db: Database, file_name: str, data: bytes, saved_search_id: str | None = None
) -> ImportPreview:
    """What importing the file would do. Writes nothing."""
    parsed, _ = parse_file(file_name, data)
    earlier = EarlierImports(db, saved_search_id) if saved_search_id is not None else None
    matches = preview_matches(db, parsed.records)
    statuses = Counter(_status(match) for match in matches)
    warnings = Counter(w for entry in parsed.entries for w in entry.warnings)
    return ImportPreview(
        format=parsed.format,
        total=parsed.total,
        readable=len(parsed.entries),
        issues=_issues(parsed.issues),
        new=statuses["new"],
        known=statuses["known"],
        in_library=statuses["in_library"],
        repeated=statuses["repeated"],
        warnings=dict(warnings),
        sample=[
            _preview_record(entry, match)
            for entry, match in zip(parsed.entries[:SAMPLE_SIZE], matches, strict=False)
        ],
        since_last=earlier.compare([m.paper_id for m in matches if m.repeats is None])
        if earlier
        else None,
    )


def _executed_at(request: ImportRequest) -> datetime:
    if request.log is None or request.log.searched_at is None:
        return utcnow()
    day = request.log.searched_at
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def run_import(
    db: Database,
    library_path: Path,
    request: ImportRequest,
    *,
    initiated_via: InitiatedVia = InitiatedVia.GUI,
) -> ImportOutcome:
    data = read_input(request)
    return import_bytes(db, library_path, request, data, initiated_via=initiated_via)


def import_bytes(
    db: Database,
    library_path: Path,
    request: ImportRequest,
    data: bytes,
    *,
    initiated_via: InitiatedVia = InitiatedVia.GUI,
) -> ImportOutcome:
    """Store the file's records; log the run, add to the review or library, as asked."""
    parsed, text = parse_file(request.file_name, data)
    if not parsed.entries:
        params = {"file_name": request.file_name, "issues": len(parsed.issues)}
        raise TezError(ErrorCode.IMPORT_EMPTY, params, status=422)
    if request.review_id is not None and not reviews_service.review_exists(db, request.review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": request.review_id}, status=404)

    run = None
    earlier = None
    if request.log is not None and request.review_id is not None:
        log = request.log
        source, query, query_id = log.source or "", log.query or None, None
        if log.saved_search_id is not None:
            earlier = EarlierImports(db, log.saved_search_id, request.review_id)
            source, query, query_id = earlier.source, earlier.query, log.saved_search_id
        run = ImportRun(
            review_id=request.review_id,
            source=source,
            executed_at=_executed_at(request),
            file_name=request.file_name,
            raw_text=text,
            total_reported=parsed.total,
            skipped=parsed.total - len(parsed.entries),
            query=query,
            query_id=query_id,
            initiated_via=initiated_via,
        )
    stored = store_imported(db, library_path, parsed.records, run)
    paper_ids = list(dict.fromkeys(stored.paper_ids))

    added_to_review = 0
    if request.add_to_review and request.review_id is not None:
        selection = reviews_service.add_papers(db, request.review_id, paper_ids, stored.search_id)
        added_to_review = selection.added
    added_to_library = 0
    if request.add_to_library:
        with db.write_session() as session:
            added_to_library, _ = PaperService(session).keep(paper_ids)

    logger.info(
        "file imported",
        extra={
            "format": parsed.format,
            "records": len(parsed.entries),
            "search_id": stored.search_id,
        },
    )
    return ImportOutcome(
        format=parsed.format,
        total=parsed.total,
        imported=len(parsed.entries),
        issues=_issues(parsed.issues),
        new_papers=stored.new_papers,
        search_id=stored.search_id,
        added_to_review=added_to_review,
        added_to_library=added_to_library,
        since_last=earlier.compare(stored.paper_ids) if earlier else None,
    )
