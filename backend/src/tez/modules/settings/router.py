from collections.abc import Generator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from tez.core.errors import ErrorCode, TezError
from tez.modules.library.router import get_library
from tez.modules.library.service import Library
from tez.modules.settings import service
from tez.modules.settings.schemas import AppSettings, SecretStatus, SecretValue, SettingsPatch
from tez.modules.settings.secrets import SecretName, SecretStore, SecretStoreUnavailable

settings_router = APIRouter(prefix="/settings", tags=["settings"])
secrets_router = APIRouter(prefix="/secrets", tags=["settings"])

LibraryDep = Annotated[Library, Depends(get_library)]


def get_secret_store(request: Request) -> SecretStore:
    store: SecretStore = request.app.state.secret_store
    return store


StoreDep = Annotated[SecretStore, Depends(get_secret_store)]


@settings_router.get("")
def read_settings(library: LibraryDep) -> AppSettings:
    return service.read_settings(library.db)


@settings_router.patch("")
def update_settings(patch: SettingsPatch, library: LibraryDep) -> AppSettings:
    return service.update_settings(library.db, patch)


@secrets_router.get("")
def list_secrets(store: StoreDep) -> list[SecretStatus]:
    """Which API keys are set. Values are never returned."""
    with _keyring_errors():
        return service.secret_statuses(store)


@secrets_router.put("/{name}", status_code=204)
def set_secret(name: SecretName, body: SecretValue, store: StoreDep) -> Response:
    with _keyring_errors():
        store.set(name, body.value)
    return Response(status_code=204)


@secrets_router.delete("/{name}", status_code=204)
def delete_secret(name: SecretName, store: StoreDep) -> Response:
    with _keyring_errors():
        store.delete(name)
    return Response(status_code=204)


@contextmanager
def _keyring_errors() -> Generator[None]:
    try:
        yield
    except SecretStoreUnavailable as error:
        raise TezError(ErrorCode.SECRETS_UNAVAILABLE, status=503) from error
