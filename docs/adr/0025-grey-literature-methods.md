# 0025 — Grey literature as other-methods runs

- **Status:** Accepted
- **Date:** 2026-11-16
- **Task:** 37 (grey literature)

## Context

PRISMA 2020's "identification via other methods" branch counts records from websites, organisations, citation searching and other sources; the plan (Task 34) names its boxes as snowballing, websites, organisations, registers and theses. Task 37 adds records by hand (thesis, report, register record, web page) and lets an import be marked as coming from a website or an organisation. Both must go through deduplication, and PRISMA must derive every count (CLAUDE.md rule 4). ADR 0024 already records snowballing as `search_run`s with a `method`.

## Decision

- `search_run.method` gains `website`, `organisation`, `register` and `thesis` (migration 0015). The method is the PRISMA box.
- A record entered by hand is stored like a one-record import: matched against the library (the same thesis from a database later is a duplicate, not a second paper), logged as a run whose source is where it was found ("YÖK Ulusal Tez Merkezi") and whose snapshot is the entry as typed, then taken into the review. Its box follows its kind (thesis → theses, web page → websites, register record → registers, report → organisations) unless the user picks another.
- An import can be logged with `method` website, organisation or register; a database search stays the default. Citation methods cannot be claimed by an import.
- Records from other methods enter the review with origin `manual` (no new origin value, so `review_record` keeps its schema); the run's method says which box.
- The search history lists only database searches; grey literature has its own list on the review panel.
- Register records and web pages are stored with venue type `other`.

## Consequences

- PRISMA (Task 34) counts the other-methods branch per method from `search_run` and `search_result`; duplicates across branches follow from the shared matching.
- Exports type register records and web pages as generic entries until a finer venue type is needed.
