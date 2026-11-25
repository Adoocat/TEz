# 0031 — Full-text search: one chunk per page, a contentless index

- **Status:** Accepted
- **Date:** 2026-11-25
- **Tasks:** 43 (text extraction), 44 (full-text search)

## Context

The plan has `text_chunk` (a piece of a PDF's text) with FTS5 `chunk_fts` on top. Acceptance for the search: Turkish letters fold both ways, under 200 ms in 2000 papers, and a result opens the right page. 2000 papers of 12 pages are 24 000 pages and about 100 MB of text.

## Decision

- **A chunk is a page.** A page is what a result names and what the reader opens. "Every word must match" means on one page. Smaller chunks for embeddings (Phase 5) can be added later; `char_start` and `char_end` already allow them.
- **The stored text is PDFium's, character by character** (ADR 0030), so any position has a box. Text for reading and indexing is derived (`readable`, `index_text`).
- **The index is contentless** (`content=''`, `contentless_delete=1`), because an ordinary FTS5 table would keep a second, folded copy of every page. `text_chunk.search_row` is the rowid; a trigger removes a page from the index when its row goes, also through a foreign-key cascade. Contentless-delete tables need SQLite 3.43; the bundled Python has 3.53.
- **A word broken over two lines is indexed joined and in halves.** The PDF does not say whether "cost-⏎benefit" is one word or two.
- **Passages are made in Python**, from the stored text, only for the pages shown. FTS5's own `snippet()` needs content, and would show folded text.
- **A covering index** `(search_row, attachment_id, page_index)` keeps the join from reading rows with their text: 121 → 42 ms for a word on every page.
- **The list being looked at decides where to search.** The screen sends the ids its scope and filters leave, so filters mean the same thing in both search modes. At most the 2000 best pages are considered, and the result says when that cut it (`truncated`).

## Consequences

- Measured on 24 000 pages (best of five, API round trip): a rare word 9 ms, a phrase 87 ms, a word on every page 104 ms, three common words 116 ms.
- The library file grows by about the size of the text plus its index (115 MB for that test library).
- Words must be on the same page; a sentence that continues on the next page is found by either half.
- No new dependency.
