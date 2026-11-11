# 0011 — Adding PDFs: store by hash in the API, open only in the worker

- **Status:** Accepted
- **Date:** 2026-11-11
- **Task:** 16 (adding PDFs)

## Context

Task 16 adds PDFs by drag and drop: sha256, a copy in the library folder, and the page count with pypdfium2. Acceptance: *the same PDF is not added twice; a broken PDF is marked and the app does not crash.* PDFium is native code, and the plan runs native work in a separate worker process so that a crash takes down only the worker.

## Decision

- **The API never opens a PDF.** It checks the `%PDF-` header in the first kilobyte, hashes the bytes, writes `files/<2 hex>/<sha256>.pdf` atomically (a temporary file, then a rename), and records the `attachment`. It then queues a `pdf.inspect` job. The worker opens the file, counts its pages and looks for a text layer on the first three pages. The result is `ok`, or `needs_ocr` for a scan. A file PDFium cannot read is `failed` with `pdf.unreadable`. The job still ends `done`, because a broken file is an answer, not something to retry.
- **A file that crashes the worker is marked on its last attempt.** Before PDFium opens the file on the last attempt, the handler marks the attachment `failed` with `pdf.crashed`. If the process dies, that mark stays and the job is not retried again. If the file opens, the real result replaces the mark. `JobContext` now carries the database, the attempt number and the maximum number of attempts, so handlers can do this.
- **Duplicates are decided by content.** The same bytes under another name return `duplicate` with the existing paper. Nothing is copied or created. The unique `sha256` column covers a race between two uploads.
- **A PDF without a paper becomes a new paper in the inbox.** The inbox is a system collection (`is_system`, name `inbox`), created the first time a file needs it. The new paper is kept in the library (`library_added_at`), and its title comes from the file name until metadata is known. With `paper_id`, the file is attached to an existing paper instead.
- **Upload is the raw body** (`POST /pdfs?file_name=…`, `application/pdf`). Base64 would add a third to large scans. The limit is 300 MB. `POST /pdfs/from-paths` takes paths on this computer, for `tez <file.pdf>` (Task 22) and the CLI. Each path succeeds or fails on its own.
- **Drop target:** the whole window. The desktop window turns off Tauri's native file drop (`dragDropEnabled: false`), so WebView2 hands the page the same HTML5 `File` objects a browser does, and there is one code path.
- **`attachment.file_name` and `attachment.size`** *(addition to the plan's data model; migration 0006)* keep the user's name for the file, which the hash replaces on disk.

## Consequences

- Reading a PDF's DOI and fetching its metadata (design 4.6, "DOI bulundu…") is not part of this task; the paper keeps its file-name title until then.
- Text extraction (`text_chunk`) is Phase 3. `ok` here means only that a text layer exists.
- Opening a dropped PDF in the reader comes with Task 20.
- New dependency: `pypdfium2` 5.15 (Apache-2.0 or BSD-3-Clause; PDFium binaries BSD-3-Clause and Apache-2.0).
