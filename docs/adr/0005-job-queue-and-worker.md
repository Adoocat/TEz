# 0005 — Job queue and worker process

- **Status:** Accepted
- **Date:** 2026-11-04
- **Task:** 6b (job queue and worker)

## Context

The plan says that the API writes jobs to `processing_job` and a separate worker process leases them. If the worker dies, the lease expires and the job is retried; after three failures it is marked failed. The API starts and supervises the worker, and progress reaches the UI over Server-Sent Events. Open question 5 asked whether "progress is visible in the UI" can be checked before the UI exists (Task 8). The owner chose the recommended answer: in Phase 1 it is verified at the API and SSE level.

## Decision

- **Lease protocol, in `JobsRepository`:**
  - `claim` takes the highest-priority, then oldest, job that is either queued and due, or running with an expired lease. It sets `running`, `attempts + 1` and `lease_until = now + lease` (default 30 s, `TEZ_JOB_LEASE_SECONDS`).
  - An expired job with no attempts left becomes `failed` with `job.lease_expired`.
  - `attempts` is a **fencing token**: `heartbeat`, `complete` and `fail` are one conditional `UPDATE … WHERE status = 'running' AND attempts = :attempt`. A worker that lost its lease can therefore no longer change the job.
- **`lease_until` doubles as "not before" for queued jobs.** A failed attempt is re-queued with an exponential back-off (2^attempts s, at most 5 min), so a failing job cannot spin. This needed no schema change.
- **Errors are stored as codes**, `{"code": "job.handler_failed", "params": {"exception": "ValueError"}}`. The traceback goes to the log (the error model of Task 3).
- **Worker (`tez-backend worker --library <dir>`, `tez/worker.py`):**
  - It runs one job at a time.
  - A heartbeat thread extends the lease every lease/3 and saves progress at most every 0.25 s. If the lease is lost, `ctx.cancel()` tells the handler to stop.
  - It prints `TEZ_WORKER_READY {"pid"}` and exits on stdin EOF.
  - It opens the database without taking the library lock: it belongs to the API process that holds the lock.
- **Supervisor (`WorkerSupervisor`):**
  - The API starts the worker in its lifespan when a library is open, and restarts it with back-off (1 s doubling to 30 s, reset after a minute of uptime).
  - On shutdown it closes the worker's stdin, waits, then kills.
  - It takes the worker's pid from `TEZ_WORKER_READY`: on Windows a venv's `python.exe` is a launcher, so `Popen.pid` is not the worker.
  - `GET /jobs/worker` reports `alive`, `pid` and `restarts`.
- **Progress stream (`GET /jobs/events`)** uses FastAPI's built-in `EventSourceResponse`, which has keep-alive pings.
  - The stream polls the database every 0.25 s for jobs changed after a `(updated_at, id)` cursor, because the writer is another process.
  - A new client gets the active jobs first. A reconnecting client sends `Last-Event-ID` and gets exactly what it missed.
  - Polling reports the latest state, so a short-lived state (e.g. `queued`) may be folded into the next one.
  - The token travels in the `Authorization` header, so the UI reads the stream with `fetch`, not `EventSource`.
- **Job types** are registered in `modules/jobs/handlers.py`. Phase 1 has `diagnostics.sleep`, a harmless job that reports progress; it is used by the tests and for checking an installation. Feature tasks add their own handlers.
- **Layout:** queue code lives in `modules/jobs/` (models, repository, registry, handlers, supervisor, service, router), next to Task 6's model. The plan's folder sketch had a top-level `tez/jobs/` package; `tez/worker.py` is where the plan puts it.

## Consequences

- Acceptance is shown by real processes:
  - A worker is hard-killed mid-job; a second worker takes the job over only after the 1 s lease and finishes it on attempt 2.
  - Through the API, the supervisor restarts the killed worker, and the SSE stream shows the job running on attempts 1 and 2 with progress moving to `done`.
- Handlers must be idempotent: a job can run again after a worker crash.
- Job events are polled, not pushed. A notification channel can replace the polling later without changing the API.
- The UI part of "progress is visible" moves to Task 8: the jobs indicator in the status bar.
