# 0002 — Repository tooling choices

- **Status:** Accepted
- **Date:** 2026-11-03
- **Task:** 1 (monorepo and tools)

## Context

Task 1 sets up the monorepo so that one root command, `pnpm check`, lints, type checks and tests both sides on Windows without `make`. While doing so, a few points differed from `docs/plan.md` / `CLAUDE.md` or were not covered by them. The owner approved each item below before implementation.

## Decision

1. **`pnpm bootstrap` instead of `pnpm setup`.** `pnpm setup` is a built-in pnpm command (it configures `PNPM_HOME`), so a script with that name only runs via `pnpm run setup`. `CLAUDE.md` now lists `pnpm bootstrap`.
2. **The Tauri scaffold (`apps/desktop`) is created in Task 1**, not left for Task 8, so `pnpm dev:desktop` works from the start. It only hosts the web UI; the sidecar contract from ADR 0001 is wired in later. `pnpm check` therefore also runs `cargo fmt --check` and `cargo clippy -D warnings`; CI (Task 2) needs the Rust toolchain and the WebKitGTK packages on Ubuntu.
3. **Prettier** formats TypeScript, JavaScript, JSON, YAML and CSS (not Markdown, Python or Rust). `eslint-config-prettier` turns off ESLint rules that would conflict.
4. **TypeScript is pinned to 6.0.x**, not 7. `typescript-eslint` 8.72 (current) supports `typescript <6.1`. Revisit when typescript-eslint supports TypeScript 7.
5. **pyright comes from npm**, not PyPI. The PyPI wrapper downloads Node on first run, which fails offline and adds a network step to CI.
6. **pre-commit hooks call the project's own tools** (`language: system` via `uv run` / `pnpm exec`), so hook results match `pnpm check` and no second set of tool versions is pinned. The only remote hook repo is `pre-commit/pre-commit-hooks` (whitespace, YAML/JSON/TOML syntax, merge markers, case conflicts, files over 500 KB).
7. **The FastAPI test client uses `httpx2`.** Starlette deprecates `httpx` for `TestClient` in favour of `httpx2` (Pydantic's successor, BSD-3-Clause). The plan names `httpx` for outbound HTTP; that choice is revisited in Task 9.
8. **`pnpm check` is a Node script** (`scripts/check.mjs`) that runs every step even after a failure, prints a summary and exits 1 if any step failed. `pnpm check py web` runs selected groups.

## Consequences

- One command checks Python (ruff, pyright strict on `src/tez`, pytest), TypeScript (ESLint type-aware, `tsc`, Vitest), formatting (Prettier) and Rust (fmt, clippy).
- `pytest` treats warnings as errors, so dependency deprecations surface early.
- Commands whose task has not landed (`gen:api`, `e2e`) print a short note and exit 0, so every documented command runs.
- The first `cargo clippy` run compiles Tauri (~2 min); later runs are incremental.
