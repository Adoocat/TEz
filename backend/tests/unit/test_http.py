"""The HTTP layer against a fake server on a real socket: real timeouts, real headers."""

import asyncio
import io
import json
import logging
import sqlite3
from collections.abc import Awaitable, Callable
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tez.core.config import Settings
from tez.core.errors import ErrorCode, TezError
from tez.core.logging import configure_logging
from tez.shared.http import HttpClient, RateLimiter, SourcePolicy, parse_retry_after


@dataclass
class Reply:
    status: int = 200
    body: str = '{"ok": true}'
    headers: dict[str, str] = field(default_factory=dict[str, str])
    hang: bool = False


@dataclass
class FakeServer:
    """Plays `script` in order, then repeats its last reply; records what it was sent."""

    script: list[Reply]
    requests: list[dict[str, str]] = field(default_factory=list[dict[str, str]])
    port: int = 0

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/works"

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # `finally`: since Python 3.12 the server's wait_closed() waits for every connection.
        try:
            raw = await reader.readuntil(b"\r\n\r\n")
            lines = raw.decode().split("\r\n")
            headers = {k.lower(): v.strip() for k, v in (x.split(":", 1) for x in lines[1:] if x)}
            self.requests.append(headers)
            reply = self.script[min(len(self.requests) - 1, len(self.script) - 1)]
            if reply.hang:
                await asyncio.Event().wait()
            extra = "".join(f"{k}: {v}\r\n" for k, v in reply.headers.items())
            head = (
                f"HTTP/1.1 {reply.status} X\r\ncontent-length: {len(reply.body)}\r\n"
                f"connection: close\r\n{extra}\r\n"
            )
            writer.write(head.encode() + reply.body.encode())
            await writer.drain()
        finally:
            writer.close()


Scenario = Callable[[FakeServer], Awaitable[None]]


def serve(script: list[Reply], scenario: Scenario) -> FakeServer:
    fake = FakeServer(script)

    async def main() -> None:
        tasks: set[asyncio.Task[None]] = set()

        def on_connect(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
            tasks.add(asyncio.create_task(fake._handle(r, w)))

        server = await asyncio.start_server(on_connect, "127.0.0.1", 0)
        fake.port = server.sockets[0].getsockname()[1]
        try:
            await scenario(fake)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            server.close()
            await server.wait_closed()

    asyncio.run(main())
    return fake


class Sleeps:
    """Records back-off waits and returns at once, so retry tests do not take real seconds."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


# A rate so high the limiter never waits, so `Sleeps` sees only the back-off under test.
UNLIMITED = 1_000_000
FAST = SourcePolicy(name="fake", requests_per_second=UNLIMITED, timeout_seconds=0.2, max_attempts=3)


# --- 429 ------------------------------------------------------------------------------


def test_429_waits_for_retry_after_then_succeeds() -> None:
    sleeps = Sleeps()
    announced: list[float] = []

    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(sleep=sleeps) as http:
            response = await http.get(FAST, fake.url, on_wait=announced.append)
        assert response.json() == {"ok": True}

    fake = serve([Reply(429, headers={"Retry-After": "7"}), Reply()], scenario)
    assert len(fake.requests) == 2
    assert max(sleeps.waits) >= 7
    assert announced and announced[0] >= 7  # the UI shows this as a countdown


def test_persistent_429_reports_rate_limited_with_the_wait() -> None:
    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(sleep=Sleeps()) as http:
            with pytest.raises(TezError) as caught:
                await http.get(FAST, fake.url)
        assert caught.value.code is ErrorCode.SOURCE_RATE_LIMITED
        assert caught.value.params == {"source": "fake", "retry_after": 3.0}

    fake = serve([Reply(429, headers={"Retry-After": "3"})], scenario)
    assert len(fake.requests) == FAST.max_attempts


def test_a_retry_after_longer_than_we_are_willing_to_wait_fails_at_once() -> None:
    sleeps = Sleeps()

    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(sleep=sleeps) as http:
            with pytest.raises(TezError) as caught:
                await http.get(FAST, fake.url)
        assert caught.value.code is ErrorCode.SOURCE_RATE_LIMITED
        assert caught.value.params["retry_after"] == 86400.0

    fake = serve([Reply(429, headers={"Retry-After": "86400"})], scenario)
    assert len(fake.requests) == 1
    assert sleeps.waits == []


def test_429_holds_back_other_requests_to_the_same_source_only() -> None:
    limiter = RateLimiter(1000, clock=lambda: 100.0)
    other = RateLimiter(1000, clock=lambda: 100.0)
    limiter.penalize(30)
    assert limiter.delay() == pytest.approx(30)
    assert other.delay() == 0


# --- timeouts -------------------------------------------------------------------------


def test_timeout_is_retried_and_then_succeeds() -> None:
    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(sleep=Sleeps()) as http:
            response = await http.get(FAST, fake.url)
        assert response.status_code == 200

    fake = serve([Reply(hang=True), Reply()], scenario)
    assert len(fake.requests) == 2


def test_persistent_timeout_reports_timeout() -> None:
    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(sleep=Sleeps()) as http:
            with pytest.raises(TezError) as caught:
                await http.get(FAST, fake.url)
        assert caught.value.code is ErrorCode.SOURCE_TIMEOUT
        assert caught.value.params == {"source": "fake"}

    fake = serve([Reply(hang=True)], scenario)
    assert len(fake.requests) == FAST.max_attempts


# --- other failures -------------------------------------------------------------------


def test_back_off_grows_between_attempts() -> None:
    sleeps = Sleeps()
    policy = SourcePolicy(
        name="fake",
        requests_per_second=UNLIMITED,
        max_attempts=4,
        backoff_seconds=1,
        jitter_seconds=0,
    )

    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(sleep=sleeps) as http:
            with pytest.raises(TezError) as caught:
                await http.get(policy, fake.url)
        assert caught.value.code is ErrorCode.SOURCE_UNAVAILABLE
        assert caught.value.params == {"source": "fake", "status": 503}

    serve([Reply(503)], scenario)
    assert sleeps.waits == [1, 2, 4]


def test_a_client_error_is_not_retried() -> None:
    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(sleep=Sleeps()) as http:
            with pytest.raises(TezError) as caught:
                await http.get(FAST, fake.url)
        assert caught.value.code is ErrorCode.SOURCE_REJECTED
        assert caught.value.params == {"source": "fake", "status": 400}

    fake = serve([Reply(400)], scenario)
    assert len(fake.requests) == 1


def test_connection_refused_reports_network_error() -> None:
    async def main() -> None:
        # Bind then close, so the port is known to refuse.
        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        server.close()
        await server.wait_closed()
        # Windows retries a refused connection for about 2 s; a timeout must not win that race.
        patient = SourcePolicy(
            name="fake", requests_per_second=UNLIMITED, timeout_seconds=10, max_attempts=1
        )
        async with HttpClient(sleep=Sleeps()) as http:
            with pytest.raises(TezError) as caught:
                await http.get(patient, f"http://127.0.0.1:{port}/")
        assert caught.value.code is ErrorCode.SOURCE_NETWORK

    asyncio.run(main())


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("7", 7.0),
        ("0", 0.0),
        (None, None),
        ("soon", None),
        ("-3", None),
        ("Wed, 04 Nov 2026 12:00:30 GMT", 30.0),
        ("Wed, 04 Nov 2026 11:00:00 GMT", 0.0),
    ],
)
def test_parse_retry_after(value: str | None, expected: float | None) -> None:
    now = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)
    assert parse_retry_after(value, now=now) == expected


# --- rate limiter ---------------------------------------------------------------------


def test_rate_limiter_spaces_requests() -> None:
    now = [100.0]
    limiter = RateLimiter(2, clock=lambda: now[0])
    assert [limiter.reserve() for _ in range(3)] == [0, 0.5, 1.0]
    now[0] += 10  # idle time does not build up a burst
    assert [limiter.reserve() for _ in range(2)] == [0, 0.5]


def test_concurrent_requests_to_one_source_are_spaced() -> None:
    sleeps = Sleeps()
    policy = SourcePolicy(name="slow", requests_per_second=2)

    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(sleep=sleeps) as http:
            await asyncio.gather(*(http.get(policy, fake.url) for _ in range(3)))

    fake = serve([Reply()], scenario)
    assert len(fake.requests) == 3
    assert sorted(sleeps.waits) == pytest.approx([0.5, 1.0], abs=0.05)


def test_each_source_has_its_own_limiter() -> None:
    sleeps = Sleeps()
    first = SourcePolicy(name="a", requests_per_second=1)
    second = SourcePolicy(name="b", requests_per_second=1)

    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(sleep=sleeps) as http:
            await http.get(first, fake.url)
            await http.get(second, fake.url)

    serve([Reply()], scenario)
    assert sleeps.waits == []


# --- cache ----------------------------------------------------------------------------


def test_a_response_with_a_ttl_is_served_from_the_cache(tmp_path: Path) -> None:
    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(cache_path=tmp_path / "cache.sqlite", sleep=Sleeps()) as http:
            first = await http.get(FAST, fake.url, params={"q": "x"}, cache_ttl=60)
            second = await http.get(FAST, fake.url, params={"q": "x"}, cache_ttl=60)
            other = await http.get(FAST, fake.url, params={"q": "y"}, cache_ttl=60)
        assert first.json() == second.json() == {"n": 1}
        assert other.json() == {"n": 2}

    fake = serve([Reply(body='{"n": 1}'), Reply(body='{"n": 2}')], scenario)
    assert len(fake.requests) == 2


def test_the_cache_survives_a_restart(tmp_path: Path) -> None:
    async def scenario(fake: FakeServer) -> None:
        for _ in range(2):
            async with HttpClient(cache_path=tmp_path / "cache.sqlite", sleep=Sleeps()) as http:
                await http.get(FAST, fake.url, cache_ttl=60)

    fake = serve([Reply()], scenario)
    assert len(fake.requests) == 1


def test_an_expired_entry_is_fetched_again(tmp_path: Path) -> None:
    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(cache_path=tmp_path / "cache.sqlite", sleep=Sleeps()) as http:
            await http.get(FAST, fake.url, cache_ttl=0.05)
            await asyncio.sleep(0.1)
            await http.get(FAST, fake.url, cache_ttl=0.05)

    fake = serve([Reply()], scenario)
    assert len(fake.requests) == 2


def test_without_a_ttl_the_cache_is_neither_read_nor_written(tmp_path: Path) -> None:
    """A search run must record what the source says now, so searches never use the cache."""

    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(cache_path=tmp_path / "cache.sqlite", sleep=Sleeps()) as http:
            await http.get(FAST, fake.url, cache_ttl=60)
            await http.get(FAST, fake.url)
            await http.get(FAST, fake.url)

    fake = serve([Reply()], scenario)
    assert len(fake.requests) == 3


@pytest.mark.parametrize("status", [404, 500])
def test_failures_are_not_cached(tmp_path: Path, status: int) -> None:
    policy = SourcePolicy(name="fake", requests_per_second=UNLIMITED, max_attempts=1)

    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(cache_path=tmp_path / "cache.sqlite", sleep=Sleeps()) as http:
            with pytest.raises(TezError):
                await http.get(policy, fake.url, cache_ttl=60)
            response = await http.get(policy, fake.url, cache_ttl=60)
        assert response.status_code == 200

    fake = serve([Reply(status), Reply()], scenario)
    assert len(fake.requests) == 2


def test_a_corrupt_cache_file_does_not_stop_requests(tmp_path: Path) -> None:
    cache = tmp_path / "cache.sqlite"
    cache.write_bytes(b"this is not a database" * 100)

    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(cache_path=cache, sleep=Sleeps()) as http:
            for _ in range(2):
                response = await http.get(FAST, fake.url, cache_ttl=60)
                assert response.json() == {"ok": True}

    fake = serve([Reply()], scenario)
    assert len(fake.requests) == 2


# --- secrets and identity -------------------------------------------------------------


def test_api_keys_reach_the_source_but_not_the_cache(tmp_path: Path) -> None:
    cache = tmp_path / "cache.sqlite"
    secret = "s3cret-key-value"

    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(
            cache_path=cache,
            sleep=Sleeps(),
            secret_headers={"127.0.0.1": {"x-api-key": secret}},
        ) as http:
            await http.get(FAST, fake.url, cache_ttl=60)

    fake = serve([Reply()], scenario)
    assert fake.requests[0]["x-api-key"] == secret

    with closing(sqlite3.connect(cache)) as db:
        stored = list(db.execute("select * from entries"))
    assert stored, "the response should have been cached"
    assert secret.encode() not in json.dumps(stored, default=repr).encode()
    for path in tmp_path.iterdir():
        assert secret.encode() not in path.read_bytes()


def test_api_keys_go_only_to_their_own_host() -> None:
    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(
            sleep=Sleeps(), secret_headers={"api.example.org": {"x-api-key": "k"}}
        ) as http:
            await http.get(FAST, fake.url)

    fake = serve([Reply()], scenario)
    assert "x-api-key" not in fake.requests[0]


def test_requests_identify_the_application_without_personal_data() -> None:
    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(sleep=Sleeps()) as http:
            await http.get(FAST, fake.url)

    fake = serve([Reply()], scenario)
    assert fake.requests[0]["user-agent"].startswith("TEz/")


def test_outgoing_urls_stay_out_of_the_logs() -> None:
    """Source URLs can carry the user's e-mail, so the client's per-request log line is off."""
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    stream = io.StringIO()
    configure_logging(Settings(log_level="INFO"), stream=stream)

    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(sleep=Sleeps()) as http:
            await http.get(FAST, fake.url, params={"mailto": "someone@example.org"})

    try:
        serve([Reply()], scenario)
    finally:
        root.handlers[:], root.level = saved
    assert "someone@example.org" not in stream.getvalue()


def test_back_off_starts_at_the_source_policy() -> None:
    sleeps = Sleeps()
    policy = SourcePolicy(
        name="fake",
        requests_per_second=UNLIMITED,
        max_attempts=3,
        backoff_seconds=2,
        jitter_seconds=0,
    )

    async def scenario(fake: FakeServer) -> None:
        async with HttpClient(sleep=sleeps) as http:
            with pytest.raises(TezError):
                await http.get(policy, fake.url)

    serve([Reply(503)], scenario)
    assert sleeps.waits == [2, 4]
