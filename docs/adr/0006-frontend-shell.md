# 0006 — Frontend shell, preferences and the desktop sidecar

- **Status:** Accepted
- **Date:** 2026-11-04
- **Task:** 8 (frontend shell)

## Context

Task 8 builds the UI shell:
- routing and the three-panel layout;
- TanStack Query, tr/en, light/dark;
- the platform adapter;
- Tailwind + shadcn/ui on the design tokens;
- a basic Settings screen with language, theme, source email and API keys.

Acceptance: *language and theme changes persist; the app opens in the browser and in Tauri.* Several things were still open:
- No backend task covered the settings API and the keyring (open question 2).
- The Rust side of the sidecar was deferred to this task (Task 3).
- The UI half of Task 6b's "progress is visible" was deferred here as well.
- It was undecided how the browser gets the API token.

The owner asked for Tasks 6b–8 to run without stopping, using the recommended option at each open question. This ADR records those choices.

## Decision

- **Settings API (backend `modules/settings`).**
  - `GET/PATCH /settings` keep typed values (`language`, `theme`, `sources_email`) in the library's `setting` table. In a PATCH, `null` resets a field to its default.
  - `GET /secrets`, `PUT /secrets/{name}` and `DELETE /secrets/{name}` keep API keys (Semantic Scholar, OpenAlex) in the OS keyring through Python `keyring`, behind a `SecretStore` Protocol; tests use an in-memory store.
  - Values are never returned or logged; the UI only learns `configured: true|false`. A missing keyring is `secrets.unavailable` (503).
  - This resolves open question 2.
- **Language and theme are library settings, mirrored in localStorage.**
  - The server copy makes a choice survive restarts and behave the same in the browser and in Tauri, whose origins differ.
  - The localStorage copy lets the first paint use the right theme and language before the API answers.
  - `data-theme` on `<html>` switches every color variable; `color-scheme` follows it (ADR 0001, WebView2 rule).
- **Tokens:**
  - `pnpm gen:tokens` turns `docs/design/tokens.json` into `apps/web/src/styles/tokens.css`. CI fails when the file is stale (`pnpm check web`).
  - Tailwind v4 maps the variables to short utility names (`bg-canvas`, `text-fg-muted`, `rounded-md`, `text-ui`) in `styles/index.css`. Colors and sizes come only from tokens.
  - The dark set is still the draft from open question 10.
- **Fonts** (Inter, JetBrains Mono) are bundled from `@fontsource` (OFL-1.1). There is no font CDN, because network access is allowed only to the listed services.
- **Components:** shadcn/ui-style, written in the repo on `radix-ui` primitives with `cva`. So far: Button, Input, Segmented (a radio group), Tooltip.
- **Browser mode and the token.**
  - `tez serve` will print a link with `#api=…&token=…`. The fragment is never sent to a server; the UI moves it to sessionStorage and removes it from the address bar.
  - In development, `pnpm dev`'s Vite proxy forwards `/api` to the backend and adds the token from the development library's `.tez/instance.json`, so the token never reaches the page.
  - Elsewhere, without a token, the UI shows `backend.no_token`.
- **Hash routing** (`createHashRouter`) works the same from Tauri's asset protocol and from any static server, with no fallback configuration.
- **Job progress in the UI** (the rest of 6b's acceptance):
  - One `fetch`-based SSE reader follows `/jobs/events` (EventSource cannot send the Authorization header). It reconnects with `Last-Event-ID` and feeds a Zustand store.
  - The status bar shows "N jobs running · M failed", and `/jobs` lists the jobs.
- **Desktop sidecar (Rust, `src-tauri/src/backend.rs`):**
  - `setup()` starts the backend with `std::process` (no shell plugin). It writes a 256-bit token to stdin, reads `TEZ_READY` or `TEZ_ERROR` from stdout, and assigns the process to the Windows Job Object.
  - The UI calls `backend_status` and listens for `backend-status`, so either order of events works.
  - An exit that was not announced becomes `backend.exited`. On app exit, stdin is closed.
  - Debug builds run `uv run --project backend tez-backend` on `backend/.dev/TEz Library`, the same library as `pnpm dev`. Release builds run the bundled `tez-backend` on `Documents/TEz Library`. That default stays until the welcome screen lets the user choose (open question 1).
- **Phase 1 navigation:** Search, Library, Screening, Reader, Notes, Matrix, Jobs, Settings. The AI assistant is hidden (`docs/progress.md`, "Sonraya"). Sections whose tasks have not landed show a "coming soon" page.
- **Supply chain:** pnpm 12's `minimumReleaseAge` policy is respected. When `pnpm add` silently added exclusions for packages published hours earlier, the exclusions were removed and the previous releases pinned: tailwindcss 4.3.3, lucide-react 1.66.0, react-i18next 17.1.11.

## Consequences

- The Settings screen covers General, Search sources, Library and About. The other categories in design 5.11 arrive with their features.
- Running `pnpm dev` and `pnpm dev:desktop` at the same time opens the same development library twice. The second gets `library.locked`, shown translated.
- The production bundle is about 500 kB before code splitting. Code splitting comes when the reader (pdf.js) lands.
- `cargo test` now runs in `pnpm check rust` and CI.
