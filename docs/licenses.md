# Third-party licenses

TEz is MIT-licensed. Every dependency that ships with the app has a licence compatible with that: there is no AGPL or GPL code (CLAUDE.md rule 6; PyMuPDF and Marker are excluded for that reason). This list covers the runtime dependencies as of Phase 1 (2026-11-11). Development-only tools (linters, test runners, Playwright) are not distributed and are left out. Each new dependency's licence is also noted in its pull request and ADR.

## Backend (Python, bundled with PyInstaller)

| Package | Version | Licence | Used for |
| --- | --- | --- | --- |
| alembic | 1.20 | MIT | database migrations |
| bibtexparser | 2.1 | MIT | BibTeX import |
| fastapi | 0.162 | MIT | the API |
| hishel | 1.4 | BSD-3-Clause | HTTP cache |
| httpx2 | 2.16 | BSD-3-Clause | outbound HTTP |
| keyring | 25.7 | MIT | API keys in the OS keyring |
| pydantic, pydantic-settings | 2.14, 2.16 | MIT | schemas, configuration |
| pylatexenc | 2.11 | MIT | LaTeX in BibTeX to text |
| pypdfium2 | 5.15 | Apache-2.0 or BSD-3-Clause (PDFium: BSD-3-Clause, Apache-2.0) | PDF page count and text layer |
| rapidfuzz | 3.14 | MIT | fuzzy title matching |
| rispy | 0.10 | MIT | RIS import |
| sqlalchemy | 2.1 | MIT | database access |
| starlette | 1.10 | BSD-3-Clause | ASGI toolkit (FastAPI) |
| tenacity | 9.2 | Apache-2.0 | retries |
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
| lucide-react | 1.66 | ISC |
| clsx, tailwind-merge | 2.1, 3.7 | MIT |
| class-variance-authority | 0.7 | Apache-2.0 |
| @tauri-apps/api | 2.12 | Apache-2.0 or MIT |
| @fontsource/inter, @fontsource/jetbrains-mono | 5.3 | SIL Open Font License 1.1 |

The reader's text-layer CSS (`apps/web/src/styles/index.css`) is adapted from pdf.js's `web/pdf_viewer.css` (Apache-2.0).

## Desktop shell (Rust)

| Crate | Licence |
| --- | --- |
| tauri | Apache-2.0 or MIT |
| tauri-plugin-single-instance, tauri-plugin-deep-link | Apache-2.0 or MIT |
| serde, serde_json | Apache-2.0 or MIT |
| getrandom | Apache-2.0 or MIT |
| windows | Apache-2.0 or MIT |
