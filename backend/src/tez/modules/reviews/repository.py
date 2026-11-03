from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from tez.core.errors import ErrorCode, TezError
from tez.modules.reviews.models import (
    CriterionKind,
    Decision,
    RecordOrigin,
    Review,
    ReviewMethod,
    ReviewRecord,
    ScreeningCriterion,
    ScreeningDecision,
    ScreeningStage,
)


class ReviewsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_review(
        self,
        title: str,
        *,
        method: ReviewMethod,
        research_questions_md: str | None = None,
        protocol_md: str | None = None,
    ) -> Review:
        review = Review(
            title=title,
            method=method,
            research_questions_md=research_questions_md,
            protocol_md=protocol_md,
        )
        self.session.add(review)
        self.session.flush()
        return review

    def get_review(self, review_id: str) -> Review | None:
        return self.session.get(Review, review_id)

    def add_record(
        self,
        review_id: str,
        paper_id: str,
        origin: RecordOrigin,
        origin_ref: str | None = None,
    ) -> ReviewRecord:
        record = ReviewRecord(
            review_id=review_id, paper_id=paper_id, origin=origin, origin_ref=origin_ref
        )
        self.session.add(record)
        self.session.flush()
        return record

    def records(self, review_id: str) -> list[ReviewRecord]:
        return list(
            self.session.scalars(
                select(ReviewRecord)
                .where(ReviewRecord.review_id == review_id)
                .order_by(ReviewRecord.created_at)
            )
        )

    def add_criterion(
        self,
        review_id: str,
        kind: CriterionKind,
        code: str,
        text: str,
        stage: ScreeningStage | None = None,
    ) -> ScreeningCriterion:
        criterion = ScreeningCriterion(
            review_id=review_id, kind=kind, code=code, text=text, stage=stage
        )
        self.session.add(criterion)
        self.session.flush()
        return criterion

    def criteria(self, review_id: str) -> list[ScreeningCriterion]:
        return list(
            self.session.scalars(
                select(ScreeningCriterion)
                .where(ScreeningCriterion.review_id == review_id)
                .order_by(ScreeningCriterion.code)
            )
        )

    def decide(
        self,
        review_id: str,
        paper_id: str,
        stage: ScreeningStage,
        decision: Decision,
        *,
        criterion_id: str | None = None,
        note: str | None = None,
        reviewer: str = "owner",
        supersedes_id: str | None = None,
    ) -> ScreeningDecision:
        """Record a decision. A correction is a new row that names the one it replaces."""
        if supersedes_id is not None:
            previous = self.session.get(ScreeningDecision, supersedes_id)
            if previous is None or (previous.review_id, previous.paper_id, previous.stage) != (
                review_id,
                paper_id,
                stage,
            ):
                raise TezError(
                    ErrorCode.SCREENING_INVALID_CORRECTION, {"supersedes_id": supersedes_id}
                )
        row = ScreeningDecision(
            review_id=review_id,
            paper_id=paper_id,
            stage=stage,
            decision=decision,
            criterion_id=criterion_id,
            note=note,
            reviewer=reviewer,
            supersedes_id=supersedes_id,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def current_decisions(self, review_id: str, stage: ScreeningStage) -> list[ScreeningDecision]:
        """Decisions in force: those no later row corrects."""
        correction = aliased(ScreeningDecision)
        return list(
            self.session.scalars(
                select(ScreeningDecision)
                .outerjoin(correction, correction.supersedes_id == ScreeningDecision.id)
                .where(
                    ScreeningDecision.review_id == review_id,
                    ScreeningDecision.stage == stage,
                    correction.id.is_(None),
                )
                .order_by(ScreeningDecision.created_at, ScreeningDecision.id)
            )
        )

    def history(self, review_id: str, paper_id: str) -> list[ScreeningDecision]:
        return list(
            self.session.scalars(
                select(ScreeningDecision)
                .where(
                    ScreeningDecision.review_id == review_id,
                    ScreeningDecision.paper_id == paper_id,
                )
                .order_by(ScreeningDecision.created_at, ScreeningDecision.id)
            )
        )
