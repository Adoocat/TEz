# 0012 — Open-access PDFs: arXiv, then Unpaywall, then the source's link, in a job

- **Status:** Accepted
- **Date:** 2026-11-11
- **Task:** 17 (open-access PDF)

## Context

Task 17 finds and downloads free PDFs from Unpaywall and arXiv as a `processing_job`. Acceptance: *the download runs in the background and its progress shows in the UI.* A paper may have an arXiv id, a DOI, and an open-access link from the search source. Many "PDF" links turn out to be landing pages or login walls.

## Decision

- **One `pdf.fetch_open_access` job per paper,** run by the worker. The dedupe key is `oa:<paper id>`, so asking twice while it runs queues nothing more. `POST /pdfs/open-access` skips papers that already have a PDF and papers with nowhere to look (no DOI, arXiv id or link). It reports both counts. Asking for a paper's PDF keeps the paper in the library.
- **Candidate order:** arXiv (`arxiv.org/pdf/<id>`, always free). Next comes Unpaywall's best location and then its other locations (`url_for_pdf`). Last is `paper.oa_url` from the search. Unpaywall needs the e-mail address from Settings. Without one, Unpaywall is skipped, and if a DOI was the only way, the job ends with `source.email_required`.
- **Only a real PDF counts.** A candidate whose bytes lack the `%PDF-` header is skipped for the next one. The first PDF is stored exactly like a dropped file (Task 16, ADR 0011): stored by hash, a duplicate if already present, inspected by `pdf.inspect`, and `attachment.source` says where it came from.
- **Progress:** `HttpClient.download` streams the body and reports bytes against `Content-Length`. The job splits its progress across candidates, so the status bar and the Jobs screen move during a large download. Downloads are one attempt each and never cached. The job, not the request, is what gets retried.
- **Failures say why.** Handlers can raise `JobFailed(code, params, retry=…)`. The job's error is then that code instead of `job.handler_failed`. When no free copy exists (`pdf.no_open_access`), the job fails at once: retrying would not change the answer. A timeout, a network error or a 5xx counts as one failed attempt and is retried with back-off.
- **The answer from Unpaywall is cached for a day** in `.tez/http-cache.sqlite`, the opt-in cache from ADR 0007. Downloads are not cached.
- **Tests do not touch the network.** `HttpClient` takes an optional `transport`, and the tests use `httpx2.MockTransport`. The Unpaywall answers in the tests follow the documented v2 schema. No real response was recorded, because recording would mean sending a real e-mail address. The first real use should confirm the schema.

## Consequences

- Rate policies are in code: Unpaywall at 5 requests a second, arXiv at one every three seconds, other hosts at one a second. Making them configurable is the open item from Task 11.
- Publisher pages behind JavaScript or cookies are not followed. Such a paper ends with `pdf.no_open_access` and the user adds the PDF by hand.
- The PyInstaller build must include the HTTP cache path (hishel/anysqlite). This was noted under Task 13 and is now exercised by Unpaywall lookups.
