"""Which rows importing a decision file adds, worked out before anything is written (Task 41).

`screening_decision` is append-only, so importing compares the file with the decisions already
imported for that reviewer: a decision that is the same adds nothing (importing a file twice
creates no rows), a changed decision is a correction that supersedes the earlier imported row, and
a decision with no imported row yet is added.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from tez.modules.dual_screening.fileformat import DecisionFile, FileDecision
from tez.modules.dual_screening.matching import RecordMatch
from tez.modules.reviews.models import Decision, ScreeningStage

_STAGE_ORDER = {ScreeningStage.TITLE_ABSTRACT: 0, ScreeningStage.FULL_TEXT: 1}

type DecisionKey = tuple[str, ScreeningStage]  # paper id, stage


@dataclass(frozen=True)
class ExistingDecision:
    """A decision in force for the imported reviewer, as this library holds it."""

    id: str
    decision: Decision
    criterion_id: str | None
    note: str | None


@dataclass(frozen=True)
class PlannedDecision:
    paper_id: str
    stage: ScreeningStage
    decision: Decision
    criterion_id: str | None
    note: str | None
    # The imported row this one corrects; None for a first decision.
    supersedes_id: str | None
    # The decision's id in the exporting library.
    source_id: str


@dataclass(frozen=True)
class ImportPlan:
    writes: list[PlannedDecision]
    unchanged: int
    # Decisions of records that matched no paper of the review.
    unmatched_decisions: int
    # Criterion codes of the file this review does not have, with how many decisions use each.
    unknown_criteria: dict[str, int] = field(default_factory=dict[str, int])
    # Imported decisions in force that the file no longer has (left as they are).
    withdrawn: int = 0

    @property
    def added(self) -> int:
        return sum(1 for write in self.writes if write.supersedes_id is None)

    @property
    def corrected(self) -> int:
        return sum(1 for write in self.writes if write.supersedes_id is not None)


def _note(note: str | None) -> str | None:
    return (note.strip() or None) if note else None


def _ordered(decisions: Iterable[FileDecision]) -> list[FileDecision]:
    """Title-abstract decisions first, so a full-text decision never precedes its basis."""
    return sorted(decisions, key=lambda decision: _STAGE_ORDER[decision.stage])


def plan_import(
    document: DecisionFile,
    matches: Iterable[RecordMatch],
    criterion_ids: Mapping[str, str],
    existing: Mapping[DecisionKey, ExistingDecision],
) -> ImportPlan:
    """The rows to append so the reviewer's imported decisions equal the file.

    `criterion_ids` maps this review's criterion codes to ids; `existing` holds the reviewer's
    decisions in force, keyed by paper and stage.
    """
    papers = {match.ref: match.paper_id for match in matches if match.paper_id is not None}
    writes: list[PlannedDecision] = []
    covered: set[DecisionKey] = set()
    unchanged = unmatched = 0
    unknown: dict[str, int] = {}
    for decision in _ordered(document.decisions):
        paper_id = papers.get(decision.record)
        if paper_id is None:
            unmatched += 1
            continue
        key = (paper_id, decision.stage)
        covered.add(key)
        criterion_id: str | None = None
        if decision.criterion is not None:
            criterion_id = criterion_ids.get(decision.criterion)
            if criterion_id is None:
                unknown[decision.criterion] = unknown.get(decision.criterion, 0) + 1
                continue
        note = _note(decision.note)
        previous = existing.get(key)
        if previous is not None and (
            previous.decision,
            previous.criterion_id,
            _note(previous.note),
        ) == (decision.decision, criterion_id, note):
            unchanged += 1
            continue
        writes.append(
            PlannedDecision(
                paper_id=paper_id,
                stage=decision.stage,
                decision=decision.decision,
                criterion_id=criterion_id,
                note=note,
                supersedes_id=previous.id if previous else None,
                source_id=decision.id,
            )
        )
    withdrawn = sum(1 for key in existing if key not in covered)
    return ImportPlan(writes, unchanged, unmatched, unknown, withdrawn)
