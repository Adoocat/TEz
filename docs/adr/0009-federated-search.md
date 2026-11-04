# 0009 — Federated search: one transaction per source, one id per search

- **Status:** Accepted
- **Date:** 2026-11-04
- **Task:** 13 (federated search)

## Context

Task 13 asks all sources in parallel, tolerates partial failure, and writes `search_run`, `search_result` and a raw snapshot. Acceptance: *when one source crashes the other results still arrive and the error is on record.* Three questions were open:

1. Where does a search run: in the worker process or in the API?
2. How do the runs of one search stay together? The history and the result list need that, and `search_query` does not give it, because running a query again reuses its row.
3. What exists for a paper a search finds but the user has not chosen?

## Decision

- **A search runs as an asyncio task in the API process, not as a job.** It is network waiting, not CPU work, and it needs per-source progress (rate-limit countdowns) that `processing_job.progress` cannot carry. Progress lives in memory (`SearchRegistry`); the record lives in the database. If the process stops, finished sources stay on record and the running ones are simply absent.
- **`search_run.search_id`** groups one search's runs *(addition to the plan's data model)*. Migration 0003 uses plain `ALTER TABLE`, because a batch rebuild would drop the append-only triggers.
- **One transaction per source, written as soon as it answers.** Answers are processed one at a time, so papers created from one source are matched by the next. A database failure on one source rolls back that source only: the index reloads and a failed run is recorded.
- **A failure is a run.** A crashed or rejected source gets a `search_run` with `status=error` and the code in `error`, so the systematic record shows it was asked. Exceptions other than `TezError` are caught in exactly one place, logged with their traceback and recorded as `internal.unexpected`.
- **Every search result is a `paper` row,** because `search_result.paper_id` is required. The owner chose a `paper.library_added_at` column to mark what is really in the library (Task 14).
- **`search_query` holds the user's query and filters.** Each new query text in a review adds a row; repeating it reuses the row. There is no "saved" flag yet, because saved queries are not in Phase 1.
- **Enrichment only fills gaps.** A later source may add a missing abstract or identifier but never changes an existing value. An identifier already owned by another paper is not added, so a record holding the ids of a preprint and its publication cannot break the run.
- **Results are read per search through `PaperService`,** which is also how other modules reach papers: never through `LibraryRepository`.
- **Searches do not use the HTTP cache,** so the record reflects what the source says now (ADR 0007).

## Consequences

- PRISMA-style counts stay derived. `GET /searches/{id}` computes retrieved, unique and duplicates from the rows.
- The papers table holds every candidate a search returned, which is why Task 19's library list must filter on `library_added_at`.
- Retrying one failed source is not possible yet; the whole search is run again.
- `tez search` (Task 23) can call `run_search` directly with `initiated_via=cli`.
