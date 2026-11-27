# 0036 — Figures and tables: an area the user marks, its picture, and its place

- **Status:** Accepted
- **Date:** 2026-11-27
- **Tasks:** 55 (figure and table gallery)

## Context

The plan has `extracted_asset` (attachment, kind table/figure, label, caption, page, box, anchor, picture file, `data_json`, extractor and its version) and design 5.5 a gallery with side-by-side comparison and export that carries the source. Phase 3 decided against Docling and OCR: figures and tables come from an area the user selects. Acceptance: from an item back to its place in the PDF.

## Decision

- **The user marks the area** with a reader tool ("Keep a figure or table") and says whether it is a figure or a table, its label as the paper has it ("Şekil 3") and its caption. `extractor` is `manual`, version `1`; `data_json` stays empty until a table extractor exists.
- **The place is an area anchor** (ADR 0033), made with the asset. The gallery opens the reader with `?anchor=`; a lost anchor is shown as such. Deleting an asset keeps its anchor.
- **The picture is what the reader drew**, cut from the page canvas at the current zoom and pixel ratio, and sent as a PNG. The backend checks the PNG signature and a 10 MB limit and keeps it at `derived/<attachment>/assets/<asset>.png`. Rendering in the worker with PDFium would give a sharper picture at any zoom but needs a job and a wait; it can replace this without a schema change.
- **Pictures are fetched with the token** (an `<img>` cannot send it) and shown from a blob address made once per picture.
- **Export is one HTML page** with the chosen pictures embedded and each one's label, caption and source ("Kim et al. 2024, p. 7"): it opens anywhere and pastes into Word with its captions.

## Consequences

- No new dependency, and no work in the worker.
- A picture taken at low zoom is small; the user can zoom in before marking.
