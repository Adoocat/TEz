from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from tez.modules.reviews.models import ReviewMethod, ReviewStatus


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=300)
    method: ReviewMethod


class ReviewView(BaseModel):
    id: str
    title: str
    method: ReviewMethod
    status: ReviewStatus
    created_at: datetime
