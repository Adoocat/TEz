from typing import Literal

from pydantic import BaseModel


class ExportResult(BaseModel):
    format: Literal["bibtex", "ris"]
    # Papers written.
    count: int
    content: str
