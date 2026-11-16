from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from tez.modules.quality.templates import Language

QuestionText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


class ScaleOption(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Stable key answers refer to; labels and scores may change, values may not.
    value: str = Field(pattern=r"^[a-z0-9_]{1,32}$")
    label: str = Field(min_length=1, max_length=80)
    # Counted in the derived total; null for options such as "Not applicable".
    score: float | None = Field(default=None, ge=-1000, le=1000)


class Scale(BaseModel):
    """Wrapper so the option list is validated as a whole (unique values)."""

    options: list[ScaleOption] = Field(min_length=2, max_length=12)

    @model_validator(mode="after")
    def _unique_values(self) -> Self:
        values = [option.value for option in self.options]
        if len(set(values)) != len(values):
            raise ValueError("scale option values must be unique")
        return self


class QuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: QuestionText
    guidance: LongText | None = None
    scale: Scale


class QuestionsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[QuestionCreate] = Field(min_length=1, max_length=200)


class QuestionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: QuestionText | None = None
    guidance: LongText | None = None
    scale: Scale | None = None


class QuestionView(BaseModel):
    id: str
    text: str
    guidance: str | None
    scale: list[ScaleOption]
    sort_order: int
    template: str | None


class QualitySettingPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class QualityView(BaseModel):
    enabled: bool
    questions: list[QuestionView]


class QuestionOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_ids: list[str] = Field(min_length=1, max_length=200)


class TemplateApply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Language of the scale labels copied into the review.
    language: Language


class PresetOptionView(BaseModel):
    value: str
    labels: dict[Language, str]
    score: float | None


class ScalePresetView(BaseModel):
    key: str
    options: list[PresetOptionView]


class TemplateView(BaseModel):
    key: str
    title: str
    publisher: str
    design: str
    version: str
    license: str
    source_url: str
    questions: list[str]
    scale: str
    rating_question: str | None
    rating_scale: str | None


class QualityCatalog(BaseModel):
    templates: list[TemplateView]
    scales: list[ScalePresetView]


class AnswerPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # A scale option's value, or null to clear it.
    answer: str | None = None
    note: LongText | None = None


class AnswerView(BaseModel):
    question_id: str
    answer: str | None
    note: str | None
    updated_at: datetime


class PaperAssessment(BaseModel):
    paper_id: str
    answers: list[AnswerView]


class PaperQualityRow(BaseModel):
    """An included paper with its derived progress and total; nothing here is stored."""

    paper_id: str
    title: str
    year: int | None
    first_author: str | None
    answered: int
    questions: int
    # Sum of the chosen options' scores, out of the best reachable for the answers given
    # (options without a score, such as "Not applicable", leave the question out).
    score: float | None
    max_score: float | None


class QualitySummary(BaseModel):
    """What the review panel shows for the stage; hidden there when `enabled` is false."""

    enabled: bool
    questions: int
    papers: int
    assessed: int
    in_progress: int
