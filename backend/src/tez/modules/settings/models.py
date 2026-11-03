from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from tez.core.db import Base, UtcDateTime, utcnow


class Setting(Base):
    """Keyed by name (`ui.language`), so no UUID: the key is the identity."""

    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)
