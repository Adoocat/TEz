# 0004 — Phase 1 schema: append-only history, corrections, job de-duplication

- **Status:** Accepted
- **Date:** 2026-11-03
- **Task:** 6 (Phase 1 tables)

## Context

Task 6 creates groups 1 and 2 of the data model (without quality assessment), plus `processing_job` and `setting`. CLAUDE.md rule 3 says `search_run`, `search_result` and `screening_decision` are append-only and a correction is a new row. The plan's data model has two details that conflict with that rule or with later use:

1. `screening_decision.superseded_by` is set on the *old* row when it is corrected. That is an UPDATE of an append-only table.
2. `processing_job.dedupe_key` is UNIQUE. A finished job would then block the same work forever, e.g. "reprocess this PDF".

Some smaller choices also needed a decision: how ids, times and enumerations are stored, and how deletes propagate.

## Decision

- **Corrections point backwards: `screening_decision.supersedes_id`** *(deviation from plan, approved)*.
  - A correction is a new row naming the decision it replaces. The old row never changes.
  - `supersedes_id` is UNIQUE, so a decision is corrected at most once and the corrections form a chain.
  - The decision in force is the one no other row supersedes.
  - The repository checks that a correction targets the same review, paper and stage.
- **Append-only is enforced by the database.** `BEFORE UPDATE` and `BEFORE DELETE` triggers on the three tables `RAISE(ABORT, 'append-only table: …')`. A bug or a hand-written SQL statement cannot rewrite the screening record.
  - Consequence: a `search_run` is written once, after its source has answered. Its progress is reported through the job queue, not by updating the row.
  - These tables have `created_at` but no `updated_at`.
- **`processing_job.dedupe_key` is unique only among active jobs** *(deviation from plan, approved)*. It is a partial unique index `WHERE status IN ('queued', 'running')`. The same work cannot be queued twice at once, but it can run again after it has finished. `JobsRepository.enqueue` returns the active job when there is one.
- **Screening decisions reference the review record.** A composite foreign key `(review_id, paper_id) → review_record` means only papers taken into a review can be screened in it.
- **Ids:** UUIDv7 text from `tez.shared.ids.new_id`, written by hand because Python 3.12 has no `uuid.uuid7`. Within one millisecond a counter keeps one process's ids strictly increasing (RFC 9562, method 1).
- **Times:** `UtcDateTime` stores fixed-width ISO 8601 text in UTC (`2026-11-03T19:49:03.000120+00:00`), so text order is time order. Naive datetimes are rejected. Migrations render it as `String(32)`, so they never import application types.
- **Enumerations:** `StrEnum`s stored as TEXT values, with named CHECK constraints such as `ck_review_status`. They are not SQLite enums, which do not exist.
- **Deletes:**
  - `CASCADE` for parts of a paper: identifiers, author links, collection and tag links, relations.
  - `RESTRICT` where the deletion must be deliberate:
    - attachments, because their files on disk must also go;
    - review records, search results and screening decisions, because history must not vanish;
    - authors, which outlive their papers.
  - Papers are normally soft-deleted (`deleted_at`).
- **`title_norm`** comes from `tez.shared.text.normalize_title`. Every i-like letter (I, İ, ı, i) folds to "i" and diacritics are dropped, so Turkish titles match regardless of case. Task 12 builds deduplication on it.
- **`setting`** is keyed by its name (`ui.language`) rather than a UUID. API keys never go there (rule 7).

## Consequences

- PRISMA counts are derived from `search_result`, `review_record` and the current decisions, never stored (rule 4).
- Task 13 must collect a source's answer before writing its run.
- Emptying the trash (later) must delete attachments and their files explicitly before the paper.
- Alembic autogenerate does not see triggers or partial-index predicates, so changes to them are written by hand. Tests assert that the triggers exist, that UPDATE and DELETE on the three tables fail, and that a finished job can be queued again.
