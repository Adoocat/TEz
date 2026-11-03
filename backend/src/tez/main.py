"""Application factory."""

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tez import __version__
from tez.core.auth import TokenAuthMiddleware, bearer_scheme
from tez.core.config import Settings
from tez.core.errors import ERROR_RESPONSES, install_error_handlers
from tez.core.logging import configure_logging
from tez.core.requests import RequestContextMiddleware
from tez.modules.system.router import router as system_router

# `serve --reload` hands the token to the reloaded child process through this variable.
# Development only: the sidecar receives its token over stdin (ADR 0001).
DEV_TOKEN_ENV = "TEZ_DEV_TOKEN"

_DOCS_PATHS = ("/docs", "/docs/oauth2-redirect", "/openapi.json")


def create_app(*, token: str, settings: Settings, open_docs: bool = False) -> FastAPI:
    """Build the API. Every route needs `token`; `open_docs` exempts the API docs (dev)."""
    if not token:
        raise ValueError("API token must not be empty")

    app = FastAPI(title="TEz", version=__version__, redoc_url=None)
    install_error_handlers(app)
    app.include_router(
        system_router, dependencies=[Depends(bearer_scheme)], responses=ERROR_RESPONSES
    )

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
    return create_app(token=os.environ.get(DEV_TOKEN_ENV, ""), settings=settings, open_docs=True)
