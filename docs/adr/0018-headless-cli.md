# 0018 — The `tez` command: one set of services, reached through the open app or directly

- **Status:** Accepted
- **Date:** 2026-11-11
- **Task:** 23 (headless CLI)

## Context

Task 23 covers `tez search`, `tez import`, `tez add` and `tez export` with Typer, plus `--json`, `--library` and exit codes. When an instance is running, the command uses its API; otherwise it takes the lock and writes to the database directly. Acceptance: *end-to-end tests pass in both modes, and `--help` comes in Turkish and English.* The plan's rules apply: there are never two writers, work started from the terminal shows live in the window, `search_run.initiated_via = cli`, human output is in the system language, and `--json` field names are English.

## Decision

- **One package, `tez.cli`,** installed as the `tez` console script. `tez-backend cli …` forwards to it, so the Phase 6 console shell can be a thin `tez.exe` that calls the backend binary.
- **Choosing the mode** (`cli/access.py: connect`):
  - If the library's lock is held and `.tez/instance.json` names an API, the command talks to that API with its token (`ApiAccess`).
  - If the lock is held by something without an API (another `tez` command), the command stops with `cli.library_busy`.
  - If nobody holds the lock, the command opens the library itself (`kind="cli"`) and calls the same services (`DirectAccess`).

  Both ways return the API's own response models, so the commands, their output and the tests do not depend on the mode.
- **What the commands do:**
  - `search` resolves the review by id or by Turkish-folded title. Naming it is optional when the library has only one. It accepts source aliases (`oa`, `s2`, `cr`), prints per-source progress (from the SSE stream in API mode, or from the listener in direct mode) and records the search as `cli`.
  - `import` logs the file as a search run of the review. The backend reads the file by path, and the run is recorded as `cli`.
  - `add` accepts files and folders (PDFs found recursively), and `--collection` finds the collection by its folded name or makes it.
  - `export` writes BibTeX or RIS for a review, a collection or the whole library, to a file or standard output.
- **Export is a new module** (`modules/export`, `GET /export`). Titles are double-braced, LaTeX specials are escaped, Unicode is kept, and pages use `--`. A review record that was never kept gets a citation key for that file only. Both formats read back through our importers.
- **Exit codes:** 0 done; 1 failed; 2 partly done (a source failed, entries were skipped, some files could not be added). Failures carry the backend's codes. With `--json`, the output is a single JSON document (`{"mode": …, …}` or `{"error": {"code", "params"}}`).
- **Language:** the order is `--lang`, then `TEZ_LANG`, then the system UI language (Windows `GetUserDefaultUILanguage`, then `LANG`). It is fixed before the commands are built, so `--help` is translated too. Click's and Typer's own words (section headings, `[default]`, the help option, usage errors) are translated by swapping the module-level `_` in Typer's bundled Click. Two strings are hard-coded there and stay English: "Usage:" and "Try … for help.". A test checks the Turkish help, so a Typer update that moves these strings shows up.
- **Output is always UTF-8,** so `tez --json | …` keeps "ş" and "İ" on Windows. Library warnings (for example a BibTeX parser's note) are silenced unless `TEZ_LOG_LEVEL` is set; what matters is already in the command's report.

## Consequences

- Direct mode has no worker. PDFs added there are inspected the next time the app opens, and the command says so.
- In API mode a search runs in the app's process, so the window shows it live, and closing the terminal does not stop it.
- Not built yet: `tez list`, `tez jobs`, `tez backup` and `tez prisma` from the plan's command table, and the window commands (`tez <file>` starting the desktop app), which come with the console shell in Phase 6. A UI for exporting (design 5.10) is also still to come.
- New dependency: `typer` 0.29 (MIT). It bundles Click (BSD-3-Clause) and pulls in `rich` (MIT) and `shellingham` (ISC).
