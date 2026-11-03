# 0001 — Desktop shell, Python sidecar and `tez` launcher

- **Status:** Accepted
- **Date:** 2026-11-03
- **Task:** S1 (risk spike), code in `spikes/s1-tauri-sidecar/` (throwaway)

## Context

TEz is a Tauri v2 desktop app whose backend is a Python (FastAPI) process. `docs/plan.md` assumes that:

1. Tauri can start a PyInstaller-packaged backend as a sidecar with a random port and a one-time token, and the backend dies with the app;
2. a second launch (`TEz.exe paper.pdf`, `tez://…`) is forwarded to the running window instead of opening a new one;
3. a separate console program `tez` can print to PowerShell and forward window commands;
4. pdf.js in WebView2 can show a 300-page PDF with acceptable memory and scrolling.

If any of these failed, the architecture had to change before Phase 1. The spike tested all four on the target OS (Windows 11, x64) with a real NSIS installer, installed silently, exercised and uninstalled by `scripts/measure.py`.

## What was built

| Part | Implementation |
| --- | --- |
| Backend | `tez-backend serve \| worker \| cli` — one PyInstaller **onedir** binary. `serve` reads the token from stdin, binds `127.0.0.1:0`, calls `listen()`, prints `TEZ_READY {"port": N}`, starts a `worker` child. Both exit on stdin EOF. Token-less requests get 401. |
| Shell | Tauri 2.12 (Rust). Spawns the sidecar via `tauri-plugin-shell` from Rust (no shell permission is exposed to JavaScript), writes the token to its stdin, reads the port from stdout, assigns the process to a **Windows Job Object** with `KILL_ON_JOB_CLOSE`. |
| Single instance | `tauri-plugin-single-instance` (feature `deep-link`, registered first) + `tauri-plugin-deep-link` (scheme `tez`). |
| `tez` | ~220 KB Rust console program at `<install>/bin/tez.exe`. Window commands → canonical absolute paths → `TEz.exe <args>` (detached). Headless commands → `tez-backend cli …` with inherited stdio. |
| PDF | pdfjs-dist 6.5, PDF streamed from the backend over HTTP Range with the token header; virtualized pages (canvas + text layer only within ±1500 px of the viewport). |

## Measurements

Windows 11 Home 26200, release build, NSIS per-user install. Raw data: `spikes/s1-tauri-sidecar/RESULTS.json`, `BUILD.json`.

| Metric | Value |
| --- | --- |
| PyInstaller onedir (FastAPI + uvicorn) | **30.3 MB** (exe 6.3 MB + `_internal/`) |
| `TEz.exe` (Tauri, release) | 11.6 MB |
| NSIS installer | **15.2 MB** |
| Installed size | 42.2 MB |
| Silent install | 2.5 s |
| Launch → Rust `main` | ~600 ms (see open risks) |
| Rust `main` → window painted | ~500 ms |
| Rust `main` → sidecar spawned | 330 ms (after plugin/runtime init) |
| Sidecar spawn → `TEZ_READY` | ~720 ms |
| Rust `main` → first `/health` 200 from the UI | **~1.08 s** (≈ 1.7 s from double-click) |
| Forced kill of `TEz.exe` → backend + worker gone | **~690 ms** |
| `tez --help` (Rust only) | **16 ms** median |
| `tez hello` (→ PyInstaller backend cold start) | **339 ms** median |
| pdf.js, 300 pages: open → first page painted | 115 ms (doc open 64 ms) |
| Scroll 80 pages at 3000 px/s | 160 fps avg, p95 frame 6.4 ms, 1 frame > 50 ms |
| Page render (canvas + text layer) | avg 34 ms, p95 81 ms |
| Jump to page 150 / 300 / 1 | 117 / 87 / 52 ms |
| Pages alive in DOM (max) | 5 |
| WebView2 memory, idle (no PDF) | 333 MB working set / 170 MB private (6 processes) |
| WebView2 memory after the 300-page benchmark | 600 MB working set / 411 MB private; JS heap 5 MB |
| Backend memory (serve + worker) | 95 MB working set |

## Verification

All 13 checks in `measure.py` pass on the installed package:

1. Sidecar starts with random port + token; `/health` 200 with token, 401 without; job assignment succeeds.
2. `TEz.exe <pdf>` while running → args (absolute path) arrive in the running window; no second process remains.
3. `tez --help` and `tez hello` print in the console (UTF-8 verified byte-wise); `tez <relative.pdf>` is forwarded as an absolute path; a missing path prints *what happened + what to do* and exits 1.
4. `tez://open?citekey=demo2024&page=4` (via the OS protocol handler) reaches the running window with all parameters.
5. pdf.js 300-page self-test completes.
6. Graceful close (WM_CLOSE): backend and worker exit.
7. Forced kill (`taskkill /F`): backend and worker exit (job object).

The uninstaller removes the binaries.

## Decision

Keep the planned architecture. Specifically:

1. **Tauri v2 + PyInstaller onedir sidecar.** `bundle.externalBin` ships `tez-backend.exe`; the onedir `_internal/` folder ships via `bundle.resources` mapped to `_internal/` (it lands next to the exe in both `tauri dev`/`target` and the installed layout). Onefile is not used (slower start, extra bootloader process).
2. **The sidecar picks its port** (`127.0.0.1:0`) and announces it on stdout *after* `listen()`. *Deviation from plan (approved):* the plan had Tauri pick a free port, which is racy (TOCTOU).
3. **The token goes over stdin**, never argv or env (not visible in the process list).
4. **Process lifetime = Windows Job Object (`KILL_ON_JOB_CLOSE`) + stdin-EOF watchdog in Python.** *Deviation from plan (approved):* the plan relied on Tauri killing the sidecar on exit. `tauri-plugin-shell` only kills children on `RunEvent::Exit`, only those spawned from JavaScript, and never grandchildren (our worker); a crash or Task Manager kill would leave orphans. On macOS/Linux (Phase 6) the stdin-EOF watchdog is the equivalent; add `PR_SET_PDEATHSIG` on Linux.
5. **`tez` is a small Rust console program installed in `<install>/bin/`**, the folder added to PATH. It cannot live next to `TEz.exe`: `tez.exe` and `TEz.exe` collide on the case-insensitive Windows file system (same reason VS Code uses `bin/code.cmd`). Window commands never start Python, so they are instant; headless commands pay the ~340 ms backend cold start, within the plan's < 1 s target.
6. **Single-instance must be registered first, with the `deep-link` feature**; on Windows a `tez://` link arrives as argv of a new process and is forwarded. Debug builds call `register_all()` so links work without installing. URLs arrive normalized (`tez://open/?…`), so parse them with a URL parser, never string matching.
7. **pdf.js with page virtualization is acceptable in WebView2.** Keep at most a handful of rendered pages; tear down canvases (`width = 0`) off screen.
8. **NSIS, per-user install** (no admin prompt). MSI is not used: it needs VBSCRIPT, which Windows is deprecating.
9. **Tauri 2.x stable**, not the 3.0 alphas now on crates.io.

## Consequences and rules for Phase 1

- The backend must call `listen()` before announcing readiness. Without it the UI's first request was refused ("Failed to fetch") — the spike hit this bug.
- CORS middleware must be the **outermost** middleware so 401s carry CORS headers; otherwise the webview sees a network error instead of 401. The webview origin on Windows is `http://tauri.localhost`.
- The CSP allows `connect-src http://127.0.0.1:*` and `worker-src blob:` for pdf.js; keep it explicit.
- Frontend code that runs before the backend is ready must handle both orders: the `backend-ready` event may fire before or after the UI subscribes (the spike calls `backend_info` after subscribing).
- WebView2 follows the Windows app theme. With Windows in dark mode, native controls get light text even when the page styles them light, so the spike's buttons rendered white on white. Every surface the UI styles must set both foreground and background from tokens, and the root must declare `color-scheme` to match the active theme (Task 8).
- `tez` must canonicalize relative paths before forwarding (the receiving process has a different cwd) and strip the `\\?\` prefix.
- The backend's `cli` mode must force UTF-8 stdout. Windows PowerShell 5.1 pipelines still decode with the OEM code page; document `[Console]::OutputEncoding = [Text.UTF8Encoding]::new()` for `--json` users.
- Licensing (rule 6): PyInstaller is GPL-2.0 **with the bootloader exception**, so bundling does not affect TEz's MIT license. To be restated in the Task 21 license notes.

## Alternatives considered

| Option | Why not |
| --- | --- |
| Tauri picks the port and passes it to the sidecar (plan) | Race between picking and binding. |
| Rely on `tauri-plugin-shell` to kill the sidecar | Misses crashes, forced kills and grandchildren. |
| Assign `TEz.exe` itself to the job | Simpler, but anything TEz launches (e.g. "open in system viewer") would die with it. |
| PyInstaller onefile | Unpacks on every start and adds a second process; slower and harder to kill cleanly. |
| `tez` as a PyInstaller console exe | ~340 ms Python start even for window commands; a Rust shim is 16 ms. |
| `tez.cmd` batch shim | Batch argument quoting is fragile with spaces and `&`; no single-binary installer story. |

## Open risks

- **Launch → Rust `main` ≈ 600 ms.** Probably real-time antivirus scanning an unsigned, freshly installed binary; to re-measure with a signed build (Phase 6). Code signing cost is still open (plan, "Kod imzalama").
- **Sidecar starts only after Tauri plugin/runtime init (~330 ms).** Spawning it at the top of `run()` with `std::process` (same job object, same stdin/stdout contract) would overlap Python start-up with WebView2 start-up and save ~300 ms. Candidate for Task 3/8; not required.
- **WebView2 memory** grows from 170 MB to ~410 MB private after skimming 80 pages; the JS heap stays at 5 MB, so most of it is GPU/compositor cache that the browser manages. Acceptable for a desktop app; re-check in Task 20 with real papers and the reader UI.
- **Scroll smoothness** was measured and then confirmed by hand by the owner (scrolled to page 300).
- **SmartScreen** warns on the unsigned installer (expected).
- **macOS / Linux** were not tested (Phase 6); WKWebView and WebKitGTK pdf.js performance remain open as the plan's "Webview farkları" risk.
- **Windows Defender** did not flag the PyInstaller binary in this spike; it is known to do so occasionally.
