from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from tez.modules.anchors.schemas import AnchorPaper, AnchorStatus, Rect
from tez.modules.assets.models import AssetKind

Label = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Caption = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
# A PNG of a few megabytes at most, as base64.
MAX_IMAGE_BASE64 = 14_000_000


class AssetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: AssetKind
    label: Label = ""
    caption: Caption = ""
    # Counts from 1, like the reader's address.
    page: int = Field(ge=1)
    rect: Rect
    # The area as the reader drew it, as a PNG.
    image_base64: str = Field(min_length=1, max_length=MAX_IMAGE_BASE64)


class AssetPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: AssetKind | None = None
    label: Label | None = None
    caption: Caption | None = None


class AssetView(BaseModel):
    id: str
    kind: AssetKind
    label: str
    caption: str
    page: int
    attachment_id: str
    anchor_id: str
    # ADR 0033: lost when the PDF was replaced and the area is gone from it.
    anchor_status: AnchorStatus
    paper: AnchorPaper
    created_at: datetime
