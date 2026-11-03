# S1 spike — Tauri v2 + Python sidecar

Throwaway code for risk spike S1. Results and decisions: [`docs/adr/0001-desktop-shell-and-sidecar.md`](../../docs/adr/0001-desktop-shell-and-sidecar.md). Do not import anything from here into the main code base.

## Layout

```text
backend/   tez-backend: serve | worker | cli (FastAPI hello, PyInstaller onedir)
desktop/   Tauri v2 shell + Vite/TS page with a virtualized pdf.js viewer
cli/       `tez` console launcher (Rust)
scripts/   build.py · measure.py · gen_pdf.py · check_backend.py
BUILD.json / RESULTS.json   measurements from the last run
```

## Reproduce (Windows, PowerShell)

Requires uv, Rust (MSVC), pnpm, VS Build Tools.

```powershell
cd spikes/s1-tauri-sidecar/backend; uv sync; cd ..
cd desktop; pnpm install; cd ..
backend/.venv/Scripts/python.exe scripts/build.py      # onedir + tez.exe + NSIS installer
backend/.venv/Scripts/python.exe scripts/measure.py --installer desktop/src-tauri/target/release/bundle/nsis/TEz_0.0.1_x64-setup.exe
```

`measure.py` installs silently (per user), runs 13 checks, writes `RESULTS.json` and uninstalls. The app window opens and closes a few times while it runs.

Manual look: run the installed `TEz.exe`, click **300 sayfalık PDF'i aç**, scroll; then from another terminal run `tez <some.pdf>` (from `%LOCALAPPDATA%\TEz\bin`) and watch it appear in the "İletilen argümanlar" list.
