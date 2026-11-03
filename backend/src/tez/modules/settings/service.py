"""Library settings as typed values over the key/JSON `setting` table, and API key status."""

from tez.core.db import Database
from tez.modules.settings.repository import SettingsRepository
from tez.modules.settings.schemas import AppSettings, SecretStatus, SettingsPatch
from tez.modules.settings.secrets import SecretName, SecretStore

# Field of AppSettings -> key in the `setting` table.
_KEYS = {"language": "ui.language", "theme": "ui.theme", "sources_email": "sources.email"}


def read_settings(db: Database) -> AppSettings:
    with db.session() as s:
        stored = SettingsRepository(s).all()
    values = {field: stored[key] for field, key in _KEYS.items() if stored.get(key) is not None}
    return AppSettings.model_validate(values)


def update_settings(db: Database, patch: SettingsPatch) -> AppSettings:
    with db.write_session() as s:
        repo = SettingsRepository(s)
        for field in patch.model_fields_set:
            value = getattr(patch, field)
            if value is None:
                repo.delete(_KEYS[field])
            else:
                repo.set(_KEYS[field], value)
    return read_settings(db)


def secret_statuses(store: SecretStore) -> list[SecretStatus]:
    return [SecretStatus(name=name, configured=store.get(name) is not None) for name in SecretName]
