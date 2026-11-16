from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tez.modules.quality.models import QualityAssessment, QualityQuestion, QualitySetting


class QualityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- the stage switch ----------------------------------------------------------------

    def enabled(self, review_id: str) -> bool:
        setting = self._setting(review_id)
        return setting is not None and setting.enabled

    def set_enabled(self, review_id: str, enabled: bool) -> None:
        setting = self._setting(review_id)
        if setting is None:
            self.session.add(QualitySetting(review_id=review_id, enabled=enabled))
        else:
            setting.enabled = enabled
        self.session.flush()

    def _setting(self, review_id: str) -> QualitySetting | None:
        return self.session.scalars(
            select(QualitySetting).where(QualitySetting.review_id == review_id)
        ).one_or_none()

    # --- questions -----------------------------------------------------------------------

    def questions(self, review_id: str) -> list[QualityQuestion]:
        return list(
            self.session.scalars(
                select(QualityQuestion)
                .where(QualityQuestion.review_id == review_id)
                .order_by(QualityQuestion.sort_order, QualityQuestion.id)
            )
        )

    def get_question(self, review_id: str, question_id: str) -> QualityQuestion | None:
        question = self.session.get(QualityQuestion, question_id)
        return question if question is not None and question.review_id == review_id else None

    def add_questions(
        self,
        review_id: str,
        questions: Iterable[tuple[str, str | None, list[dict[str, Any]]]],
        template: str | None = None,
    ) -> list[QualityQuestion]:
        """Append questions after the last one, in the order given."""
        last = self.session.scalar(
            select(func.max(QualityQuestion.sort_order)).where(
                QualityQuestion.review_id == review_id
            )
        )
        start = -1 if last is None else last
        rows = [
            QualityQuestion(
                review_id=review_id,
                text=text,
                guidance=guidance,
                scale_json=scale,
                sort_order=start + 1 + offset,
                template=template,
            )
            for offset, (text, guidance, scale) in enumerate(questions)
        ]
        self.session.add_all(rows)
        self.session.flush()
        return rows

    def delete_question(self, question: QualityQuestion) -> None:
        self.session.delete(question)
        self.session.flush()

    def used_answers(self, question_id: str) -> set[str]:
        """Scale values some assessment has chosen for this question."""
        answers = self.session.scalars(
            select(QualityAssessment.answer).where(QualityAssessment.question_id == question_id)
        )
        return {answer for answer in answers if answer is not None}

    def is_used(self, question_id: str) -> bool:
        return (
            self.session.scalar(
                select(QualityAssessment.id).where(QualityAssessment.question_id == question_id)
            )
            is not None
        )

    # --- answers -------------------------------------------------------------------------

    def assessments(
        self, review_id: str, paper_ids: Sequence[str] | None = None, reviewer: str = "owner"
    ) -> list[QualityAssessment]:
        query = select(QualityAssessment).where(
            QualityAssessment.review_id == review_id, QualityAssessment.reviewer == reviewer
        )
        if paper_ids is not None:
            query = query.where(QualityAssessment.paper_id.in_(list(paper_ids)))
        return list(self.session.scalars(query.order_by(QualityAssessment.id)))

    def get_assessment(
        self, review_id: str, paper_id: str, question_id: str, reviewer: str = "owner"
    ) -> QualityAssessment | None:
        return self.session.scalars(
            select(QualityAssessment).where(
                QualityAssessment.review_id == review_id,
                QualityAssessment.paper_id == paper_id,
                QualityAssessment.question_id == question_id,
                QualityAssessment.reviewer == reviewer,
            )
        ).one_or_none()

    def save_assessment(
        self,
        review_id: str,
        paper_id: str,
        question_id: str,
        answer: str | None,
        note: str | None,
        reviewer: str = "owner",
    ) -> None:
        """Set or replace an answer. Clearing both the answer and the note removes the row."""
        row = self.get_assessment(review_id, paper_id, question_id, reviewer)
        if answer is None and not note:
            if row is not None:
                self.session.delete(row)
        elif row is None:
            self.session.add(
                QualityAssessment(
                    review_id=review_id,
                    paper_id=paper_id,
                    question_id=question_id,
                    answer=answer,
                    note=note or None,
                    reviewer=reviewer,
                )
            )
        else:
            row.answer = answer
            row.note = note or None
        self.session.flush()
