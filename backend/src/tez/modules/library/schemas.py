from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InstanceKind = Literal["app", "cli"]


class LibraryInfo(BaseModel):
    path: str
    name: str
    schema_revision: str


class ApiEndpoint(BaseModel):
    url: str
    token: str


class Instance(BaseModel):
    """Contents of `.tez/instance.json`: who has the library open, and how to reach it."""

    pid: int
    kind: InstanceKind
    host: str
    started_at: str
    version: str
    api: ApiEndpoint | None = None


class PaperSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_ids: list[str] = Field(min_length=1, max_length=20000)
    # Where the selection came from, kept on each new review record.
    search_id: str | None = None


class SelectionResult(BaseModel):
    added: int
    already_present: int
