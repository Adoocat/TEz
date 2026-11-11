# 0013 — Collections, tags and reading status; Playwright end-to-end tests

- **Status:** Accepted
- **Date:** 2026-11-11
- **Task:** 18 (collections and tags)

## Context

Task 18 covers the collection tree (create, rename, move, delete), drag and drop, a paper in several collections, tags, and reading status. Acceptance: *integration tests and an E2E flow.* Playwright had been a placeholder since Task 1, so the E2E flow needed it set up. The library list itself is Task 19, but dragging papers needs a list to drag from.

## Decision

- **Collections point at papers; they never own them.** Deleting a collection deletes its sub-collections and memberships (`ON DELETE CASCADE`), never a paper. Moving a collection under itself or a descendant is `collection.cycle` (409). Sibling names are unique after Turkish-aware folding (`Işık` = `ışık`).
- **The inbox is a system collection** (Task 16). It cannot be renamed, moved or deleted (`collection.system`), and the UI names it from its own strings.
- **Filing a paper keeps it.** A search candidate dropped on a collection is put in the library (`library_added_at`), because the library list shows only kept papers. Tags and reading status change only the papers given.
- **Counts are derived per request** from the membership tables and leave out trashed and unkept papers.
- **Tag colours are token names** (`yellow`, `green`, `blue`, `pink`, `purple` → `--color-highlight-*`), checked by a pattern, so no raw colour reaches the UI. New tags take the next colour, and a tag's colour button cycles through them.
- **Drag and drop uses custom data types** (`application/x-tez-papers`, `application/x-tez-collection`), so a file dragged in from the desktop (Task 16) is never mistaken for papers. Dragging a checked row drags the whole selection. A collection dropped on another moves inside it, and dropped on the "Collections" heading it moves to the top.
- **The library page has a simple list** (title, reading status, tags, first author, year) and a bulk bar for reading status, adding a tag and leaving the current collection. Task 19 replaces the list with the full virtualized table.
- **End-to-end tests run in web mode** (`pnpm e2e`). Playwright's global setup starts `tez-backend serve` on a fresh temporary library on port 8799, with CORS opened for the test origin. Vite serves the app on 1431, and the tests open it with the address and token in the URL fragment, as `tez serve` does. Tests seed papers through the import API. CI has an `e2e` job.

## Consequences

- Sibling order is alphabetical. `sort_order` exists, but nothing reorders collections by hand yet.
- Smart collections (design 4.3) are not part of this task.
- New development dependency: `@playwright/test` 1.65 (Apache-2.0). Chromium for the tests is downloaded by `playwright install`.
