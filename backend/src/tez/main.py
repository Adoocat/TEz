"""Application factory."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tez import __version__
from tez.core.auth import TokenAuthMiddleware, bearer_scheme
from tez.core.config import Settings
from tez.core.errors import ERROR_RESPONSES, ErrorResponse, install_error_handlers
from tez.core.logging import configure_logging
from tez.core.requests import RequestContextMiddleware
from tez.modules.jobs.router import router as jobs_router
from tez.modules.jobs.supervisor import WorkerSupervisor
from tez.modules.library.router import router as library_router
from tez.modules.library.service import Library, open_library
from tez.modules.system.router import router as system_router

# `serve --reload` hands these to the reloaded child process, which builds the app.
# Development only: the sidecar receives its token over stdin (ADR 0001).
DEV_TOKEN_ENV = "TEZ_DEV_TOKEN"
DEV_LIBRARY_ENV = "TEZ_DEV_LIBRARY"
DEV_URL_ENV = "TEZ_DEV_URL"

_DOCS_PATHS = ("/docs", "/docs/oauth2-redirect", "/openapi.json")


def create_app(
    *,
    token: str,
    settings: Settings,
    open_docs: bool = False,
    library: Library | None = None,
    start_worker: bool = False,
) -> FastAPI:
    """Build the API. Every route needs `token`; `open_docs` exempts the API docs (dev).

    The app takes ownership of `library` and closes it on shutdown. With `start_worker`,
    it also runs (and restarts) the job worker process for that library.
    """
    if not token:
        raise ValueError("API token must not be empty")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        if library is not None and start_worker:
            app.state.worker = WorkerSupervisor(library.path)
            app.state.worker.start()
        try:
            yield
        finally:
            if app.state.worker is not None:
                app.state.worker.stop()
            if library is not None:
                library.close()

    app = FastAPI(title="TEz", version=__version__, redoc_url=None, lifespan=lifespan)
    app.state.library = library
    app.state.worker = None
    install_error_handlers(app)
    secured = [Depends(bearer_scheme)]
    app.include_router(system_router, dependencies=secured, responses=ERROR_RESPONSES)
    needs_library = {
        **ERROR_RESPONSES,
        409: {"model": ErrorResponse, "description": "No library is open"},
    }
    app.include_router(library_router, dependencies=secured, responses=needs_library)
    app.include_router(jobs_router, dependencies=secured, responses=needs_library)

    # Starlette wraps in reverse order: the last middleware added is the outermost.
    app.add_middleware(
        TokenAuthMiddleware, token=token, public_paths=_DOCS_PATHS if open_docs else ()
    )
    app.add_middleware(RequestContextMiddleware)
    # Outermost, so 401 and 500 responses carry CORS headers too (ADR 0001).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type", "Range"],
        expose_headers=["X-Request-ID", "Accept-Ranges", "Content-Range", "Content-Length"],
    )
    return app


def create_dev_app() -> FastAPI:
    """Factory for `serve --reload`, which re-imports the app in a child process."""
    settings = Settings()
    configure_logging(settings)
    token = os.environ.get(DEV_TOKEN_ENV, "")
    if not token:
        raise ValueError("API token must not be empty")
    library = None
    if library_path := os.environ.get(DEV_LIBRARY_ENV):
        library = open_library(Path(library_path), create=True)
        if url := os.environ.get(DEV_URL_ENV):
            library.publish_api(url=url, token=token)
    return create_app(
        token=token, settings=settings, open_docs=True, library=library, start_worker=True
    )
