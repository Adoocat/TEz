import io
import json
import logging
from collections.abc import Iterator
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.core.logging import configure_logging


@pytest.fixture
def log_stream() -> Iterator[io.StringIO]:
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    stream = io.StringIO()
    configure_logging(Settings(log_format="json", log_level="INFO"), stream=stream)
    yield stream
    root.handlers[:], root.level = saved


def lines(stream: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_json_line_has_utc_time_level_and_extras(log_stream: io.StringIO) -> None:
    logging.getLogger("tez.test").info("hello %s", "dünya", extra={"paper_count": 3})

    (entry,) = lines(log_stream)
    assert entry["level"] == "INFO"
    assert entry["logger"] == "tez.test"
    assert entry["msg"] == "hello dünya"
    assert entry["paper_count"] == 3
    assert datetime.fromisoformat(entry["ts"]).utcoffset() is not None
    assert entry["ts"].endswith("+00:00")


def test_exception_is_included(log_stream: io.StringIO) -> None:
    try:
        raise ValueError("bad pdf")
    except ValueError:
        logging.getLogger("tez.test").exception("failed")

    (entry,) = lines(log_stream)
    assert "ValueError: bad pdf" in entry["exc"]


def test_requests_are_logged_with_request_id_and_without_token(
    log_stream: io.StringIO, client: TestClient
) -> None:
    ok = client.get("/health", headers=AUTH)
    client.get("/health", headers={"Authorization": "Bearer guessed-token"})

    requests = [e for e in lines(log_stream) if e["msg"] == "request"]
    assert [(e["method"], e["path"], e["status"]) for e in requests] == [
        ("GET", "/health", 200),
        ("GET", "/health", 401),
    ]
    assert requests[0]["request_id"] == ok.headers["x-request-id"]
    assert isinstance(requests[0]["duration_ms"], float)
    output = log_stream.getvalue()
    assert TOKEN not in output
    assert "guessed-token" not in output


def test_query_string_is_not_logged(log_stream: io.StringIO, client: TestClient) -> None:
    client.get("/health?token=leak-me", headers=AUTH)

    # httpx2 is the test client itself logging its outgoing request; only server logs count.
    server_logs = [e for e in lines(log_stream) if not e["logger"].startswith("httpx")]
    assert server_logs
    assert "leak-me" not in json.dumps(server_logs)


def test_console_format_is_human_readable() -> None:
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    stream = io.StringIO()
    try:
        configure_logging(Settings(log_format="console"), stream=stream)
        logging.getLogger("tez.test").warning("disk almost full")
    finally:
        root.handlers[:], root.level = saved

    line = stream.getvalue().strip()
    assert "WARNING" in line
    assert "tez.test" in line
    assert line.endswith("disk almost full")


def test_console_format_shows_extras_on_the_same_line() -> None:
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    stream = io.StringIO()
    try:
        configure_logging(Settings(log_format="console"), stream=stream)
        logging.getLogger("tez.test").info("request", extra={"path": "/health", "status": 200})
    finally:
        root.handlers[:], root.level = saved

    assert stream.getvalue().strip().endswith("request path=/health status=200")


def test_uvicorn_access_log_does_not_reach_our_output(log_stream: io.StringIO) -> None:
    # Our request log replaces it, so each request is logged once, with its id.
    logging.getLogger("uvicorn.access").info('127.0.0.1 - "GET /health" 200')

    assert log_stream.getvalue() == ""
    assert logging.getLogger("uvicorn.access").propagate is False


def test_uvicorn_color_copy_is_dropped(log_stream: io.StringIO) -> None:
    logging.getLogger("uvicorn.error").info("started", extra={"color_message": "\x1b[1mstarted"})

    (entry,) = lines(log_stream)
    assert "color_message" not in entry
