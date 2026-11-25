# 0033 — Anchors: verified quotes, and looking them up again when a PDF changes

- **Status:** Accepted
- **Date:** 2026-11-25
- **Task:** 46

## Context

Everything taken from a PDF must point at an anchor (CLAUDE.md rule 2). The plan's table has the page, boxes, the quote with what stands before and after it, and a character range. Acceptance: when the PDF changes the quote is found again; when it cannot be, it is marked lost and never sent to a wrong place. The app had no way for a PDF to change.

## Decision

- **The API checks a selection without opening the PDF.** The reader sends boxes (pdf.js, PDF user space), the quote, its surroundings and which of the identical passages it is. The quote is looked for in the stored text (ADR 0030, 0031); when found, the anchor keeps **the file's own words**, not the reader's, and is `verified`. When not (text not read yet, or read differently), it is `unverified` and checked again after the next reading. This replaces "the reader's boxes choose between repeats" in ADR 0030: boxes would need PDFium in the API process.
- **`file_sha256`** says which file the coordinates belong to. While it differs from the attachment's, the anchor is shown as `checking`, whatever its stored state.
- **A file can be replaced** (`PUT /attachments/{id}/file`, "Replace with another version…" in the inspector). The attachment keeps its id, so everything that points at it stays. The old file stays on disk. The file is no longer served as immutable.
- **The text job looks the anchors up in the new text** and takes boxes from PDFium, in the worker. The rules (`shared/passages.py`): a single exact match of at least 20 letters, or one whose surroundings are at least 60% alike; among repeats the clearly most alike, then the one on its old page; an approximate match only for passages of 24 letters or more, above 90 and clearly the best. Anything else is `lost`. A lost anchor keeps its quote and page, and is found again if the old file comes back.
- **Areas** (figures, tables, scans) cannot be looked up: they are lost when the file changes.
- **The same passage twice is the same anchor**, so a note and a matrix cell that quote one sentence share it.
- **`attachment_id` is RESTRICT:** evidence does not disappear because a file was removed.
- `?anchor=<id>` opens the reader at the place and shows it for two seconds. For a lost anchor the reader shows the quote and stays where it is.

## Consequences

- Looking up is deliberately shy: a short quote that moved without its surroundings is lost rather than guessed. The user can select it again.
- Replaced files pile up in `files/`; emptying them belongs with the trash (Task 16 note).
- A selection over a page break becomes an anchor on the page it starts on (Task 47).
