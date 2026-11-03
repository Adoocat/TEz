# TEz

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

Development setup and commands are added in Phase 1, task 1. Progress is tracked in [`docs/progress.md`](docs/progress.md).

## License

[MIT](LICENSE)
