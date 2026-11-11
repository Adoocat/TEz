"""Outbound HTTP for academic sources: one client, a limiter per source, retries and a cache.

Failures come out as `TezError`s with `source.*` codes, so a caller can record them per source
and carry on with the others. Three decisions are worth knowing:

- API keys are added below the cache. The cache stores requests as well as responses, and it
  must never hold a key (CLAUDE.md rule 7). For the same reason keys are matched by host, so a
  redirect to another host cannot carry them along.
- The cache is opt-in per call. A search run records what a source says now, so searches pass
  no `cache_ttl`; metadata lookups can.
- A broken cache file is logged and then ignored. It never stops a request (rule 5).
"""

import asyncio
import logging
import sqlite3
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import httpx2
from hishel import AsyncSqliteStorage, BaseFilter, FilterPolicy, Response
from hishel.httpx2 import AsyncCacheTransport
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from tez.core.errors import ErrorCode, TezError

logger = logging.getLogger(__name__)

_OK = 200
_TOO_MANY_REQUESTS = 429
_RETRIED_STATUSES = frozenset({500, 502, 503, 504})
_BAD_GATEWAY = 502
_TTL_EXTENSION = "hishel_ttl"

Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class SourcePolicy:
    """How to behave towards one source. Each provider declares its own."""

    name: str
    requests_per_second: float
    timeout_seconds: float = 30.0
    max_attempts: int = 4
    backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0
    jitter_seconds: float = 0.5
    # A source asking for a longer pause than this has run out of quota for now: report it.
    max_retry_after_seconds: float = 120.0


class RateLimiter:
    """Spaces requests evenly. Idle time builds no burst: sources count requests per second."""

    def __init__(self, per_second: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._interval = 1 / per_second
        self._clock = clock
        self._next_free = 0.0

    def reserve(self) -> float:
        """Take the next slot; returns how long the caller must wait for it."""
        now = self._clock()
        start = max(now, self._next_free)
        self._next_free = start + self._interval
        return start - now

    def penalize(self, seconds: float) -> None:
        """Hold back every request to this source, including those already queued for a slot."""
        self._next_free = max(self._next_free, self._clock() + seconds)

    def delay(self) -> float:
        return max(0.0, self._next_free - self._clock())


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    """`Retry-After` as seconds from now: either a number or an HTTP date. None if unusable."""
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        pass  # Not a number, so it may be a date.
    else:
        return seconds if seconds >= 0 else None
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return max(0.0, (moment - (now or datetime.now(UTC))).total_seconds())


class _Retry(Exception):
    """An attempt failed in a way worth trying again; `error` is what callers get if none works."""

    def __init__(self, error: TezError, retry_after: float | None = None) -> None:
        super().__init__(error.code.value)
        self.error = error
        self.retry_after = retry_after


class _SecretHeaders(httpx2.AsyncBaseTransport):
    """Adds API keys on the way out, below the cache and the client's logging."""

    def __init__(
        self, next_transport: httpx2.AsyncBaseTransport, by_host: Mapping[str, Mapping[str, str]]
    ) -> None:
        self._next = next_transport
        self._by_host = by_host

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        request.headers.update(self._by_host.get(request.url.host, {}))
        return await self._next.handle_async_request(request)

    async def aclose(self) -> None:
        await self._next.aclose()


class _OnlySuccess(BaseFilter[Response]):
    def needs_body(self) -> bool:
        return False

    def apply(self, item: Response, body: bytes | None) -> bool:
        return item.status_code == _OK


class _OptionalCache(httpx2.AsyncBaseTransport):
    """Sends calls with a TTL through the cache, and all calls directly once the cache breaks."""

    def __init__(self, network: httpx2.AsyncBaseTransport, cache_path: Path | None) -> None:
        self._network = network
        self._cache: AsyncCacheTransport | None = None
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache = AsyncCacheTransport(
                next_transport=network,
                storage=AsyncSqliteStorage(database_path=cache_path),
                policy=FilterPolicy(response_filters=[_OnlySuccess()]),
            )

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        if self._cache is None or _TTL_EXTENSION not in request.extensions:
            return await self._network.handle_async_request(request)
        try:
            return await self._cache.handle_async_request(request)
        except sqlite3.Error as exc:
            logger.warning("http cache disabled", extra={"error": repr(exc)})
            await self._close_cache()
            return await self._network.handle_async_request(request)

    async def _close_cache(self) -> None:
        cache, self._cache = self._cache, None
        if cache is None:
            return
        try:
            await cache.storage.close()
        except sqlite3.Error as exc:
            logger.warning("http cache did not close cleanly", extra={"error": repr(exc)})

    async def aclose(self) -> None:
        await self._close_cache()
        await self._network.aclose()


def _user_agent() -> str:
    try:
        return f"TEz/{version('tez')}"
    except PackageNotFoundError:  # A frozen build may carry no package metadata.
        return "TEz"


@dataclass(frozen=True)
class Download:
    content: bytes
    content_type: str
    # After redirects: where the file really came from.
    final_url: str


class HttpClient:
    """The one way out to academic sources. Use as an async context manager."""

    def __init__(
        self,
        *,
        cache_path: Path | None = None,
        secret_headers: Mapping[str, Mapping[str, str]] | None = None,
        sleep: Sleep = asyncio.sleep,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        """`transport` replaces the network, for tests; keys and the cache still apply."""
        network = _SecretHeaders(transport or httpx2.AsyncHTTPTransport(), secret_headers or {})
        self._client = httpx2.AsyncClient(
            transport=_OptionalCache(network, cache_path),
            headers={"User-Agent": _user_agent()},
            follow_redirects=True,
        )
        self._limiters: dict[str, RateLimiter] = {}
        self._sleep = sleep

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(
        self,
        source: SourcePolicy,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        cache_ttl: float | None = None,
        on_wait: Callable[[float], None] | None = None,
    ) -> httpx2.Response:
        """GET with rate limiting and retries. Raises `TezError` with a `source.*` code.

        `cache_ttl` opts in to the cache, in seconds. `on_wait` is told each back-off, in
        seconds, so a UI can show a countdown.
        """
        exponential = wait_exponential_jitter(
            multiplier=source.backoff_seconds,
            max=source.max_backoff_seconds,
            jitter=source.jitter_seconds,
        )

        def wait(state: RetryCallState) -> float:
            backoff = exponential(state)
            failure = state.outcome.exception() if state.outcome else None
            retry_after = failure.retry_after if isinstance(failure, _Retry) else None
            return max(backoff, retry_after or 0.0)

        def before_sleep(state: RetryCallState) -> None:
            seconds = state.upcoming_sleep
            failure = state.outcome.exception() if state.outcome else None
            logger.info(
                "source retry",
                extra={"source": source.name, "wait": seconds, "error": repr(failure)},
            )
            if on_wait is not None:
                on_wait(seconds)

        extensions = None if cache_ttl is None else {_TTL_EXTENSION: cache_ttl}
        retrying = AsyncRetrying(
            stop=stop_after_attempt(source.max_attempts),
            wait=wait,
            retry=retry_if_exception_type(_Retry),
            before_sleep=before_sleep,
            sleep=self._sleep,
            reraise=True,
        )
        try:
            return await retrying(self._attempt, source, url, params, headers, extensions)
        except _Retry as exc:
            raise exc.error from exc

    async def _attempt(
        self,
        source: SourcePolicy,
        url: str,
        params: Mapping[str, Any] | None,
        headers: Mapping[str, str] | None,
        extensions: dict[str, Any] | None,
    ) -> httpx2.Response:
        limiter = self._limiters.setdefault(source.name, RateLimiter(source.requests_per_second))
        delay = limiter.reserve()
        if delay > 0:
            await self._sleep(delay)
        try:
            response = await self._client.get(
                url,
                params=params,
                headers=headers,
                timeout=source.timeout_seconds,
                extensions=extensions,
            )
        except httpx2.TimeoutException as exc:
            raise _Retry(_error(ErrorCode.SOURCE_TIMEOUT, source)) from exc
        except httpx2.TransportError as exc:
            raise _Retry(_error(ErrorCode.SOURCE_NETWORK, source)) from exc
        if response.status_code == _TOO_MANY_REQUESTS:
            raise self._rate_limited(source, limiter, response)
        if response.status_code in _RETRIED_STATUSES:
            status = response.status_code
            raise _Retry(_error(ErrorCode.SOURCE_UNAVAILABLE, source, status=status))
        if not response.is_success:
            raise _error(ErrorCode.SOURCE_REJECTED, source, status=response.status_code)
        return response

    async def download(
        self,
        source: SourcePolicy,
        url: str,
        *,
        max_bytes: int,
        on_progress: Callable[[int, int | None], None] | None = None,
    ) -> Download:
        """Stream a file, telling `on_progress` (bytes so far, total if known) as it comes.

        One attempt, rate limited, never cached: a download is large and is retried as a whole
        job. Raises `TezError` with a `source.*` code, or `source.too_large` past `max_bytes`.
        """
        limiter = self._limiters.setdefault(source.name, RateLimiter(source.requests_per_second))
        delay = limiter.reserve()
        if delay > 0:
            await self._sleep(delay)
        try:
            async with self._client.stream("GET", url, timeout=source.timeout_seconds) as response:
                if response.status_code == _TOO_MANY_REQUESTS:
                    raise _unwrap(self._rate_limited(source, limiter, response))
                if not response.is_success:
                    code = (
                        ErrorCode.SOURCE_UNAVAILABLE
                        if response.status_code in _RETRIED_STATUSES
                        else ErrorCode.SOURCE_REJECTED
                    )
                    raise _error(code, source, status=response.status_code)
                total = _content_length(response)
                if total is not None and total > max_bytes:
                    raise _error(ErrorCode.SOURCE_TOO_LARGE, source, size=total)
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > max_bytes:
                        raise _error(ErrorCode.SOURCE_TOO_LARGE, source, size=len(body))
                    if on_progress is not None:
                        on_progress(len(body), total)
                return Download(
                    content=bytes(body),
                    content_type=response.headers.get("Content-Type", ""),
                    final_url=str(response.url),
                )
        except httpx2.TimeoutException as exc:
            raise _error(ErrorCode.SOURCE_TIMEOUT, source) from exc
        except httpx2.TransportError as exc:
            raise _error(ErrorCode.SOURCE_NETWORK, source) from exc

    def _rate_limited(
        self, source: SourcePolicy, limiter: RateLimiter, response: httpx2.Response
    ) -> Exception:
        retry_after = parse_retry_after(response.headers.get("Retry-After"))
        params = {} if retry_after is None else {"retry_after": retry_after}
        error = _error(ErrorCode.SOURCE_RATE_LIMITED, source, **params)
        limiter.penalize(source.backoff_seconds if retry_after is None else retry_after)
        if retry_after is not None and retry_after > source.max_retry_after_seconds:
            return error
        return _Retry(error, retry_after)


def _content_length(response: httpx2.Response) -> int | None:
    value = response.headers.get("Content-Length", "")
    return int(value) if value.isdigit() else None


def _unwrap(failure: Exception) -> TezError:
    if isinstance(failure, _Retry):
        return failure.error
    assert isinstance(failure, TezError)
    return failure


def _error(code: ErrorCode, source: SourcePolicy, **params: Any) -> TezError:
    return TezError(code, {"source": source.name, **params}, status=_BAD_GATEWAY)
