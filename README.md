# TEz

[![CI](https://github.com/Adoocat/TEz/actions/workflows/ci.yml/badge.svg)](https://github.com/Adoocat/TEz/actions/workflows/ci.yml)

A local-first desktop workbench for systematic literature reviews, built for graduate students: search → screen → read → notes and literature matrix → thesis writing.

> **Status:** Phase 1 (library and search) is complete. Screening, notes, the literature matrix and installers come in later phases ([plan](docs/plan.md), [progress](docs/progress.md)).

## What works today

- **Systematic search** across OpenAlex, Semantic Scholar, arXiv and Crossref at once. Each source has its own translated query and live state, and each search stays on record for the method section. Duplicates are merged by DOI or arXiv id, then by fuzzy title with year and author checks. Preprints are linked to their published versions.
- **Imports from databases without an open API** (IEEE Xplore, ACM DL, Scopus, Web of Science). BibTeX and RIS exports are previewed with a report of broken entries, then logged as search runs.
- **A library** with collections (a tree, a paper in several), coloured tags, reading status, and citation keys like `yilmaz2024automated`. A virtualized, sortable, filterable table handles 2000+ papers. Metadata full-text search folds Turkish correctly (`isik` finds "Işık") and answers in milliseconds.
- **PDFs** can be dropped on the window. Each file is stored once by hash and checked in a separate worker process, so a broken file cannot crash the app. Free copies can be fetched from arXiv and Unpaywall in the background.
- **A reader** built on pdf.js streams the PDF in byte ranges and draws only the pages near the screen. It has a selectable text layer, zoom, and links to a page (`#/reader/<id>?page=12`).
- **Backups** are one zip with checksums. Restoring goes into a new folder and is verified before the library opens.
- **The `tez` terminal command** searches, imports exported results, adds PDFs and exports BibTeX or RIS. It works through the open window when there is one, or on the library directly when there is not.

## Principles

- **Local-first.** Your library (database, PDFs, notes) lives in a folder on your machine. The network is used only for academic search, metadata and PDF download (OpenAlex, Semantic Scholar, arXiv, Crossref, Unpaywall).
- **Traceable.** Every piece of information extracted from a PDF links back to its exact location. AI suggestions are never saved without your approval.
- **Systematic.** Searches and screening decisions are append-only records; PRISMA 2020 counts are derived from them, never stored.

## Architecture

A Tauri v2 shell runs a React + TypeScript UI and starts a Python (FastAPI) backend as a local sidecar on `127.0.0.1` with a per-session token. A worker process, supervised by the backend, runs PDF inspection, downloads and backups from a lease-based job queue in SQLite. The same backend also runs without the shell for the browser (`tez-backend serve`). Data lives in one SQLite database (WAL, FTS5) next to the files.

Read [`docs/architecture.md`](docs/architecture.md) first, then [`docs/plan.md`](docs/plan.md) for the plan and [`docs/adr/`](docs/adr/) for the decisions and why they were made.

## Development

Requirements: [uv](https://docs.astral.sh/uv/), Node 24 with pnpm, Rust (stable, MSVC on Windows) and, on Windows, Visual Studio Build Tools and WebView2. No `make` or bash is needed; helper scripts are Node or Python.

```text
pnpm bootstrap     install Python and Node dependencies and the git hooks
pnpm dev           backend (http://127.0.0.1:8787) + web UI (http://localhost:1420)
pnpm dev:desktop   the web UI inside the Tauri desktop shell
pnpm check         lint, type check and tests for Python, TypeScript and Rust (same as CI)
pnpm check py web  only some groups: py, api, web, rust, format
pnpm e2e           end-to-end tests (Playwright) against a real backend on a temporary library
pnpm gen:api       regenerate the typed API client after changing the backend's API
pnpm gen:tokens    regenerate the CSS variables after changing docs/design/tokens.json
pnpm format        apply Prettier and ruff formatting
```

The first `pnpm e2e` needs a browser: `pnpm --filter @tez/web exec playwright install chromium`.

`pnpm dev` opens a development library in `backend/.dev/TEz Library` (git-ignored, created on first run). Every API request needs `Authorization: Bearer <token>`. `pnpm dev` prints a fresh token at start-up; in dev mode the API docs at `http://127.0.0.1:8787/docs` open without it (use "Authorize" to call endpoints). Settings come from `TEZ_*` environment variables (`TEZ_LOG_LEVEL`, `TEZ_LOG_FORMAT=json|console`, `TEZ_CORS_ORIGINS`).

### The `tez` command

```text
tez search '"code review" AND LLM' --sources oa,s2 --review "My SLR"
tez import scopus.ris --source Scopus --searched-at 2026-11-01 --query '"code review"'
tez add papers/ --collection Thesis
tez export --format bibtex --review "My SLR" -o refs.bib
```

In development, run it as `uv run --project backend tez …`. Common options: `--library <folder>` (default: `TEZ_LIBRARY`, or `Documents/TEz Library`), `--json` for scripts, `--lang tr|en`, `--quiet`. Exit codes: 0 done, 1 failed, 2 partly done. Output is UTF-8. In Windows PowerShell 5.1, piping it into another command needs `[Console]::OutputEncoding = [Text.Encoding]::UTF8` first.

### Useful commands

```text
uv run --project backend tez-backend serve --library <folder> --create
    the API on an existing or new library, in web mode; prints the address and token
uv run --project backend python -m tez.devtools.demo <folder> --papers 2000
    a demo library of fictional papers (fixed seed), for trying the app and measuring it
uv run --project backend tez-backend restore <TEz-backup-….zip> <new folder>
    restore a backup into a new library folder (checked against its checksums)
```

Database migrations (Alembic, run from `backend/`): `uv run alembic upgrade head` applies them to a development database in `backend/.dev/`; `uv run alembic revision --autogenerate --rev-id 0008 -m "..."` creates the next one. The app migrates each library itself on start-up, after copying the database to `backups/`. See [ADR 0003](docs/adr/0003-database-layer.md).

Layout: `backend/` (Python, uv), `apps/web/` (React + Vite, `e2e/` for Playwright), `apps/desktop/` (Tauri). Progress is tracked in [`docs/progress.md`](docs/progress.md).

## License

[MIT](LICENSE). Third-party licenses are listed in [`docs/licenses.md`](docs/licenses.md).
