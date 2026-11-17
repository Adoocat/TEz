"""Write one reviewer's decisions as a decision file (plan, Task 41)."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from tez import __version__
from tez.modules.dual_screening.fileformat import (
    DecisionFile,
    FileAuthor,
    FileCriterion,
    FileDecision,
    FileRecord,
    FileReview,
)
from tez.modules.library.paper_service import PaperCard
from tez.modules.reviews.models import (
    CriterionKind,
    Decision,
    ReviewMethod,
    ScreeningStage,
)


@dataclass(frozen=True)
class ReviewInfo:
    id: str
    title: str
    method: ReviewMethod


@dataclass(frozen=True)
class CriterionInfo:
    code: str
    kind: CriterionKind
    text: str
    stage: ScreeningStage | None


@dataclass(frozen=True)
class DecisionInfo:
    """A decision in force, as the screening service reports it."""

    id: str
    paper_id: str
    stage: ScreeningStage
    decision: Decision
    criterion_code: str | None
    note: str | None
    decided_at: datetime


def file_record(card: PaperCard) -> FileRecord:
    first = card.first_author
    return FileRecord(
        ref=card.paper.id,
        title=card.paper.title,
        year=card.paper.year,
        first_author=FileAuthor(display_name=first.display_name, family=first.family)
        if first
        else None,
        venue_type=card.paper.venue_type.value if card.paper.venue_type else None,
        identifiers={scheme.value: value for scheme, value in sorted(card.identifiers.items())},
    )


def build_file(
    *,
    review: ReviewInfo,
    reviewer: str,
    criteria: Iterable[CriterionInfo],
    decisions: Sequence[DecisionInfo],
    cards: Mapping[str, PaperCard],
    exported_at: datetime,
) -> DecisionFile:
    """A file with the given decisions and only the records they need, in a stable order."""
    paper_ids = sorted({decision.paper_id for decision in decisions})
    return DecisionFile(
        exported_at=exported_at,
        app_version=__version__,
        reviewer=reviewer,
        review=FileReview(id=review.id, title=review.title, method=review.method.value),
        criteria=[
            FileCriterion(code=c.code, kind=c.kind, text=c.text, stage=c.stage)
            for c in sorted(criteria, key=lambda c: c.code)
        ],
        records=[file_record(cards[paper_id]) for paper_id in paper_ids],
        decisions=[
            FileDecision(
                id=d.id,
                record=d.paper_id,
                stage=d.stage,
                decision=d.decision,
                criterion=d.criterion_code,
                note=d.note,
                decided_at=d.decided_at,
            )
            for d in sorted(decisions, key=lambda d: (d.paper_id, d.stage.value))
        ],
    )
