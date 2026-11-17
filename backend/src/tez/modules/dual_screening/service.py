"""Moving screening decisions between libraries (plan, Task 41; ADR 0019).

Each person screens in their own library. Exporting writes the owner's decisions in force, under
a name they choose, to a decision file (`fileformat`). Importing matches the file's records to
this review (`matching`), works out the rows to append (`planning`) and writes them through the
screening service under the file's reviewer name, so every rule of Task 31 holds for them too.
Rows are only ever appended: importing the same file again writes nothing, and a decision that
changed in the colleague's library supersedes the imported one.
"""

from collections.abc import Mapping
from datetime import UTC, datetime

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.dual_screening.agreement import conflicting_papers, stage_agreement
from tez.modules.dual_screening.building import (
    CriterionInfo,
    DecisionInfo,
    ReviewInfo,
    build_file,
)
from tez.modules.dual_screening.fileformat import (
    DecisionFile,
    is_reserved_reviewer,
    parse_decision_file,
)
from tez.modules.dual_screening.matching import match_records
from tez.modules.dual_screening.planning import DecisionKey, ExistingDecision, plan_import
from tez.modules.dual_screening.schemas import (
    AgreementView,
    ConflictList,
    ConflictView,
    ImportReport,
    Reconciliation,
    SideDecision,
    SkippedDecision,
    StageAgreementView,
    UnknownCriterion,
    UnmatchedRecord,
)
from tez.modules.library.paper_service import PaperService
from tez.modules.reviews import service as reviews_service
from tez.modules.reviews.models import Decision, ScreeningStage
from tez.modules.reviews.schemas import CriterionView
from tez.modules.screening.schemas import DecisionView
from tez.modules.screening.service import (
    CONSENSUS_REVIEWER,
    LOCAL_REVIEWER,
    CurrentDecision,
    ScreeningService,
    decision_view,
)


def _reviewer_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > 64:
        raise TezError(ErrorCode.REQUEST_INVALID, {"reviewer": name})
    if is_reserved_reviewer(cleaned):
        raise TezError(ErrorCode.DECISIONS_RESERVED_REVIEWER, {"reviewer": cleaned})
    return cleaned


def export_decisions(
    db: Database, review_id: str, reviewer: str, *, now: datetime | None = None
) -> DecisionFile:
    """The owner's decisions in force, both stages, as a file under the name `reviewer`."""
    name = _reviewer_name(reviewer)
    review = reviews_service.get_review(db, review_id)
    criteria = reviews_service.list_criteria(db, review_id)
    codes = {criterion.id: criterion.code for criterion in criteria}
    with db.session() as session:
        screening = ScreeningService(session)
        decisions = [
            DecisionInfo(
                id=current.decision_id,
                paper_id=current.paper_id,
                stage=stage,
                decision=current.decision,
                criterion_code=codes.get(current.criterion_id) if current.criterion_id else None,
                note=current.note,
                decided_at=current.decided_at,
            )
            for stage in ScreeningStage
            for current in screening.current(review_id, stage).values()
        ]
        cards = PaperService(session).cards({decision.paper_id for decision in decisions})
    return build_file(
        review=ReviewInfo(review.id, review.title, review.method),
        reviewer=name,
        criteria=[CriterionInfo(c.code, c.kind, c.text, c.stage) for c in criteria],
        decisions=decisions,
        cards=cards,
        exported_at=now or datetime.now(UTC),
    )


def import_decisions(db: Database, review_id: str, content: str) -> ImportReport:
    """Append the file's decisions to this review under the file's reviewer name."""
    if not reviews_service.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
    document = parse_decision_file(content)
    reviewer = _reviewer_name(document.reviewer)
    matches = match_records(db, review_id, document.records)
    criterion_ids = {c.code: c.id for c in reviews_service.list_criteria(db, review_id)}
    skipped: list[SkippedDecision] = []
    with db.write_session() as session:
        screening = ScreeningService(session)
        existing: dict[DecisionKey, ExistingDecision] = {
            (paper_id, stage): ExistingDecision(
                current.decision_id, current.decision, current.criterion_id, current.note
            )
            for stage in ScreeningStage
            for paper_id, current in screening.current(review_id, stage, reviewer).items()
        }
        plan = plan_import(document, matches, criterion_ids, existing)
        for write in plan.writes:
            try:
                screening.decide(
                    review_id,
                    write.paper_id,
                    write.stage,
                    write.decision,
                    criterion_id=write.criterion_id,
                    note=write.note,
                    reviewer=reviewer,
                )
            except TezError as error:
                # A rule of this review refuses it (an archived criterion, a full-text decision
                # whose title-abstract one was skipped): report it, keep the others.
                skipped.append(
                    SkippedDecision(source_id=write.source_id, stage=write.stage, code=error.code)
                )
    titles = {record.ref: record.title for record in document.records}
    unmatched = [
        UnmatchedRecord(ref=match.ref, title=titles[match.ref], problem=match.problem)
        for match in matches
        if match.problem is not None
    ]
    skipped_ids = {item.source_id for item in skipped}
    written = [write for write in plan.writes if write.source_id not in skipped_ids]
    return ImportReport(
        reviewer=reviewer,
        records=len(document.records),
        matched=len(document.records) - len(unmatched),
        added=sum(1 for write in written if write.supersedes_id is None),
        corrected=sum(1 for write in written if write.supersedes_id is not None),
        unchanged=plan.unchanged,
        withdrawn=plan.withdrawn,
        unmatched=unmatched,
        unknown_criteria=[
            UnknownCriterion(code=code, decisions=count)
            for code, count in sorted(plan.unknown_criteria.items())
        ],
        skipped=skipped,
    )


def reviewers(db: Database, review_id: str) -> list[str]:
    """Who has decided in the review: the owner, colleagues imported, and `consensus`."""
    if not reviews_service.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
    with db.session() as session:
        found = ScreeningService(session).reviewers(review_id)
    return sorted(found, key=lambda name: (name != LOCAL_REVIEWER, name.casefold()))


# --- Agreement, conflicts and reconciliation (Task 42) -------------------------------------


def _colleagues(screening: ScreeningService, review_id: str) -> list[str]:
    found = screening.reviewers(review_id)
    return sorted(
        (r for r in found if r not in (LOCAL_REVIEWER, CONSENSUS_REVIEWER)), key=str.casefold
    )


def _colleague(screening: ScreeningService, review_id: str, reviewer: str | None) -> str | None:
    """The colleague to compare with: the one asked for, else the first by name."""
    colleagues = _colleagues(screening, review_id)
    if reviewer is None:
        return colleagues[0] if colleagues else None
    if reviewer not in colleagues:
        raise TezError(ErrorCode.REQUEST_INVALID, {"reviewer": reviewer})
    return reviewer


def _decisions(
    screening: ScreeningService, review_id: str, stage: ScreeningStage, reviewer: str
) -> dict[str, Decision]:
    return {
        paper_id: current.decision
        for paper_id, current in screening.current(review_id, stage, reviewer).items()
    }


def agreement(db: Database, review_id: str, reviewer: str | None = None) -> AgreementView:
    """Per stage: how often the owner and the colleague agree, with Cohen's kappa, over the
    records both decided; and how many disagreements are still open."""
    if not reviews_service.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
    with db.session() as session:
        screening = ScreeningService(session)
        colleague = _colleague(screening, review_id, reviewer)
        stages: list[StageAgreementView] = []
        for stage in ScreeningStage:
            if colleague is None:
                stages.append(
                    StageAgreementView(
                        stage=stage, compared=0, agreed=0, percent=None, kappa=None, conflicts=0
                    )
                )
                continue
            owner = _decisions(screening, review_id, stage, LOCAL_REVIEWER)
            other = _decisions(screening, review_id, stage, colleague)
            result = stage_agreement(stage, owner, other)
            reconciled = screening.current(review_id, stage, CONSENSUS_REVIEWER)
            stages.append(
                StageAgreementView(
                    stage=stage,
                    compared=result.compared,
                    agreed=result.agreed,
                    percent=result.percent,
                    kappa=result.kappa,
                    conflicts=len(conflicting_papers(stage, owner, other, reconciled)),
                )
            )
        return AgreementView(
            reviewer=colleague, reviewers=_colleagues(screening, review_id), stages=stages
        )


def _side(current: CurrentDecision, criteria: Mapping[str, CriterionView]) -> SideDecision:
    criterion = criteria.get(current.criterion_id) if current.criterion_id else None
    return SideDecision(
        decision=current.decision,
        criterion_code=criterion.code if criterion else None,
        criterion_text=criterion.text if criterion else None,
        note=current.note,
    )


def conflicts(
    db: Database, review_id: str, stage: ScreeningStage, reviewer: str | None = None
) -> ConflictList:
    """Records the owner and the colleague decided differently and nobody has reconciled,
    in the review's order, with both decisions side by side."""
    if not reviews_service.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
    criteria = {c.id: c for c in reviews_service.list_criteria(db, review_id)}
    with db.session() as session:
        screening = ScreeningService(session)
        colleague = _colleague(screening, review_id, reviewer)
        if colleague is None:
            return ConflictList(reviewer=None, stage=stage, items=[])
        owner = screening.current(review_id, stage, LOCAL_REVIEWER)
        other = screening.current(review_id, stage, colleague)
        still_open = set(
            conflicting_papers(
                stage,
                {paper_id: c.decision for paper_id, c in owner.items()},
                {paper_id: c.decision for paper_id, c in other.items()},
                screening.current(review_id, stage, CONSENSUS_REVIEWER),
            )
        )
        order = [
            paper_id
            for paper_id in screening.queue(review_id, ScreeningStage.TITLE_ABSTRACT)
            if paper_id in still_open
        ]
        cards = PaperService(session).cards(order)
        items: list[ConflictView] = []
        for paper_id in order:
            card = cards[paper_id]
            items.append(
                ConflictView(
                    paper_id=paper_id,
                    title=card.paper.title,
                    first_author=card.first_author.display_name if card.first_author else None,
                    author_count=card.author_count,
                    year=card.paper.year,
                    venue=card.paper.venue,
                    owner=_side(owner[paper_id], criteria),
                    other=_side(other[paper_id], criteria),
                )
            )
        return ConflictList(reviewer=colleague, stage=stage, items=items)


def reconcile(
    db: Database, review_id: str, stage: ScreeningStage, body: Reconciliation
) -> DecisionView:
    """The agreed decision for a conflict, as a new `consensus` row. PRISMA and the included
    studies read it in place of the owner's."""
    with db.write_session() as session:
        row = ScreeningService(session).decide(
            review_id,
            body.paper_id,
            stage,
            Decision(body.decision.value),
            criterion_id=body.criterion_id,
            note=body.note or None,
            reviewer=CONSENSUS_REVIEWER,
        )
        return decision_view(row)
