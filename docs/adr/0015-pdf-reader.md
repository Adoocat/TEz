# 0015 — PDF reader: pdf.js over HTTP ranges, virtualized pages, a text layer

- **Status:** Accepted
- **Date:** 2026-11-11
- **Task:** 20 (PDF viewer)

## Context

Task 20 covers pdfjs-dist with the PDF streamed from the backend over HTTP Range, virtualized pages, zoom, a text layer, and `?page=` deep links. Acceptance: *memory and scrolling are acceptable on a 300-page PDF.* The S1 spike measured pdf.js at 170 MB idle, rising to about 410 MB after scrolling 300 pages, with every page kept.

## Decision

- **`GET /attachments/{id}/file`** serves the stored file through Starlette's `FileResponse`, which answers `Range` with 206 and `Content-Range`. The response is `inline` with an `immutable` cache header, which is safe because the file name is its hash. The token goes in the `Authorization` header, which pdf.js sends with every range request. CORS already exposes `Accept-Ranges` and `Content-Range` (Task 3). Successful range requests are logged at DEBUG, because a page turn makes dozens of them (an open item from Task 3).
- **pdf.js is loaded on first use** (`lib/pdf.ts`, dynamic `import()`). The ~440 kB library and the worker are not in the start-up bundle. `lib/pdf.ts` is also the only place that touches the pdf.js API, so component tests replace it with a fake.
- **Ranges only:** `disableAutoFetch` and `disableStream` are on, with 256 kB chunks. pdf.js fetches what the shown pages need and nothing in the background.
- **Pages are virtualized.** Only the pages on screen, plus two either side, have a canvas. A page leaving the window cancels its render and calls `page.cleanup()`. Every page is sized from page 1 at the current zoom, since papers rarely mix page sizes. Canvases are drawn at the device pixel ratio.
- **The text layer** is pdf.js's `TextLayer`. Its CSS rules are copied into `styles/index.css`, reduced from pdf.js's `pdf_viewer.css` (Apache-2.0), with the selection colour taken from our tokens. Pages keep `color-scheme: light` in the dark theme, because a page is paper.
- **Zoom:** fit width by default, plus fixed steps from 50% to 300%. **Deep link:** `#/reader/<attachment>?page=N` opens at page N, and the address follows the page being read (replace, debounced), so a reload or a copied link keeps the place.
- **Ways in:** "Open PDF" in the library inspector, file names in its Files tab, and dropping a single PDF on the window (design 4.6). Several files dropped at once only go to the inbox.

## Consequences

- Measured in headless Chromium on a 300-page, 6.1 MB PDF (Playwright, `e2e/reader.spec.ts`, development build with React StrictMode): opening at page 150 read 1.7 MB in ranges, and scrolling all 300 pages read 6.7 MB. At most 3 canvases were in the DOM. The JS heap stayed at 35 MB before and after the full scroll. A scroll step of 900 px took 18 ms at p50, 34 ms at p95 and 99 ms at most. Real WebView2 numbers are still to be taken (see S1).
- How well ranges work depends on the file. pdf.js checks the last page when it opens, so it reads every node of the page tree. A tree written in one place (LaTeX, Word) costs a few chunks. A file with its tree scattered across it is read nearly whole, in ranges. The e2e test PDF writes its tree like real producers.
- Not built yet: search inside the document, highlights, the outline and thumbnails sidebar, rotation, and different page sizes in one file (pages are sized from page 1). Standard-font data and the wasm decoders (`standardFontDataUrl`, `wasmUrl`) are not configured, so a PDF that relies on unembedded standard fonts or JPEG 2000 images may draw with fallbacks.
- New dependency: `pdfjs-dist` 6.5 (Apache-2.0).
