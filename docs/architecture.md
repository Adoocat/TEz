# TEz architecture

This is the map of the code as it stands after Phase 1. Read it before [`plan.md`](plan.md), which has the full design and later phases. The *why* behind each choice is in the [ADRs](adr/).

## Processes

```text
┌────────────── Tauri v2 shell (Rust) ──────────────┐
│ starts the sidecar with a token on stdin, kills it │  apps/desktop/src-tauri
│ with the window (Job Object on Windows)            │  ADR 0001
└──────────────┬─────────────────────────────────────┘
               │ webview (WebView2) or any browser
┌──────────────▼──────────────┐   HTTP + SSE, Bearer token   ┌───────────────────────────┐
│ React UI                    │ ───────────────────────────► │ tez-backend serve         │
│ apps/web                    │                              │ FastAPI on 127.0.0.1      │
│ TanStack Query, i18n, Radix │ ◄─────────────────────────── │ backend/src/tez           │
└─────────────────────────────┘                              └──────┬─────────────▲──────┘
                                                    starts, watches │             │ jobs table
                                                                    ▼             │ (lease)
                                                             ┌──────────────────────────┐
                                                             │ tez-backend worker       │
                                                             │ PDF inspection, OA       │
                                                             │ downloads, backups       │
                                                             └──────────────────────────┘
Library folder: library.sqlite (WAL, FTS5) · files/ · snapshots/ · derived/ · backups/ · .tez/
```

- **One backend binary, several modes** (`backend/src/tez/__main__.py`): `serve` runs the API, as the desktop sidecar (`--token-stdin`), in web mode, or in development (`--reload`); `worker` runs jobs; `restore` restores a backup. The terminal CLI (`tez`) is Task 23.
- **One process owns a library.** An OS file lock on `.tez/lock` decides who. `.tez/instance.json` tells others how to reach the owner's API (ADR 0004 for the schema, Task 5 for the lock).
- **The worker is a separate process** so that native code (PDFium) crashing on a hostile PDF takes down only the worker. The API restarts it, and a job whose lease runs out is retried (ADR 0005). A file that keeps crashing the worker is marked and skipped (ADR 0011).

## Backend modules

`backend/src/tez/modules/<name>/` follows one pattern: `router` (HTTP, no logic) → `service` (rules) → `repository` (SQL). Modules use each other's services, never their repositories.

| Module | What it does | ADRs |
| --- | --- | --- |
| `library` | Library folder (open, lock, migrate), papers, collections, tags, reading status, citation keys, metadata search (`paper_fts`) | 0004, 0013, 0014 |
| `search` | Source adapters (`providers/`), deduplication (`dedup.py`), federated search, search history | 0007–0009 |
| `importers` | BibTeX and RIS exports → `NormalizedRecord` → the search road | 0010 |
| `files` | PDFs stored by hash, inspection in the worker, open-access downloads, the range-capable file endpoint | 0011, 0012, 0015 |
| `reviews` | Reviews and their records (screening comes in Phase 2) | 0004 |
| `jobs` | Lease-based queue, worker supervisor, progress over SSE | 0005 |
| `backup` | Zip backups with a checksum manifest, verified restore | 0016 |
| `settings` | Library settings; API keys in the OS keyring | 0006 |

Shared code: `core/` (configuration, database and its pragmas, errors as codes, token auth, logging) and `shared/` (outbound HTTP with rate limits, retries and a cache; identifier normalization; Turkish-safe text folding).

### Rules that hold everywhere

- **Errors are codes.** A `TezError(code, params)` becomes `{"error": {"code": ..., "params": ...}}`, and the UI turns the code into a sentence in the user's language.
- **Append-only records.** `search_run`, `search_result` and `screening_decision` are protected by triggers. PRISMA counts are derived from them, never stored.
- **Text folding happens in one place.** `shared/text.fold` treats I, İ, ı and i as the same letter. `title_norm` and the search index use it, because SQLite's tokenizer does not get Turkish right.
- **Tests never go online.** External services sit behind `Protocol` adapters. Tests use fakes, recorded cassettes or a mock transport.

## Frontend

`apps/web/src/features/<name>/` is one vertical slice per screen (`search`, `imports`, `library`, `files`, `reader`, `jobs`, `settings`, `reviews`).

- **Server state lives only in TanStack Query.** Calls go through the client generated from the backend's OpenAPI schema (`src/api/`, `pnpm gen:api`); CI fails when it is stale.
- **UI state lives in small Zustand stores** (the open scope, the selection, notices).
- **Styling comes from design tokens.** `docs/design/tokens.json` becomes CSS variables (`pnpm gen:tokens`), then Tailwind classes. There are no raw colours.
- **Long lists are virtualized**: search results, the library table and reader pages.
- **Platform differences sit behind `lib/platform/`**: the Tauri sidecar connection, or the browser's `#api=…&token=…` link.

## Data flow examples

- **A search.** `POST /searches` returns at once. The sources are asked in parallel in the API process. Each answer is deduplicated and written in its own transaction, together with its raw snapshot. Progress streams over `/searches/{id}/events` (ADR 0009).
- **A dropped PDF.** `POST /pdfs` checks the header and hashes the bytes. It stores `files/ab/<sha256>.pdf` and records the attachment, then queues `pdf.inspect`. The worker counts the pages and checks for a text layer, and the UI sees the job change on `/jobs/events` (ADR 0011).
- **Reading.** pdf.js asks `/attachments/{id}/file` for 256 kB byte ranges. Only the pages near the screen get a canvas (ADR 0015).

## Testing

- `pnpm check` runs everything CI runs: ruff and pyright (strict) and pytest, the API client check, ESLint, `tsc` and Vitest, Prettier, and cargo fmt, test and clippy.
- `pnpm e2e` runs Playwright against a real backend on a temporary library. It covers the library flows, the 300-page reader acceptance and a smoke test.
- Acceptance criteria from the plan are written as tests and named after their task, for example `test_task_19_acceptance_search_in_2000_papers_under_100_ms`.
