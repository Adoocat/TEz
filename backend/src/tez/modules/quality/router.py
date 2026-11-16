from typing import Annotated

from fastapi import APIRouter, Depends, Response

from tez.modules.library.router import get_library
from tez.modules.library.service import Library
from tez.modules.quality import service
from tez.modules.quality.schemas import (
    AnswerPut,
    PaperAssessment,
    PaperQualityRow,
    QualityCatalog,
    QualitySettingPut,
    QualitySummary,
    QualityView,
    QuestionOrder,
    QuestionPatch,
    QuestionsCreate,
    QuestionView,
    TemplateApply,
)

router = APIRouter(tags=["quality"])

LibraryDep = Annotated[Library, Depends(get_library)]
_BASE = "/reviews/{review_id}/quality"


@router.get("/quality/catalog")
def get_catalog() -> QualityCatalog:
    """Bundled checklist templates (with their licenses) and scale presets."""
    return service.catalog()


@router.get(_BASE)
def get_quality(review_id: str, library: LibraryDep) -> QualityView:
    return service.get_quality(library.db, review_id)


@router.put(f"{_BASE}/setting")
def set_quality_setting(
    review_id: str, body: QualitySettingPut, library: LibraryDep
) -> QualityView:
    """Turn the optional stage on or off; off keeps every question and answer."""
    return service.set_enabled(library.db, review_id, body.enabled)


@router.post(f"{_BASE}/questions", status_code=201)
def add_questions(review_id: str, body: QuestionsCreate, library: LibraryDep) -> list[QuestionView]:
    return service.add_questions(library.db, review_id, body.questions)


@router.post(f"{_BASE}/templates/{{template_key}}", status_code=201)
def apply_template(
    review_id: str, template_key: str, body: TemplateApply, library: LibraryDep
) -> list[QuestionView]:
    """Copy a bundled checklist's questions after the review's own."""
    return service.apply_template(library.db, review_id, template_key, body.language)


@router.patch(f"{_BASE}/questions/{{question_id}}")
def update_question(
    review_id: str, question_id: str, body: QuestionPatch, library: LibraryDep
) -> QuestionView:
    return service.update_question(library.db, review_id, question_id, body)


@router.delete(f"{_BASE}/questions/{{question_id}}", status_code=204)
def delete_question(review_id: str, question_id: str, library: LibraryDep) -> Response:
    service.delete_question(library.db, review_id, question_id)
    return Response(status_code=204)


@router.put(f"{_BASE}/order")
def reorder_questions(
    review_id: str, body: QuestionOrder, library: LibraryDep
) -> list[QuestionView]:
    return service.reorder_questions(library.db, review_id, body.question_ids)


@router.get(f"{_BASE}/papers")
def list_papers(review_id: str, library: LibraryDep) -> list[PaperQualityRow]:
    """Papers included at full text, with derived progress and totals."""
    return service.papers(library.db, review_id)


@router.get(f"{_BASE}/papers/{{paper_id}}")
def get_paper_assessment(review_id: str, paper_id: str, library: LibraryDep) -> PaperAssessment:
    return service.paper_assessment(library.db, review_id, paper_id)


@router.put(f"{_BASE}/papers/{{paper_id}}/answers/{{question_id}}")
def put_answer(
    review_id: str, paper_id: str, question_id: str, body: AnswerPut, library: LibraryDep
) -> PaperAssessment:
    """Set, change or clear one answer; clearing the answer and the note removes it."""
    return service.answer(library.db, review_id, paper_id, question_id, body)


@router.get(f"{_BASE}/summary")
def get_summary(review_id: str, library: LibraryDep) -> QualitySummary:
    return service.summary(library.db, review_id)
