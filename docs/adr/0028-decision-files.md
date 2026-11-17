# 0028 — Two reviewers, two libraries: decision files

- **Status:** Accepted
- **Date:** 2026-11-17
- **Task:** 41 (moving screening decisions between libraries)

## Context

ADR 0019 settled two-reviewer screening for the end of Phase 2: everyone screens in their own library, decisions travel as a file, and Cohen's kappa follows (Task 42). TEz is local-first, so there is no shared server. Papers have different ids in each library, and `screening_decision` is append-only (CLAUDE.md rule 3). Acceptance: a round trip between two temporary libraries, and importing the same file twice creates nothing.

## Decision

- **`reviewer` values** (`screening_decision.reviewer`): `owner` is the library's owner, `consensus` is a reconciled decision (Task 42), and any other name is a colleague's imported decisions. `owner` and `consensus` cannot be used as an exported name.
- **The file** (`tez.screening-decisions`, `version` 1, JSON Schema in `docs/formats/screening-decisions.v1.schema.json`) is a snapshot of one reviewer's decisions in force, at most one per record and stage. It holds the review's title and method, its criteria (code, kind, text, stage), the records that have a decision (identifiers, title, year, first author, publication type) and the decisions (stage, decision, criterion code, note, time). A reader refuses another `format` or a newer `version` with its own error code, so a newer file is never misread.
- **Matching** uses the search deduplication rules (Task 12): an identifier first, then a fuzzy title checked against the year and first author. A record matches only papers taken into the target review, and each paper at most once. Records that do not match are reported (not in the library, in the library but not in the review, the same paper twice in the file).
- **Criteria** are matched by code. A decision citing a code the review lacks is not imported and is reported; it is never guessed.
- **Importing** writes through the screening service (Task 31) under the file's reviewer name, so every screening rule holds for imported rows too (an exclusion needs a reason, full text follows title-abstract). The plan compares the file with that reviewer's decisions in force: the same decision writes nothing, a changed one supersedes the earlier imported row, and a decision the file no longer has is left as it is and counted. Importing a file twice therefore adds no rows.
- **API:** `GET /reviews/{id}/decisions/export?reviewer=…`, `POST /reviews/{id}/decisions/import` (`{content}`: the file's text, so a bad file gets our error codes rather than a generic validation error), `GET /reviews/{id}/decisions/reviewers`.
- **UI:** a "Two reviewers" section on the review panel: export my decisions under a name kept on this device, import a colleague's file, and a report of what matched.

## Consequences

- Imported decisions never touch the owner's: the screening queue, filters and states read only `owner` rows (Task 31). Task 42 compares the two and writes reconciled decisions as `consensus`.
- A colleague's decision on a record the owner's review lacks is reported, not added; the owner imports that record first (for example the colleague's search export) and imports the decisions again.
- Only the decisions in force travel, not each reviewer's correction history; the receiving library keeps its own append-only history of what was imported when.
