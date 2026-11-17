"""The decision file: one reviewer's screening decisions for one review (plan, Task 41).

Each person screens in their own library (ADR 0019). A reviewer exports their decisions to this
file and a colleague imports it into their library. Papers have different ids in each library, so
every record carries what is needed to find it again: its identifiers, title, year and first
author, matched with the same rules as search deduplication (Task 12).

The file is a snapshot of the reviewer's decisions in force, at most one per record and stage.
`version` changes whenever a reader of an older version could misread a newer file.
"""

import json
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from tez.core.errors import ErrorCode, TezError
from tez.modules.reviews.models import CriterionKind, Decision, ScreeningStage

FORMAT = "tez.screening-decisions"
VERSION = 1
# Reviewer names this library uses for itself and for reconciled decisions.
RESERVED_REVIEWERS = frozenset({"owner", "consensus", "reconciled"})

_ShortText = Field(min_length=1, max_length=300)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FileAuthor(_Strict):
    display_name: str = Field(min_length=1)
    family: str | None = None


class FileRecord(_Strict):
    # The paper's id in the exporting library: decisions point at it.
    ref: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1)
    year: int | None = None
    first_author: FileAuthor | None = None
    # Free strings, so a newer library's type or scheme does not make the file unreadable.
    venue_type: str | None = None
    identifiers: dict[str, str] = Field(default_factory=dict[str, str])


class FileCriterion(_Strict):
    code: str = Field(min_length=1, max_length=16)
    kind: CriterionKind
    text: str
    stage: ScreeningStage | None = None


class FileDecision(_Strict):
    # The decision's id in the exporting library.
    id: str = Field(min_length=1, max_length=64)
    record: str
    stage: ScreeningStage
    decision: Decision
    criterion: str | None = Field(default=None, max_length=16)
    note: str | None = None
    decided_at: datetime


class FileReview(_Strict):
    id: str = Field(min_length=1, max_length=64)
    title: str = _ShortText
    method: str


class DecisionFile(_Strict):
    format: Literal["tez.screening-decisions"] = FORMAT
    version: Literal[1] = VERSION
    exported_at: datetime
    app_version: str
    reviewer: str = Field(min_length=1, max_length=64)
    review: FileReview
    criteria: list[FileCriterion] = Field(default_factory=list[FileCriterion])
    records: list[FileRecord] = Field(default_factory=list[FileRecord])
    decisions: list[FileDecision] = Field(default_factory=list[FileDecision])

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        refs = [record.ref for record in self.records]
        if len(refs) != len(set(refs)):
            raise ValueError("record refs must be unique")
        known = set(refs)
        seen: set[tuple[str, ScreeningStage]] = set()
        for decision in self.decisions:
            if decision.record not in known:
                raise ValueError(f"decision {decision.id} names an unknown record")
            key = (decision.record, decision.stage)
            if key in seen:
                raise ValueError(f"record {decision.record} has two decisions at one stage")
            seen.add(key)
        codes = [criterion.code for criterion in self.criteria]
        if len(codes) != len(set(codes)):
            raise ValueError("criterion codes must be unique")
        return self


def is_reserved_reviewer(name: str) -> bool:
    return name.strip().casefold() in RESERVED_REVIEWERS


def dump_decision_file(document: DecisionFile) -> str:
    return document.model_dump_json(indent=2) + "\n"


def parse_decision_file(content: str | bytes) -> DecisionFile:
    """Read a decision file, or explain in an error code why it cannot be read."""
    try:
        raw: Any = json.loads(content)
    except (ValueError, UnicodeDecodeError) as error:
        raise TezError(ErrorCode.DECISIONS_INVALID_FILE, {"reason": "not_json"}) from error
    if not isinstance(raw, dict) or raw.get("format") != FORMAT:  # pyright: ignore[reportUnknownMemberType]
        raise TezError(ErrorCode.DECISIONS_INVALID_FILE, {"reason": "not_a_decision_file"})
    version: Any = raw.get("version")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if version != VERSION:
        raise TezError(
            ErrorCode.DECISIONS_UNSUPPORTED_VERSION, {"version": version, "supported": VERSION}
        )
    try:
        document = DecisionFile.model_validate(raw)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise TezError(
            ErrorCode.DECISIONS_INVALID_FILE, {"reason": "invalid", "field": location}
        ) from error
    if is_reserved_reviewer(document.reviewer):
        raise TezError(ErrorCode.DECISIONS_RESERVED_REVIEWER, {"reviewer": document.reviewer})
    return document


def json_schema() -> dict[str, Any]:
    """The published JSON Schema of the current version (docs/formats)."""
    schema = DecisionFile.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return schema
