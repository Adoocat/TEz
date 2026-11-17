"""Agreement between two reviewers and the conflicts to reconcile (plan, Task 42).

Decisions are compared by what they do to a record, not by their label (owner's choice,
Nov 14, 2026). At title-abstract, "include" and "maybe" both send a record to full text, so they
agree; only "advances" against "exclude" is a conflict. At full text, include, exclude and maybe
are three outcomes. Two exclusions agree even when their criteria differ.

Cohen's kappa compares the two reviewers' own decisions, before any reconciliation, over the
records both of them decided at that stage.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from tez.modules.reviews.models import Decision, ScreeningStage

ADVANCES = "advances"


def outcome(stage: ScreeningStage, decision: Decision) -> str:
    """The category a decision falls in for agreement and conflicts."""
    if stage is ScreeningStage.TITLE_ABSTRACT and decision is not Decision.EXCLUDE:
        return ADVANCES
    return decision.value


def cohen_kappa(pairs: Iterable[tuple[str, str]]) -> float | None:
    """Cohen's kappa of paired categories; None when it is undefined.

    Kappa is (po - pe) / (1 - pe). It is undefined with no pairs, and when chance agreement is
    already certain (both reviewers used one and the same category throughout).
    """
    pairs = list(pairs)
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(1 for first, second in pairs if first == second) / n
    firsts = Counter(first for first, _ in pairs)
    seconds = Counter(second for _, second in pairs)
    expected = sum(firsts[c] * seconds[c] for c in firsts.keys() & seconds.keys()) / (n * n)
    if expected == 1:
        return None
    return (observed - expected) / (1 - expected)


@dataclass(frozen=True)
class StageAgreement:
    stage: ScreeningStage
    # Records both reviewers decided at this stage.
    compared: int
    agreed: int
    kappa: float | None

    @property
    def percent(self) -> float | None:
        return 100 * self.agreed / self.compared if self.compared else None


def stage_agreement(
    stage: ScreeningStage, first: Mapping[str, Decision], second: Mapping[str, Decision]
) -> StageAgreement:
    """Agreement of two reviewers' decisions in force, each keyed by paper id."""
    pairs = [
        (outcome(stage, first[paper_id]), outcome(stage, second[paper_id]))
        for paper_id in sorted(first.keys() & second.keys())
    ]
    agreed = sum(1 for a, b in pairs if a == b)
    return StageAgreement(stage, len(pairs), agreed, cohen_kappa(pairs))


def conflicting_papers(
    stage: ScreeningStage,
    first: Mapping[str, Decision],
    second: Mapping[str, Decision],
    reconciled: Iterable[str],
) -> list[str]:
    """Papers both reviewers decided differently and nobody has reconciled yet."""
    settled = set(reconciled)
    return [
        paper_id
        for paper_id in sorted(first.keys() & second.keys())
        if paper_id not in settled
        and outcome(stage, first[paper_id]) != outcome(stage, second[paper_id])
    ]
