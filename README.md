# TEz

[![CI](https://github.com/Adoocat/TEz/actions/workflows/ci.yml/badge.svg)](https://github.com/Adoocat/TEz/actions/workflows/ci.yml)

A local-first desktop workbench for systematic literature reviews, built for graduate students: search → screen → read → notes and literature matrix → thesis writing.

> **Status:** early development (Phase 1). Not usable yet.

## Principles

- **Local-first.** Your library (database, PDFs, notes) lives in a folder on your machine. The network is used only for academic search, metadata and PDF download (OpenAlex, Semantic Scholar, arXiv, Crossref, DBLP, Unpaywall).
- **Traceable.** Every piece of information extracted from a PDF links back to its exact location. AI suggestions are never saved without your approval.
- **Systematic.** Searches and screening decisions are append-only records; PRISMA 2020 counts are derived from them, never stored.

## Architecture

A Tauri v2 shell runs a React + TypeScript UI and starts a Python (FastAPI) backend as a local sidecar bound to `127.0.0.1` with a per-session token. The same backend also runs in a browser-only mode (`tez serve`) and behind a `tez` terminal command. Data is stored in SQLite (WAL, FTS5).

See [`docs/plan.md`](docs/plan.md) for the architecture and Phase 1 plan, and [`docs/adr/`](docs/adr/) for architecture decisions.

## Development

Requirements: [uv](https://docs.astral.sh/uv/), Node 24 with pnpm, Rust (stable, MSVC on Windows) and, on Windows, Visual Studio Build Tools and WebView2. No `make` or bash is needed; helper scripts are Node or Python.

```text
pnpm bootstrap     install Python and Node dependencies and the git hooks
pnpm dev           backend (http://127.0.0.1:8787) + web UI (http://localhost:1420)
pnpm dev:desktop   the web UI inside the Tauri desktop shell
pnpm check         lint, type check and tests for Python, TypeScript and Rust (same as CI)
pnpm check py web  only some groups: py, web, rust, format
pnpm format        apply Prettier and ruff formatting
```

`pnpm dev` opens a development library in `backend/.dev/TEz Library` (git-ignored, created on first run). Every API request needs `Authorization: Bearer <token>`. `pnpm dev` prints a fresh token at start-up; in dev mode the API docs at `http://127.0.0.1:8787/docs` open without it (use "Authorize" to call endpoints). Settings come from `TEZ_*` environment variables (`TEZ_LOG_LEVEL`, `TEZ_LOG_FORMAT=json|console`, `TEZ_CORS_ORIGINS`).

Database migrations (Alembic, run from `backend/`): `uv run alembic upgrade head` applies them to a development database in `backend/.dev/`; `uv run alembic revision --autogenerate --rev-id 0002 -m "..."` creates the next one. The app migrates each library itself on start-up. See [ADR 0003](docs/adr/0003-database-layer.md).

Layout: `backend/` (Python, uv), `apps/web/` (React + Vite), `apps/desktop/` (Tauri). Progress is tracked in [`docs/progress.md`](docs/progress.md).

## License

[MIT](LICENSE)
