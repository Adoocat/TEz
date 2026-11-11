"""The worker's job types. Feature tasks add theirs here (PDF text, Unpaywall, ...)."""

import time
from typing import Any

from tez.modules.files.open_access import FETCH_JOB, fetch_open_access
from tez.modules.files.service import INSPECT_JOB, inspect_attachment
from tez.modules.jobs.registry import JobContext, Registry

registry = Registry()
registry.handler(INSPECT_JOB)(inspect_attachment)
registry.handler(FETCH_JOB)(fetch_open_access)


@registry.handler("diagnostics.sleep")
def diagnostics_sleep(payload: dict[str, Any], ctx: JobContext) -> None:
    """Does nothing for a while, reporting progress: checks the queue end to end."""
    steps = int(payload.get("steps", 10))
    seconds = float(payload.get("seconds", 0.5))
    for step in range(1, steps + 1):
        if ctx.cancelled:
            return
        time.sleep(seconds)
        ctx.report(step / steps)
