# 0016 — Backups: one zip with a checksum manifest, restored only into a new folder

- **Status:** Accepted
- **Date:** 2026-11-11
- **Task:** 21 (closing)

## Context

Task 21 adds backups (SQLite backup API plus zip), the README, an architecture document and a Playwright smoke test. Acceptance: *a restore-from-backup test passes.* A library is a database plus files that the database points at by path and hash. A backup is only useful if it can be shown to be complete and unchanged when it is restored.

## Decision

- **A backup is one zip file**, `backups/TEz-backup-<UTC time>.zip`, holding:
  - a copy of `library.sqlite` taken with SQLite's online backup API. That copy is consistent while the app and the worker write (WAL), and it is checked with `PRAGMA integrity_check` before it goes in;
  - `files/` (PDFs, stored uncompressed because they are already compressed) and `snapshots/` (raw search answers);
  - `tez-backup.json`: the format version, app version, schema revision, paper and file counts, and the size and SHA-256 of every entry.

  `derived/` is left out because it can be produced again, and so are `.tez/` and `backups/`. The zip is written to a hidden `.part` file and renamed when complete, so a half-written backup is never listed.
- **Backing up is a job** (`library.backup`, run by the worker, with progress). Settings › Backup starts it and lists the backups with their contents. Asking twice while one runs queues nothing more.
- **A restore never overwrites an open library.** `tez-backend restore <zip> <folder>` unpacks into a missing or empty folder. Every entry is checked against the manifest's SHA-256, entries that would land outside the folder (`..`, absolute paths) are refused, and the database passes `integrity_check`. The folder is then opened once, which migrates an older schema (with its own pre-migration copy) and rebuilds the search index if needed. On any failure the half-restored folder is removed.
- **No restore button in the UI yet.** Restoring means switching libraries, and the welcome screen and library picker (design 4.1, open question 1) do not exist. Settings shows the command meanwhile.

## Consequences

- The acceptance test backs up a library that has an imported search run, a PDF and a collection. After restoring it, the papers with their citation keys, the collection counts, search results, search history and PDF bytes all match.
- Backups are manual. A schedule and keeping only the last *n* (design: "Son yerel yedek") come later.
- A backup is as large as the PDFs. Copying it off the machine is the user's step, and Settings says so.
