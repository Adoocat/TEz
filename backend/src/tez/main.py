"""Application factory."""

from fastapi import FastAPI

from tez import __version__


def create_app() -> FastAPI:
    """Build the API application. Routers, auth and error handling arrive in Task 3."""
    return FastAPI(title="TEz", version=__version__)


def broken() -> int:
    return "not an int"
