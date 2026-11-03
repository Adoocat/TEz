"""Job types and their handlers.

A handler is a plain function `(payload, ctx) -> None` that runs in the worker process.
It reports progress with `ctx.report(fraction)` and should stop early when
`ctx.cancelled` becomes true (the job was taken from it). Raising marks the attempt
failed; it is retried until `max_attempts`.
"""

import threading
from collections.abc import Callable
from typing import Any


class JobContext:
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self.progress: float | None = None
        self._cancelled = threading.Event()

    def report(self, progress: float) -> None:
        self.progress = min(max(progress, 0.0), 1.0)

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self) -> None:
        self._cancelled.set()


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
