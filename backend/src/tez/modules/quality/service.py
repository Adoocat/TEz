"""Quality assessment for the API and the review panel (Task 38, ADR 0026).

The stage is optional and tool-neutral: a review brings its own questions and scales, or
copies a bundled template. Only papers included at full-text screening are assessed;
which those are comes from the screening service. Totals and progress are derived.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.library.paper_service import PaperService
from tez.modules.quality.models import QualityAssessment, QualityQuestion
from tez.modules.quality.repository import QualityRepository
from tez.modules.quality.schemas import (
    AnswerPut,
    AnswerView,
    PaperAssessment,
    PaperQualityRow,
    PresetOptionView,
    QualityCatalog,
    QualitySummary,
    QualityView,
    QuestionCreate,
    QuestionPatch,
    QuestionView,
    Scale,
    ScaleOption,
    ScalePresetView,
    TemplateView,
)
from tez.modules.quality.templates import SCALES, TEMPLATES, Language, ScalePreset
from tez.modules.reviews import service as reviews
from tez.modules.reviews.models import ScreeningStage
from tez.modules.screening.service import ScreeningService

# --- catalog --------------------------------------------------------------------------------


def catalog() -> QualityCatalog:
    return QualityCatalog(
        templates=[
            TemplateView(
                key=t.key,
                title=t.title,
                publisher=t.publisher,
                design=t.design,
                version=t.version,
                license=t.license,
                source_url=t.source_url,
                questions=list(t.questions),
                scale=t.scale,
                rating_question=t.rating_question,
                rating_scale=t.rating_scale,
            )
            for t in TEMPLATES.values()
        ],
        scales=[
            ScalePresetView(
                key=preset.key,
                options=[
                    PresetOptionView(value=o.value, labels=dict(o.labels), score=o.score)
                    for o in preset.options
                ],
            )
            for preset in SCALES.values()
        ],
    )


def _localized(preset: ScalePreset, language: Language) -> list[dict[str, Any]]:
    return [
        {"value": o.value, "label": o.labels[language], "score": o.score} for o in preset.options
    ]


# --- question set ---------------------------------------------------------------------------


def _question_view(question: QualityQuestion) -> QuestionView:
    return QuestionView(
        id=question.id,
        text=question.text,
        guidance=question.guidance,
        scale=[ScaleOption.model_validate(option) for option in question.scale_json],
        sort_order=question.sort_order,
        template=question.template,
    )


def _require_review(db: Database, review_id: str) -> None:
    if not reviews.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)


def _require_question(
    repository: QualityRepository, review_id: str, question_id: str
) -> QualityQuestion:
    question = repository.get_question(review_id, question_id)
    if question is None:
        raise TezError(
            ErrorCode.QUALITY_QUESTION_NOT_FOUND, {"question_id": question_id}, status=404
        )
    return question


def get_quality(db: Database, review_id: str) -> QualityView:
    _require_review(db, review_id)
    with db.session() as session:
        repository = QualityRepository(session)
        return QualityView(
            enabled=repository.enabled(review_id),
            questions=[_question_view(q) for q in repository.questions(review_id)],
        )


def set_enabled(db: Database, review_id: str, enabled: bool) -> QualityView:
    """Turn the stage on or off. Off only hides it: questions and answers are kept."""
    _require_review(db, review_id)
    with db.write_session() as session:
        QualityRepository(session).set_enabled(review_id, enabled)
    return get_quality(db, review_id)


def add_questions(
    db: Database, review_id: str, questions: Sequence[QuestionCreate]
) -> list[QuestionView]:
    _require_review(db, review_id)
    with db.write_session() as session:
        rows = QualityRepository(session).add_questions(
            review_id,
            [(q.text, q.guidance, q.scale.model_dump()["options"]) for q in questions],
        )
        return [_question_view(row) for row in rows]


def apply_template(
    db: Database, review_id: str, template_key: str, language: Language
) -> list[QuestionView]:
    """Copy a bundled checklist into the review, after any questions it already has."""
    template = TEMPLATES.get(template_key)
    if template is None:
        raise TezError(ErrorCode.QUALITY_TEMPLATE_UNKNOWN, {"template": template_key}, status=404)
    _require_review(db, review_id)
    scale = _localized(SCALES[template.scale], language)
    with db.write_session() as session:
        repository = QualityRepository(session)
        rows = repository.add_questions(
            review_id, [(text, None, scale) for text in template.questions], template.key
        )
        if template.rating_question and template.rating_scale:
            rating = _localized(SCALES[template.rating_scale], language)
            rows += repository.add_questions(
                review_id, [(template.rating_question, None, rating)], template.key
            )
        return [_question_view(row) for row in rows]


def update_question(
    db: Database, review_id: str, question_id: str, patch: QuestionPatch
) -> QuestionView:
    """Edit a question. A scale change may relabel or rescore, never drop a used value."""
    _require_review(db, review_id)
    with db.write_session() as session:
        repository = QualityRepository(session)
        question = _require_question(repository, review_id, question_id)
        if patch.text is not None:
            question.text = patch.text
        if "guidance" in patch.model_fields_set:
            question.guidance = patch.guidance or None
        if patch.scale is not None:
            _check_scale_keeps_answers(repository, question_id, patch.scale)
            question.scale_json = patch.scale.model_dump()["options"]
        session.flush()
        return _question_view(question)


def _check_scale_keeps_answers(
    repository: QualityRepository, question_id: str, scale: Scale
) -> None:
    kept = {option.value for option in scale.options}
    if lost := repository.used_answers(question_id) - kept:
        raise TezError(ErrorCode.QUALITY_SCALE_VALUE_IN_USE, {"values": sorted(lost)}, status=409)


def delete_question(db: Database, review_id: str, question_id: str) -> None:
    """Remove a question nobody has answered yet; an answered one is refused."""
    _require_review(db, review_id)
    with db.write_session() as session:
        repository = QualityRepository(session)
        question = _require_question(repository, review_id, question_id)
        if repository.is_used(question_id):
            raise TezError(
                ErrorCode.QUALITY_QUESTION_IN_USE, {"question_id": question_id}, status=409
            )
        repository.delete_question(question)


def reorder_questions(
    db: Database, review_id: str, question_ids: Sequence[str]
) -> list[QuestionView]:
    """Put the questions in the given order; it must name each question exactly once."""
    _require_review(db, review_id)
    with db.write_session() as session:
        repository = QualityRepository(session)
        questions = {q.id: q for q in repository.questions(review_id)}
        if len(question_ids) != len(questions) or set(question_ids) != set(questions):
            raise TezError(ErrorCode.QUALITY_ORDER_MISMATCH)
        for position, question_id in enumerate(question_ids):
            questions[question_id].sort_order = position
        session.flush()
        return [_question_view(questions[question_id]) for question_id in question_ids]


# --- assessing papers -----------------------------------------------------------------------


def _included_paper_ids(db: Database, review_id: str) -> list[str]:
    """Papers whose current full-text decision is include, in the screening service's order."""
    with db.session() as session:
        return ScreeningService(session).included(review_id, ScreeningStage.FULL_TEXT)


def _require_included(db: Database, review_id: str, paper_id: str) -> None:
    if paper_id not in _included_paper_ids(db, review_id):
        raise TezError(ErrorCode.QUALITY_PAPER_NOT_INCLUDED, {"paper_id": paper_id}, status=409)


def _answer_view(row: QualityAssessment) -> AnswerView:
    return AnswerView(
        question_id=row.question_id, answer=row.answer, note=row.note, updated_at=row.updated_at
    )


def _score(
    questions: Sequence[QualityQuestion], answers: dict[str, str | None]
) -> tuple[float | None, float | None]:
    """Sum of chosen scores, out of the best reachable for the questions that count.

    A question counts when its scale has scores and it is unanswered or answered with a
    scored option; "Not applicable"-style options (no score) take it out of the maximum.
    """
    total = maximum = 0.0
    scored = False
    for question in questions:
        scores = {o["value"]: o.get("score") for o in question.scale_json}
        numeric = [s for s in scores.values() if s is not None]
        if not numeric:
            continue
        chosen = answers.get(question.id)
        if chosen is not None and scores.get(chosen) is None:
            continue
        scored = True
        maximum += max(numeric)
        if chosen is not None:
            total += scores[chosen] or 0.0
    return (total, maximum) if scored else (None, None)


def papers(db: Database, review_id: str) -> list[PaperQualityRow]:
    """Included papers with their progress and derived total, in screening order."""
    _require_review(db, review_id)
    paper_ids = _included_paper_ids(db, review_id)
    with db.session() as session:
        repository = QualityRepository(session)
        questions = repository.questions(review_id)
        by_paper: dict[str, dict[str, str | None]] = {}
        for row in repository.assessments(review_id, paper_ids):
            by_paper.setdefault(row.paper_id, {})[row.question_id] = row.answer
        cards = PaperService(session).cards(paper_ids)
        rows: list[PaperQualityRow] = []
        for paper_id in paper_ids:
            card = cards.get(paper_id)
            if card is None:
                continue
            answers = by_paper.get(paper_id, {})
            score, max_score = _score(questions, answers)
            rows.append(
                PaperQualityRow(
                    paper_id=paper_id,
                    title=card.paper.title,
                    year=card.paper.year,
                    first_author=card.first_author.display_name if card.first_author else None,
                    answered=sum(1 for q in questions if answers.get(q.id) is not None),
                    questions=len(questions),
                    score=score,
                    max_score=max_score,
                )
            )
        return rows


def paper_assessment(db: Database, review_id: str, paper_id: str) -> PaperAssessment:
    _require_review(db, review_id)
    _require_included(db, review_id, paper_id)
    with db.session() as session:
        return _paper_assessment(session, review_id, paper_id)


def _paper_assessment(session: Session, review_id: str, paper_id: str) -> PaperAssessment:
    rows = QualityRepository(session).assessments(review_id, [paper_id])
    return PaperAssessment(paper_id=paper_id, answers=[_answer_view(row) for row in rows])


def answer(
    db: Database, review_id: str, paper_id: str, question_id: str, body: AnswerPut
) -> PaperAssessment:
    """Set, change or clear one answer and its note."""
    _require_review(db, review_id)
    _require_included(db, review_id, paper_id)
    with db.write_session() as session:
        repository = QualityRepository(session)
        question = _require_question(repository, review_id, question_id)
        values = {option["value"] for option in question.scale_json}
        if body.answer is not None and body.answer not in values:
            raise TezError(
                ErrorCode.QUALITY_ANSWER_INVALID,
                {"answer": body.answer, "question_id": question_id},
            )
        repository.save_assessment(review_id, paper_id, question_id, body.answer, body.note)
        return _paper_assessment(session, review_id, paper_id)


def summary(db: Database, review_id: str) -> QualitySummary:
    """The stage's numbers for the review panel, all derived."""
    rows = papers(db, review_id)
    with db.session() as session:
        enabled = QualityRepository(session).enabled(review_id)
    questions = rows[0].questions if rows else len(get_quality(db, review_id).questions)
    assessed = sum(1 for r in rows if questions and r.answered == questions)
    in_progress = sum(1 for r in rows if 0 < r.answered < questions)
    return QualitySummary(
        enabled=enabled,
        questions=questions,
        papers=len(rows),
        assessed=assessed,
        in_progress=in_progress,
    )
