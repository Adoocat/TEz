# 0037 — GROBID: optional, on this computer, read on request

- **Status:** Accepted
- **Date:** 2026-11-27
- **Tasks:** 56 (GROBID)

## Context

The plan makes GROBID an optional outside service (Docker or a lab server) that reads a paper's sections and reference list, with `document_section` and `reference_entry` in the data model. Phase 3 decided: GROBID only at a `localhost` address (rule 1). Acceptance: tests use a recorded response; without GROBID nothing breaks.

## Decision

- **An address in the settings turns it on** (`grobid_url`, Settings → Sources). Only `http(s)://localhost`, `127.0.0.1` or `[::1]` with a port is taken: the PDF is sent to it, so it must be on this computer. A lab server can be reached through an SSH tunnel to a local port. With no address, `GET /grobid` says so, the reader shows no Structure tab, and `POST /attachments/{id}/structure` answers `grobid.off`.
- **A reading is a worker job on request** (`grobid.read`, one attempt): the reader's Structure tab has "Read sections and references". It is not queued for every PDF, as GROBID takes up to a minute a paper and may not be running.
- **The adapter is a `Protocol`** (`structure/grobid.py`) with an `httpx2` implementation calling `/api/processFulltextDocument` with head and reference coordinates and raw citations, without consolidation (which would call Crossref from GROBID). Tests replace it with a recorded answer; nothing in the tests reaches the network.
- **What is kept:** each reading replaces the file's sections (body headings with their pages, the abstract first; type guessed from Turkish and English heading words) and references (title, authors, year, DOI, page, the raw text). A reference is matched to a library paper by DOI, else by its folded title (`match_score` 1 or 0.9). `structure_read` records when a file was read, or the error of the last try (`grobid.unreachable`, `grobid.failed`), which the reader shows instead of raising.
- **Not yet:** `citation_edge` from these references (Phase 4, citation graph), and using sections in search or the matrix.

## Consequences

- TEz installs and runs the same with or without GROBID.
- The test answer has GROBID 0.8's TEI shape but was written for the test, not recorded from a running GROBID; the first run against a real one may show differences to fix.
