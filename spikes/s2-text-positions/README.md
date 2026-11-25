# S2 spike — does PDFium's text land where pdf.js's selection was?

Throwaway code for risk spike S2. Results and decisions: [`docs/adr/0030-text-positions.md`](../../docs/adr/0030-text-positions.md). Do not import anything from here into the main code base.

Needs `pdflatex` on the PATH (nothing is downloaded) and Playwright's Chromium:

```powershell
cd spikes/s2-text-positions
uv run --project ../../backend python scripts/make_pdfs.py   # samples into out/ (not committed)
node scripts/select.mjs                                      # random selections in pdf.js
uv run --project ../../backend python scripts/match.py       # finds them in PDFium; RESULTS.json
```
