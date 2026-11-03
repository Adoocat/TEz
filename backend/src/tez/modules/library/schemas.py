from typing import Literal

from pydantic import BaseModel

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
