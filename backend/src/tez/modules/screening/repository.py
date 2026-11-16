"""Queries on `screening_decision`. The table is append-only: this only inserts and reads."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, aliased

from tez.modules.reviews.models import Decision, ScreeningDecision, ScreeningStage


@dataclass(frozen=True)
class Head:
    """The decision in force for one record, stage and reviewer: the one nothing corrects."""

    id: str
    paper_id: str
    decision: Decision
    criterion_id: str | None
    note: str | None
    created_at: datetime


class ScreeningRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def heads(
        self, review_id: str, stage: ScreeningStage, reviewer: str, paper_id: str | None = None
    ) -> dict[str, Head]:
        """Current decision per paper. Should a paper have two uncorrected rows (written
        outside this module), the later one wins."""
        correction = aliased(ScreeningDecision)
        d = ScreeningDecision
        query = (
            select(d.id, d.paper_id, d.decision, d.criterion_id, d.note, d.created_at)
            .where(
                d.review_id == review_id,
                d.stage == stage,
                d.reviewer == reviewer,
                ~exists().where(correction.supersedes_id == d.id),
            )
            .order_by(d.created_at, d.id)
        )
        if paper_id is not None:
            query = query.where(d.paper_id == paper_id)
        return {row.paper_id: Head(*row) for row in self.session.execute(query)}

    def get(self, decision_id: str) -> ScreeningDecision | None:
        return self.session.get(ScreeningDecision, decision_id)

    def add(
        self,
        review_id: str,
        paper_id: str,
        stage: ScreeningStage,
        decision: Decision,
        *,
        criterion_id: str | None,
        note: str | None,
        reviewer: str,
        supersedes_id: str | None,
    ) -> ScreeningDecision:
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

    def reviewers(self, review_id: str) -> list[str]:
        return list(
            self.session.scalars(
                select(ScreeningDecision.reviewer)
                .where(ScreeningDecision.review_id == review_id)
                .distinct()
                .order_by(ScreeningDecision.reviewer)
            )
        )
