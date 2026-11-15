"""Which sources exist, and how to build them from the user's settings and keys."""

import logging
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass

from tez.modules.search.providers import openalex, semantic_scholar
from tez.modules.search.providers.arxiv import ArxivProvider
from tez.modules.search.providers.base import SearchProvider
from tez.modules.search.providers.crossref import CrossrefProvider
from tez.modules.search.providers.openalex import OpenAlexProvider
from tez.modules.search.providers.semantic_scholar import SemanticScholarProvider
from tez.modules.settings.secrets import SecretName, SecretStore, SecretStoreUnavailable
from tez.shared.http import HttpClient

logger = logging.getLogger(__name__)

# Sources that can be asked for theses only (Task 28).
THESIS_FILTER_SOURCES = (OpenAlexProvider.name, CrossrefProvider.name)

SOURCE_NAMES = (
    OpenAlexProvider.name,
    SemanticScholarProvider.name,
    ArxivProvider.name,
    CrossrefProvider.name,
)


@dataclass(frozen=True)
class SourceAccess:
    """What the user has set up: an e-mail for polite pools, and API keys."""

    email: str | None = None
    openalex_key: str | None = None
    semantic_scholar_key: str | None = None


ProviderFactory = Callable[
    [Sequence[str], SourceAccess], AbstractAsyncContextManager[Sequence[SearchProvider]]
]


def read_access(store: SecretStore, email: str | None) -> SourceAccess:
    """Keys are optional, so a missing keyring only means searching without them."""
    try:
        return SourceAccess(
            email=email,
            openalex_key=store.get(SecretName.OPENALEX_API_KEY),
            semantic_scholar_key=store.get(SecretName.SEMANTIC_SCHOLAR_API_KEY),
        )
    except SecretStoreUnavailable as exc:
        logger.warning("searching without API keys", extra={"error": repr(exc)})
        return SourceAccess(email=email)


def _secret_headers(access: SourceAccess) -> dict[str, dict[str, str]]:
    headers: dict[str, dict[str, str]] = {}
    if access.openalex_key:
        headers[openalex.API_HOST] = {"Authorization": f"Bearer {access.openalex_key}"}
    if access.semantic_scholar_key:
        headers[semantic_scholar.API_HOST] = {"x-api-key": access.semantic_scholar_key}
    return headers


def _build(name: str, http: HttpClient, access: SourceAccess) -> SearchProvider:
    if name == OpenAlexProvider.name:
        return OpenAlexProvider(http, has_key=bool(access.openalex_key))
    if name == SemanticScholarProvider.name:
        return SemanticScholarProvider(http)
    if name == ArxivProvider.name:
        return ArxivProvider(http)
    if name == CrossrefProvider.name:
        return CrossrefProvider(http, email=access.email)
    raise ValueError(f"unknown source: {name}")


@asynccontextmanager
async def open_providers(
    names: Sequence[str], access: SourceAccess
) -> AsyncGenerator[Sequence[SearchProvider]]:
    """The named sources on one HTTP client. Searches do not use the response cache."""
    async with HttpClient(secret_headers=_secret_headers(access)) as http:
        yield [_build(name, http, access) for name in names]
