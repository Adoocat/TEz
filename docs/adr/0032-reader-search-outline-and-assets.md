# 0032 — Reader: search, outline, page sizes, tabs and pdf.js's data files

- **Status:** Accepted
- **Date:** 2026-11-25
- **Task:** 45 (reader improvements). Adds to ADR 0015.

## Context

ADR 0015 left out search inside a document, the outline, different page sizes and pdf.js's data files. Design 4.5 also asks for document tabs and a focus mode. Spike S2 (ADR 0030) found the text layer misplaced on rotated pages.

## Decision

- **Search inside a document is answered by the backend** (`GET /attachments/{id}/find`), from the text Task 43 stored. The reader knows only the pages it has drawn; asking pdf.js would read the whole file through ranges. The answer is a count per page.
- **The marks are drawn with the CSS Custom Highlight API** over pdf.js's text layer. Nothing is added to the layer's DOM, which selections and anchors depend on. A webview without the API still jumps to the page, without marks.
- **Every page has its own size**, learned when it is drawn; until then it is assumed to be like page 1. `resizeItem` keeps the place when a page above turns out different.
- **Rotated pages:** pdf.js's `data-main-rotation` rules and its rounding variables (`--scale-round-x/y`) are in our CSS now. An end-to-end test checks that the text lies on the page at 0, 90 and 180 degrees.
- **Tabs** are remembered on this device with the page each was left at. A tab whose file is gone closes itself.
- **Focus mode** hides the shell and is not remembered; `F` turns it on, Escape off.
- **pdf.js's data files** (standard fonts, image decoders, character maps) are copied by a small Vite plugin instead of a new dependency. **The Liberation fonts are not**: they are GPL-2.0 with a font exception, which rule 6 does not allow. pdf.js then uses the system's Arial or Helvetica.

## Consequences

- A PDF that embeds no fonts, or holds JPEG 2000 or JBIG2 scans, now draws properly. The app grows by about 3 MB of files that load only when needed.
- On a Linux system without any Helvetica-like font, text in an unembedded Helvetica may draw in another font.
- The count per page comes from PDFium's text and the marks from pdf.js's; on a page where they differ (a formula, a word Skia writes in pieces) a match can be counted and not marked.
- Measured again on the 300-page PDF: p50 16 ms, p95 27 ms per scroll step, at most 3 canvases, JS heap unchanged at 40 MB.
- No new dependency.
