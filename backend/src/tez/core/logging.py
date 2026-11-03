"""Structured logging on top of the standard library.

One JSON object per line on stderr (stdout is reserved for the sidecar handshake).
Every record made while serving a request carries that request's id.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TextIO

from tez.core.config import Settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes every LogRecord has; anything else was passed via `extra=` and is emitted as a field.
# `color_message` is uvicorn's ANSI-colored copy of the message.
_STANDARD_ATTRS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()
    | {"message", "asctime", "color_message"}
)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            request_id = request_id_var.get()
            if request_id is not None:
                record.request_id = request_id
        return True


def _extras(record: logging.LogRecord) -> dict[str, object]:
    return {k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        entry.update(_extras(record))
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable line for development: the message followed by `key=value` extras."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        extras = " ".join(f"{k}={v}" for k, v in _extras(record).items())
        if not extras:
            return line
        # Keep a traceback (added by the base class) below the extras.
        head, sep, tail = line.partition("\n")
        return f"{head} {extras}{sep}{tail}"


def configure_logging(settings: Settings, stream: TextIO | None = None) -> None:
    """Route all logging (ours, uvicorn's, libraries') through one root handler."""
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.addFilter(RequestIdFilter())
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(ConsoleFormatter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.log_level)
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    # RequestContextMiddleware logs every request with its id; uvicorn's access log would
    # duplicate it. uvicorn skips access logging when this logger has no handlers.
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
