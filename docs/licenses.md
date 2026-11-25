# Third-party licenses

TEz is MIT-licensed. Every dependency that ships with the app has a licence compatible with that: there is no AGPL or GPL code (CLAUDE.md rule 6; PyMuPDF and Marker are excluded for that reason). This list covers the runtime dependencies as of Phase 1 (2026-11-11). Development-only tools (linters, test runners, Playwright) are not distributed and are left out. Each new dependency's licence is also noted in its pull request and ADR.

## Backend (Python, bundled with PyInstaller)

| Package | Version | Licence | Used for |
| --- | --- | --- | --- |
| alembic | 1.20 | MIT | database migrations |
| bibtexparser | 2.1 | MIT | BibTeX import |
| citeproc-py | 0.12 | BSD-2-Clause-Views | formatted bibliographies (CSL); bundles the CSL locale files (CC BY-SA 3.0) |
| fastapi | 0.162 | MIT | the API |
| hishel | 1.4 | BSD-3-Clause | HTTP cache |
| httpx2 | 2.16 | BSD-3-Clause | outbound HTTP |
| keyring | 25.7 | MIT | API keys in the OS keyring |
| lxml | 6.1 | BSD-3-Clause (bundles libxml2 and libxslt, MIT) | XML for citeproc-py and the CSL styles |
| pydantic, pydantic-settings | 2.14, 2.16 | MIT | schemas, configuration |
| pylatexenc | 2.11 | MIT | LaTeX in BibTeX to text |
| pypdfium2 | 5.15 | Apache-2.0 or BSD-3-Clause (PDFium: BSD-3-Clause, Apache-2.0) | PDF page count and text layer |
| rapidfuzz | 3.14 | MIT | fuzzy title matching |
| rispy | 0.10 | MIT | RIS import |
| sqlalchemy | 2.1 | MIT | database access |
| starlette | 1.10 | BSD-3-Clause | ASGI toolkit (FastAPI) |
| tenacity | 9.2 | Apache-2.0 | retries |
| typer | 0.29 | MIT (bundles Click, BSD-3-Clause) | the `tez` command |
| rich, shellingham | 15.0, 1.5 | MIT, ISC | Typer's output and shell detection |
| uvicorn | 0.54 | BSD-3-Clause | ASGI server |

**PyInstaller** builds the backend binary. It is GPL-2.0 with a bootloader exception, which explicitly allows distributing programs built with it under any licence. It is a build tool, not part of TEz's code (ADR 0001).

## Frontend (bundled into the web app)

| Package | Version | Licence |
| --- | --- | --- |
| react, react-dom | 19.3 | MIT |
| react-router | 8.5 | MIT |
| @tanstack/react-query, react-table, react-virtual | 5.105, 8.21, 3.14 | MIT |
| i18next, react-i18next | 26.7, 17.1 | MIT |
| radix-ui | 1.8 | MIT |
| zustand | 5.0 | MIT |
| openapi-fetch | 0.17 | MIT |
| pdfjs-dist | 6.5 | Apache-2.0 |
| @codemirror/state, view, commands, language, lang-markdown, autocomplete | 6.x | MIT |
| @lezer/highlight | 1.x | MIT |
| react-markdown, remark-gfm | 10.1, 4.0 | MIT |
| lucide-react | 1.66 | ISC |
| clsx, tailwind-merge | 2.1, 3.7 | MIT |
| class-variance-authority | 0.7 | Apache-2.0 |
| @tauri-apps/api | 2.12 | Apache-2.0 or MIT |
| @fontsource/inter, @fontsource/jetbrains-mono | 5.3 | SIL Open Font License 1.1 |

pdf.js's data files are copied into the app as they are (`apps/web/vite.config.ts`): the Foxit standard fonts (BSD-3-Clause), the OpenJPEG (BSD-2-Clause), JBIG2 (BSD-3-Clause) and qcms (MIT) decoders, Adobe's character maps (BSD-3-Clause) and a colour profile (CC0). The Liberation fonts in the same package are GPL-2.0 with a font exception and are **left out**; pdf.js falls back to the system's Arial or Helvetica.

The reader's text-layer CSS (`apps/web/src/styles/index.css`) is adapted from pdf.js's `web/pdf_viewer.css` (Apache-2.0).

## Desktop shell (Rust)

| Crate | Licence |
| --- | --- |
| tauri | Apache-2.0 or MIT |
| tauri-plugin-single-instance, tauri-plugin-deep-link | Apache-2.0 or MIT |
| serde, serde_json | Apache-2.0 or MIT |
| getrandom | Apache-2.0 or MIT |
| windows | Apache-2.0 or MIT |

## Bundled data

| Data | Source | Licence | Used for |
| --- | --- | --- | --- |
| NHLBI Study Quality Assessment Tools (six checklists, July 2021) | National Heart, Lung, and Blood Institute, <https://www.nhlbi.nih.gov/health-topics/study-quality-assessment-tools> | Public domain (U.S. Government work, 17 U.S.C. § 105) | quality assessment templates (Task 38, ADR 0026) |

| CSL styles: APA 7th edition, MLA 9th edition, Chicago 18th edition (author-date; notes and bibliography), NLM/Vancouver (citation-sequence), IEEE (`backend/src/tez/modules/export/styles/`) | Citation Style Language project, <https://github.com/citation-style-language/styles>; authors and contributors are named in each file's `<info>` | CC BY-SA 3.0 | formatted bibliographies (Task 39) |
| CSL locales tr-TR and en-US (shipped inside citeproc-py) | Citation Style Language project, <https://github.com/citation-style-language/locales> | CC BY-SA 3.0 | Turkish and English terms in bibliographies (Task 39) |

The CSL styles are bundled unchanged. At render time TEz adds a space after the citation number of numbered styles (`second-field-align`), in memory only. Any changed copy of a style is shared under CC BY-SA 3.0 too.

Checklists whose terms forbid commercial use or adaptation, or give no licence (Kitchenham's, JBI, RoB 2, CASP), are not bundled (ADR 0026).
