from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tez.modules.settings.models import Setting


class SettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str) -> Any:
        """The stored JSON value, or None if the key is not set."""
        setting = self.session.get(Setting, key)
        return None if setting is None else setting.value_json

    def set(self, key: str, value: Any) -> None:
        setting = self.session.get(Setting, key)
        if setting is None:
            self.session.add(Setting(key=key, value_json=value))
        else:
            setting.value_json = value
        self.session.flush()

    def delete(self, key: str) -> None:
        self.session.execute(delete(Setting).where(Setting.key == key))

    def all(self) -> dict[str, Any]:
        return {s.key: s.value_json for s in self.session.scalars(select(Setting))}
