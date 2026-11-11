"""Job types and their handlers.

A handler is a plain function `(payload, ctx) -> None` that runs in the worker process.
It reports progress with `ctx.report(fraction)` and should stop early when
`ctx.cancelled` becomes true (the job was taken from it). Raising marks the attempt
failed; it is retried until `max_attempts`.
"""

import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tez.core.db import Database


class JobContext:
    """What a handler gets besides its payload: the library, and which attempt this is."""

    def __init__(
        self,
        job_id: str,
        *,
        db: "Database | None" = None,
        attempt: int = 1,
        max_attempts: int = 1,
    ) -> None:
        self.job_id = job_id
        self._db = db
        # A handler that can crash the process (native code) sees its last chance here.
        self.attempt = attempt
        self.max_attempts = max_attempts
        self.progress: float | None = None
        self._cancelled = threading.Event()

    @property
    def db(self) -> "Database":
        if self._db is None:
            raise RuntimeError("this job context has no database")
        return self._db

    @property
    def library_path(self) -> Path:
        return self.db.path.parent

    @property
    def last_attempt(self) -> bool:
        return self.attempt >= self.max_attempts

    def report(self, progress: float) -> None:
        self.progress = min(max(progress, 0.0), 1.0)

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        self._cancelled.set()


class JobFailed(Exception):
    """Raise from a handler for a failure with its own error code.

    `retry=False` ends the job at once (the answer will not change: no open-access copy
    exists); `retry=True` counts as one failed attempt, like any other exception.
    """

    def __init__(
        self, code: str, params: dict[str, Any] | None = None, *, retry: bool = False
    ) -> None:
        super().__init__(code)
        self.code = code
        self.params: dict[str, Any] = dict(params or {})
        self.retry = retry


Handler = Callable[[dict[str, Any], JobContext], None]


class Registry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def handler(self, job_type: str) -> Callable[[Handler], Handler]:
        def register(func: Handler) -> Handler:
            if job_type in self._handlers:
                raise ValueError(f"job type registered twice: {job_type}")
            self._handlers[job_type] = func
            return func

        return register

    def get(self, job_type: str) -> Handler | None:
        return self._handlers.get(job_type)
