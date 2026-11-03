from typing import Literal

from pydantic import BaseModel


class Health(BaseModel):
    status: Literal["ok"]
    version: str

    uptime_seconds: float = 0.0
