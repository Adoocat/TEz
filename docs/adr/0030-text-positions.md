# 0030 — Text positions: pdf.js selections found in PDFium's text

- **Status:** Accepted
- **Date:** 2026-11-25
- **Task:** S2 (Phase 3 risk spike)

## Context

Phase 3 rests on one assumption: a passage selected in the reader (pdf.js) can be found again in the text the worker extracts (PDFium), in the same place. Highlights, matrix evidence and, later, AI quotes all need it. The two engines decide on their own where lines break, how ligatures and accents come out and what a line-end hyphen is. Acceptance: at least 95% of selections land in the right place.

The spike (`spikes/s2-text-positions`) made 1030 random selections in pdf.js's text layer on 13 generated PDFs: pdfLaTeX one and two columns (T1 and OT1), Chromium's PDF writer with automatic hyphenation, Turkish, pages rotated by 90, 180 and 270 degrees, and pages with a crop box. A selection counts as right when at least 90% of the characters PDFium matched lie inside the boxes pdf.js drew.

## Result

**1019 of 1030 (98.9%)**; every LaTeX file 100%, Chromium's 95–98%. Looking one selection up takes under 1 ms. All 11 misses are the same word: Skia draws `İ` as two glyphs, pdf.js reads a NUL after the `I`, and PDFium repeats a piece of the word. They were short selections (under 25 letters) found by the fuzzy step at too loose a score.

## Decision

- **Compare keys, not text.** The key of a text is its letters and digits only, folded with `shared/text.fold`, with the index each came from. Whitespace, hyphens, line breaks, quotes, ligatures and accents stop mattering, and a match maps back to exact characters and boxes.
- **One character per PDFium character.** Text is read with `FPDFText_GetUnicode` per character index, not `get_text_range`, whose string can be shorter or longer than the boxes.
- **Read pages unrotated.** PDFium orders text by the displayed page: a page rotated by 180 degrees came out with its lines scrambled (0 of 43 found). `set_rotation(0)` before reading fixes it. Boxes are in PDF user space, unrotated, which is also what pdf.js's `convertToPdfPoint` returns, so stored coordinates need no conversion.
- **Exact first, then close.** When the key is not found, `rapidfuzz`'s partial alignment gives the closest passage. It needs a minimum length and a score, and anything short must match exactly: a wrong place is worse than "not found" (rule 2).
- **The reader's boxes choose between repeats.** A sentence can occur more than once on a page; the occurrence that overlaps the selection wins. Without boxes, the stored prefix and suffix choose.
- **Known ligature codes are repaired on extraction.** A font without a Unicode map gives raw T1 codes (`0x19` ı, `0x1B`–`0x1F` ff, fi, fl, ffi, ffl). They are never valid text, so they are mapped; otherwise search would miss every such word.

## Consequences

- The text layer on rotated pages was misplaced in the app: pdf.js's `data-main-rotation` rules and the `--scale-round-*` variables were missing from our reduced CSS. Task 45 adds them, with a test.
- Text inside a crop box's cut-off margin exists in PDFium but not in pdf.js. The fuzzy step absorbs it.
- Not measured: scanned PDFs (no text), vertical scripts and right-to-left text. Real publisher PDFs were not downloaded for the spike; Task 57 tries some by hand.
