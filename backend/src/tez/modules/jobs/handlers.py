"""The worker's job types. Feature tasks add theirs here (PDF text, Unpaywall, ...)."""

import time
from typing import Any

from tez.modules.backup.service import BACKUP_JOB, backup_job
from tez.modules.files.open_access import FETCH_JOB, fetch_open_access
from tez.modules.files.service import EXTRACT_JOB, INSPECT_JOB, inspect_attachment
from tez.modules.fulltext.service import extract_text
from tez.modules.jobs.registry import JobContext, Registry
from tez.modules.snowballing.service import SNOWBALL_JOB, snowball_job

registry = Registry()
registry.handler(INSPECT_JOB)(inspect_attachment)
registry.handler(EXTRACT_JOB)(extract_text)
registry.handler(FETCH_JOB)(fetch_open_access)
registry.handler(BACKUP_JOB)(backup_job)
registry.handler(SNOWBALL_JOB)(snowball_job)


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
