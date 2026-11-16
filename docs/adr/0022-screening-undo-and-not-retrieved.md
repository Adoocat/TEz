# 0022 — Screening decisions: undo and "full text not retrieved"

- **Status:** Accepted
- **Date:** 2026-11-16
- **Task:** 31 (screening service and API); used by Task 33 and Task 34

## Context

The plan's data model gives `screening_decision.decision` three values: include, exclude, maybe. Two Phase 2 requirements do not fit them:

1. Task 31: undo is a new row (the table is append-only, ADR 0004). Undoing a record's first decision must leave it undecided, and none of the three values says "undecided".
2. Task 33: "full text could not be obtained" is a full-text outcome that PRISMA 2020 counts in its own box ("reports not retrieved"), apart from exclusions with reasons.

The owner chose on 2026-11-14 to add two values rather than encode them through criteria.

## Decision

- `decision` gains `undecided` and `not_retrieved` (migration 0012). SQLite cannot change a CHECK constraint, so the migration rebuilds the table and recreates its append-only triggers.
- `undecided` is written only by undo. A person chooses include, exclude, maybe or (full text only) not retrieved; the API refuses the rest.
- Each record, stage and reviewer has one chain: every new decision supersedes that reviewer's current one (`supersedes_id`). A correction is just a new decision; deciding what is already in force writes nothing.
- Undo names the decision it takes back and writes a row restoring the state before it: the decision it superseded, or `undecided` if it superseded none. Pressing undo again on the previous decision walks back one more step. If the record was decided again since, undo is refused (`screening.undo_stale`) instead of silently discarding the newer decision.
- The state is derived: the current decision of the owner's chain (`reviewer = "owner"`), `undecided` when there is none or it is an `undecided` row. The full-text queue is the records whose current title-abstract decision is include or maybe; a full-text decision on a record that has since left that queue does not count.
- Other modules read this through `tez.modules.screening.service` (`ScreeningService.current`, `queue`, `entries`, `included`, `reviewers`); two-reviewer screening passes its own `reviewer`.

## Consequences

- PRISMA (Task 34) counts `not_retrieved` in its own box and never sees `undecided` as a decision.
- Downgrading past migration 0012 fails on a library that holds the new values, which leaves it unchanged.
- The history keeps every step, including undos, so a reviewer's path through a record can be audited.
