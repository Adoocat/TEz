# 0014 — Library list: FTS5 metadata search folded in the app, citation keys, a virtualized table

- **Status:** Accepted
- **Date:** 2026-11-11
- **Task:** 19 (library list)

## Context

Task 19 covers a virtualized table with sorting, filters and a detail panel, plus metadata full-text search. Acceptance: *a search in a 2000-paper demo library takes under 100 ms.* SQLite's FTS5 `unicode61` tokenizer folds Turkish wrongly: `I` is not `ı`, and `İ` is not `i` (plan, data model). Open question 6 asked where `paper_fts` belongs, and the answer was here, with its own migration. The citation-key column has been empty since Task 6.

## Decision

- **`paper_fts` is an FTS5 table of already-folded text** *(migration 0007)*. It has the columns title, authors, abstract, venue and extra (identifiers, citation key, year), and the paper id is unindexed. The text goes through `tez.shared.text.fold`, the same fold used for `title_norm`, and queries are folded the same way. So `isik`, `ışık` and `IŞIK` all find "Işık".
- **The index is kept in step by an ORM `after_flush` listener.** Any flush that writes a paper, its authors or its identifiers rewrites that paper's rows in the same transaction, so the index cannot hold something that was rolled back. Bulk SQL that bypasses the ORM also bypasses the index. Nothing does that today; emptying the trash later must use the ORM, or reindex.
- **The index repairs itself when a library opens.** If it does not cover exactly the papers there are, it is rebuilt. That happens on the first open after migration 0007, and for a copied or restored library. The rebuild takes well under a second for 2000 papers. The migration does not fill it, because migrations do not import app code.
- **Query:** every word must match, as a word or a prefix (`"word"*`), so FTS syntax typed by the user cannot break the query. Ranking is bm25 with title and authors weighted highest. `GET /papers/search` returns the ids, best first, and the time taken. The list filters its already-loaded rows by those ids, so the table stays one source.
- **Filters and sorting run in the browser** over the loaded rows: year range, reading status, tag, and whether there is a PDF. A library of a few thousand papers fits, and both are instant. The table uses TanStack Table **v8** (v9 changed its API). Rows are virtualized at a fixed height, and one scroller handles both axes, so a narrow window scrolls the columns instead of pushing the inspector away. The shell grid now has `grid-cols-[minmax(0,1fr)]` for the same reason.
- **Citation keys are made when a paper enters the library**, in the form `yilmaz2024automated`: ASCII family name, year, first meaningful title word, plus a letter on a clash. The app never changes a key afterwards, because a thesis may cite it. The user can edit it (`PATCH /papers/{id}`), and the new key must be BibTeX-safe and unused. Papers kept before this task get keys when the library opens.
- **The inspector** (design 4.4) shows warnings for retraction and for a published version that exists, then the title and citation, reading status and tags, identifiers with copy buttons, the citation key, and tabs for the abstract and the files with their state.
- **A demo library** (`python -m tez.devtools.demo <folder> --papers 2000`) is made from fixed word lists and a fixed seed, with fictional names and DOIs under the 10.5555 test prefix.

## Consequences

- Measured on the 2000-paper demo: the server answers in about 1–2 ms, and a browser round trip takes about 5 ms (median) and 13 ms at most. The acceptance test also runs on CI, through the API.
- Building the demo library takes about 20 seconds. Each paper is flushed on its own and indexed in the same step.
- Columns cannot be hidden or reordered yet, and the card, timeline and citation-graph views (design 4.3) are not built.
- New dependency: `@tanstack/react-table` 8.21 (MIT).
