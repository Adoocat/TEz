"""API keys in the operating system's keyring (CLAUDE.md rule 7).

Never in the database, logs or responses: the API only says whether a key is set. The
store is a Protocol so tests use an in-memory one and never touch the real keyring.
"""

from enum import StrEnum
from typing import Protocol

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

SERVICE = "TEz"


class SecretName(StrEnum):
    SEMANTIC_SCHOLAR_API_KEY = "semantic_scholar_api_key"
    OPENALEX_API_KEY = "openalex_api_key"


class SecretStoreUnavailable(Exception):
    """No usable keyring (e.g. a headless Linux session without a secret service)."""


class SecretStore(Protocol):
    def get(self, name: str) -> str | None: ...
    def set(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...


class KeyringSecretStore:
    """Windows Credential Manager, macOS Keychain or the Linux Secret Service."""

    def get(self, name: str) -> str | None:
        try:
            return keyring.get_password(SERVICE, name)
        except KeyringError as error:
            raise SecretStoreUnavailable(type(error).__name__) from error

    def set(self, name: str, value: str) -> None:
        try:
            keyring.set_password(SERVICE, name, value)
        except KeyringError as error:
            raise SecretStoreUnavailable(type(error).__name__) from error

    def delete(self, name: str) -> None:
        try:
            keyring.delete_password(SERVICE, name)
        except PasswordDeleteError:
            return  # not set: deleting is idempotent
        except KeyringError as error:
            raise SecretStoreUnavailable(type(error).__name__) from error


class MemorySecretStore:
    """For tests and development without a keyring."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self._values.get(name)

    def set(self, name: str, value: str) -> None:
        self._values[name] = value

    def delete(self, name: str) -> None:
        self._values.pop(name, None)
