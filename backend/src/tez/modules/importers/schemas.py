from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tez.modules.importers.parsing import ImportFormat, IssueCode, RecordWarning
from tez.modules.library.models import VenueType
from tez.modules.search.models import InitiatedVia, MatchMethod

# Base64 of a 30 MB export; IEEE Xplore caps an export at 2000 records, far below this.
MAX_CONTENT_LENGTH = 40_000_000
SAMPLE_SIZE = 5


class ImportFile(BaseModel):
    """The file to read: its bytes (from a browser) or its path on this computer (from the
    desktop app's "open with" and the terminal). Exactly one of the two."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    file_name: str = Field(min_length=1, max_length=255)
    # The file's bytes, base64: the server decodes them (UTF-8, else Windows-1252).
    content_base64: str | None = Field(default=None, min_length=1, max_length=MAX_CONTENT_LENGTH)
    path: str | None = Field(default=None, min_length=1, max_length=4096)

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if (self.content_base64 is None) == (self.path is None):
            raise ValueError("give either content_base64 or path")
        return self


class ImportLog(BaseModel):
    """Log the import as a search run: the systematic record of a database search."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source: str = Field(min_length=1, max_length=64, examples=["IEEE Xplore"])
    # The day the search ran at the source; today if not given.
    searched_at: date | None = None
    query: str | None = Field(default=None, max_length=4000)


class ImportRequest(ImportFile):
    review_id: str | None = None
    log: ImportLog | None = None
    add_to_review: bool = False
    add_to_library: bool = False
    # `tez import` says "cli", so the logged run shows where it was started.
    initiated_via: InitiatedVia = InitiatedVia.GUI

    @model_validator(mode="after")
    def _has_a_target(self) -> Self:
        if self.log is None and not self.add_to_review and not self.add_to_library:
            raise ValueError("an import needs a target: log, add_to_review or add_to_library")
        if (self.log is not None or self.add_to_review) and self.review_id is None:
            raise ValueError("log and add_to_review need review_id")
        return self


class ImportIssueView(BaseModel):
    code: IssueCode
    line: int | None
    key: str | None
    detail: str | None


PreviewStatus = Literal["new", "known", "in_library", "repeated"]


class PreviewRecord(BaseModel):
    line: int | None
    key: str | None
    title: str
    first_author: str | None
    author_count: int
    year: int | None
    venue: str | None
    venue_type: VenueType | None
    doi: str | None
    warnings: list[RecordWarning]
    status: PreviewStatus
    match_method: MatchMethod


class ImportPreview(BaseModel):
    format: ImportFormat
    # Entries in the file; `readable` of them can be imported, `issues` says why not the rest.
    total: int
    readable: int
    issues: list[ImportIssueView]
    new: int
    known: int
    in_library: int
    repeated: int
    warnings: dict[RecordWarning, int]
    sample: list[PreviewRecord]


class ImportOutcome(BaseModel):
    format: ImportFormat
    total: int
    imported: int
    issues: list[ImportIssueView]
    new_papers: int
    search_id: str | None
    added_to_review: int
    added_to_library: int
