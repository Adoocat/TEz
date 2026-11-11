# 0017 — One instance; files, folders and `tez://` links handed to it through a queue

- **Status:** Accepted
- **Date:** 2026-11-11
- **Task:** 22 (single instance and argument forwarding)

## Context

Task 22 covers Tauri's single-instance and deep-link plugins, forwarding `tez`, `tez <pdf>`, `tez <folder>` and `tez://` to the running window, and the `.tez/instance.json` discovery file (that file exists since Task 5). Acceptance: *the same command gives the same result whether the app is open or closed, and no second window opens.* Open question 8 asked how much `tez <folder>` and a `.bib` file should do in Phase 1. The owner chose to keep it simple.

## Decision

- **Single instance comes first.** `tauri-plugin-single-instance` (with its `deep-link` feature) is the first plugin registered. A second launch hands its arguments and working directory to the running instance and exits. The running window is unminimized, shown and focused.
- **Arguments are classified in Rust** (`src-tauri/src/open.rs`), where paths can still be resolved against the caller's working directory:
  - no arguments → `focus`;
  - `tez:…` → `link`;
  - a folder → `folder`, either marked as a TEz library or with its PDFs (up to 4 levels deep and 500 PDFs);
  - `.pdf` → `pdf`;
  - `.bib`, `.bibtex`, `.ris` → `import`;
  - anything else → `unsupported`, or `missing` if it does not exist.

  Options (`-…`) are ignored.
- **One road for "closed" and "open".** Requests always go into a queue (`OpenQueue`). The window is only nudged with an `open-requests` event and takes them with the `take_open_requests` command. At start-up the UI takes what its own launch put in the queue. Later launches put theirs there too. So a command ends the same way in both cases, and no request is handled twice. A taken request is always handled, even if the subscription was undone in the meantime. React StrictMode subscribes twice on start-up, and dropping a taken request lost it.
- **What each request does** (owner's decision on open question 8):
  - One PDF goes to the inbox through `POST /pdfs/from-paths` and opens in the reader. If it is already there, the existing copy opens and nothing is copied.
  - Several PDFs, or a folder of them, go to the inbox with one summary notice. There is no preview dialog.
  - A `.bib` or `.ris` file opens the import dialog on the search screen. The backend reads the file by path (`ImportFile.path`).
  - A TEz library folder only shows a notice. Switching libraries waits for the library picker (open question 1).
- **`tez://` links only navigate** (plan, "Güvenlik"): `tez://reader/<attachment>?page=N`, `tez://paper/<id>`, `tez://library`, `tez://search`, `tez://jobs`. Anything else shows "unknown link". On macOS links arrive as plugin events, and they go through the same queue.
- **The scheme is declared, not registered.** `tauri.conf.json` names the `tez` scheme. Registering it with the OS (registry on Windows) is the installer's job in Phase 6, so a development run never writes to the registry.

## Consequences

- Checked with the debug build on Windows:
  - With the app open, `tez-desktop.exe <file.pdf>` exited in 150 ms, one process remained, and the PDF was added and inspected by the running app.
  - With the app closed, the same command opened the app, which added and inspected the PDF within about 5 s.
  - A bare second launch exited and left one process.
- The `tez` command on the PATH, "Open with TEz" and file associations come with the installer (Phase 6). The headless CLI is Task 23.
- New dependencies: `tauri-plugin-single-instance` 2.5 and `tauri-plugin-deep-link` 2.6 (both Apache-2.0 or MIT).
