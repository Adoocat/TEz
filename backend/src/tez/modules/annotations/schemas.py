from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tez.modules.anchors.schemas import AnchorCreate, AnchorView
from tez.modules.annotations.models import AnnotationKind

# Design tokens. Purple is left out: in TEz it means "suggested by AI".
HighlightColor = Literal["yellow", "green", "blue", "pink"]


class AnnotationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor: AnchorCreate
    color: HighlightColor = "yellow"
    comment: str = Field(default="", max_length=20_000)


class AnnotationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: HighlightColor | None = None
    comment: str | None = Field(default=None, max_length=20_000)


class AnnotationView(BaseModel):
    id: str
    kind: AnnotationKind
    color: HighlightColor
    comment: str
    anchor: AnchorView
    created_at: datetime
    updated_at: datetime
