"""How a `tez` command reaches the library: through the open app, or by opening it itself.

The plan's rule: if the library is open in a window, the command talks to that process's API
(found in `.tez/instance.json`), so its work shows in the window and two writers never meet;
otherwise the command takes the library lock and calls the same services directly. Both ways
return the API's own response models, so the commands cannot tell them apart.
"""

import asyncio
import json
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Literal, Protocol, TypeVar

import httpx2
from pydantic import BaseModel, TypeAdapter

from tez.core.errors import ErrorCode, TezError
from tez.modules.export import service as export_service
from tez.modules.export.schemas import ExportResult
from tez.modules.files import service as files_service
from tez.modules.files.schemas import PdfPathResult
from tez.modules.importers import service as import_service
from tez.modules.importers.schemas import ImportOutcome, ImportRequest
from tez.modules.library import organize
from tez.modules.library.schemas import ChangeCount, CollectionView
from tez.modules.library.service import Library, find_instance, open_library
from tez.modules.reviews import service as reviews_service
from tez.modules.reviews.schemas import ReviewView
from tez.modules.search import queries
from tez.modules.search.models import InitiatedVia
from tez.modules.search.providers.base import SearchRequest
from tez.modules.search.providers.registry import ProviderFactory, open_providers, read_access
from tez.modules.search.schemas import SearchOverview, SourceProgress
from tez.modules.search.service import SourceUpdate, run_search
from tez.modules.settings import service as settings_service
from tez.modules.settings.secrets import KeyringSecretStore, SecretStore

ProgressListener = Callable[[SourceProgress], None]
Model = TypeVar("Model", bound=BaseModel)

# Replaced in tests: no command may reach the network or the OS keyring there.
PROVIDERS: ProviderFactory = open_providers
SECRETS: Callable[[], SecretStore] = KeyringSecretStore


class CliFailure(Exception):
    """A failure to report with a code, from either mode."""

    def __init__(self, code: str, params: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.params: dict[str, Any] = dict(params or {})

    @classmethod
    def of(cls, error: TezError) -> "CliFailure":
        return cls(error.code.value, error.params)


class Access(Protocol):
    mode: Literal["api", "direct"]

    def reviews(self) -> list[ReviewView]: ...

    def search(
        self, review_id: str, request: SearchRequest, sources: list[str], on: ProgressListener
    ) -> SearchOverview: ...

    def import_file(self, request: ImportRequest) -> ImportOutcome: ...

    def add_pdfs(self, paths: list[str]) -> list[PdfPathResult]: ...

    def collections(self) -> list[CollectionView]: ...

    def create_collection(self, name: str) -> CollectionView: ...

    def file_in(self, collection_id: str, paper_ids: list[str]) -> ChangeCount: ...

    def export(
        self, fmt: str, review_id: str | None, collection_id: str | None
    ) -> ExportResult: ...

    def close(self) -> None: ...


def _progress(update: SourceUpdate) -> SourceProgress:
    return SourceProgress(
        source=update.source,
        state=update.state,
        retrieved=update.retrieved,
        total_reported=update.total_reported,
        wait_seconds=update.wait_seconds,
        error_code=update.error_code,
    )


class DirectAccess:
    """The library opened by this process, under its lock. Jobs (PDF inspection) wait in the
    queue for the app's worker; nothing runs them here."""

    mode: Literal["api", "direct"] = "direct"

    def __init__(self, library: Library) -> None:
        self.library = library

    def reviews(self) -> list[ReviewView]:
        return reviews_service.list_reviews(self.library.db)

    def search(
        self, review_id: str, request: SearchRequest, sources: list[str], on: ProgressListener
    ) -> SearchOverview:
        db = self.library.db
        email = settings_service.read_settings(db).sources_email
        access = read_access(SECRETS(), email)

        async def go() -> str:
            async with PROVIDERS(sources, access) as providers:
                return await run_search(
                    db,
                    self.library.path,
                    review_id,
                    request,
                    providers,
                    initiated_via=InitiatedVia.CLI,
                    listener=lambda update: on(_progress(update)),
                )

        search_id = asyncio.run(go())
        overview = queries.overview(db, search_id)
        if overview is None:  # every source was asked, so there is at least one run
            raise CliFailure(ErrorCode.SEARCH_NOT_FOUND.value, {"search_id": search_id})
        return overview

    def import_file(self, request: ImportRequest) -> ImportOutcome:
        return import_service.run_import(
            self.library.db, self.library.path, request, initiated_via=InitiatedVia.CLI
        )

    def add_pdfs(self, paths: list[str]) -> list[PdfPathResult]:
        return files_service.add_pdfs_from_paths(self.library.db, self.library.path, paths)

    def collections(self) -> list[CollectionView]:
        return organize.list_collections(self.library.db)

    def create_collection(self, name: str) -> CollectionView:
        return organize.create_collection(self.library.db, name, None)

    def file_in(self, collection_id: str, paper_ids: list[str]) -> ChangeCount:
        return organize.add_to_collection(self.library.db, collection_id, paper_ids)

    def export(self, fmt: str, review_id: str | None, collection_id: str | None) -> ExportResult:
        return export_service.export(
            self.library.db,
            export_service.ExportFormat(fmt),
            review_id=review_id,
            collection_id=collection_id,
        )

    def close(self) -> None:
        self.library.close()


class ApiAccess:
    """The open app's API, with the token from `.tez/instance.json`."""

    mode: Literal["api", "direct"] = "api"

    def __init__(self, url: str, token: str, *, transport: httpx2.BaseTransport | None = None):
        self.url = url
        self._client = httpx2.Client(
            base_url=url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx2.Timeout(30.0, read=600.0),
            transport=transport,
        )

    @contextmanager
    def _reaching(self) -> Generator[None]:
        try:
            yield
        except httpx2.TransportError as exc:
            raise CliFailure(ErrorCode.CLI_API_UNREACHABLE.value, {"url": self.url}) from exc

    def _check(self, response: httpx2.Response) -> httpx2.Response:
        if response.is_success:
            return response
        try:
            error = response.json()["error"]
            raise CliFailure(str(error["code"]), dict(error.get("params") or {}))
        except (ValueError, KeyError, TypeError) as exc:
            raise CliFailure("http.error", {"status": response.status_code}) from exc

    def _call(self, method: str, path: str, model: type[Model] | Any, **kwargs: Any) -> Any:
        with self._reaching():
            response = self._check(self._client.request(method, path, **kwargs))
        return TypeAdapter(model).validate_python(response.json())

    def reviews(self) -> list[ReviewView]:
        return self._call("GET", "/reviews", list[ReviewView])

    def search(
        self, review_id: str, request: SearchRequest, sources: list[str], on: ProgressListener
    ) -> SearchOverview:
        body = {
            "review_id": review_id,
            "query": request.query,
            "sources": sources,
            "year_from": request.year_from,
            "year_to": request.year_to,
            "limit": request.limit,
            "initiated_via": InitiatedVia.CLI.value,
        }
        started = self._call("POST", "/searches", dict[str, Any], json=body)
        search_id = str(started["search_id"])
        with (
            self._reaching(),
            self._client.stream("GET", f"/searches/{search_id}/events") as events,
        ):
            self._check(events)
            name = ""
            for line in events.iter_lines():
                if line.startswith("event: "):
                    name = line.removeprefix("event: ")
                elif line.startswith("data: ") and name == "source":
                    on(SourceProgress.model_validate_json(line.removeprefix("data: ")))
                elif line.startswith("data: ") and name == "finished":
                    break
        return self._call("GET", f"/searches/{search_id}", SearchOverview)

    def import_file(self, request: ImportRequest) -> ImportOutcome:
        body = request.model_copy(update={"initiated_via": InitiatedVia.CLI})
        return self._call("POST", "/imports", ImportOutcome, json=body.model_dump(mode="json"))

    def add_pdfs(self, paths: list[str]) -> list[PdfPathResult]:
        return self._call("POST", "/pdfs/from-paths", list[PdfPathResult], json={"paths": paths})

    def collections(self) -> list[CollectionView]:
        return self._call("GET", "/collections", list[CollectionView])

    def create_collection(self, name: str) -> CollectionView:
        return self._call("POST", "/collections", CollectionView, json={"name": name})

    def file_in(self, collection_id: str, paper_ids: list[str]) -> ChangeCount:
        return self._call(
            "POST",
            f"/collections/{collection_id}/papers",
            ChangeCount,
            json={"paper_ids": paper_ids},
        )

    def export(self, fmt: str, review_id: str | None, collection_id: str | None) -> ExportResult:
        params = {"format": fmt}
        if review_id:
            params["review_id"] = review_id
        if collection_id:
            params["collection_id"] = collection_id
        return self._call("GET", "/export", ExportResult, params=params)

    def close(self) -> None:
        self._client.close()


def connect(library: Path) -> Access:
    """The open app's API if it has the library, else the library itself (under its lock)."""
    path = library.absolute()
    try:
        instance = find_instance(path)
        if instance is None:
            return DirectAccess(open_library(path, kind="cli"))
    except TezError as error:
        raise CliFailure.of(error) from error
    if instance.api is None:
        # Another headless command holds it: it has no API to share.
        raise CliFailure(ErrorCode.CLI_LIBRARY_BUSY.value, {"pid": instance.pid})
    return ApiAccess(instance.api.url, instance.api.token)


def to_json(value: Any) -> str:
    """The `--json` document: pydantic models as their API JSON."""

    def plain(item: Any) -> Any:
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, list):
            return [plain(i) for i in item]  # pyright: ignore[reportUnknownVariableType]
        if isinstance(item, dict):
            return {k: plain(v) for k, v in item.items()}  # pyright: ignore[reportUnknownVariableType]
        if isinstance(item, date):
            return item.isoformat()
        return item

    return json.dumps(plain(value), ensure_ascii=False, indent=2)
