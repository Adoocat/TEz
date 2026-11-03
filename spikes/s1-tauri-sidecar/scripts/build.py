"""Build the S1 spike end to end and record artifact sizes.

usage: python scripts/build.py   (from spikes/s1-tauri-sidecar, with uv, cargo, pnpm on PATH)

1. PyInstaller onedir  -> backend/dist/tez-backend/
2. copy the exe to desktop/src-tauri/binaries/tez-backend-<target-triple>.exe
3. cargo build --release the `tez` console program
4. pnpm tauri build (NSIS installer)
Sizes are written to BUILD.json.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

SPIKE = Path(__file__).resolve().parent.parent
BACKEND = SPIKE / "backend"
DESKTOP = SPIKE / "desktop"
CLI = SPIKE / "cli"


def run(cmd: list[str], cwd: Path) -> float:
    print(f"$ {' '.join(cmd)}  (in {cwd.name})", flush=True)
    t0 = time.time()
    subprocess.run(cmd, cwd=cwd, check=True, shell=sys.platform == "win32")
    return round(time.time() - t0, 1)


def size_mb(p: Path) -> float:
    total = p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return round(total / 1048576, 1)


def main() -> int:
    info: dict[str, object] = {}
    info["pyinstaller_s"] = run(
        ["uv", "run", "pyinstaller", "--noconfirm", "--onedir", "--console", "--name", "tez-backend",
         "--log-level", "WARN", "--exclude-module", "tkinter", "entry.py"],
        BACKEND,
    )
    onedir = BACKEND / "dist" / "tez-backend"
    info["onedir_mb"] = size_mb(onedir)
    info["onedir_exe_mb"] = size_mb(onedir / "tez-backend.exe")

    triple = subprocess.run(["rustc", "--print", "host-tuple"], capture_output=True, text=True, check=True).stdout.strip()
    binaries = DESKTOP / "src-tauri" / "binaries"
    binaries.mkdir(exist_ok=True)
    shutil.copy2(onedir / "tez-backend.exe", binaries / f"tez-backend-{triple}.exe")

    info["cli_build_s"] = run(["cargo", "build", "--release", "-q"], CLI)
    info["tez_cli_exe_kb"] = round((CLI / "target" / "release" / "tez.exe").stat().st_size / 1024)

    info["tauri_build_s"] = run(["pnpm", "tauri", "build"], DESKTOP)
    release = DESKTOP / "src-tauri" / "target" / "release"
    info["tez_app_exe_mb"] = size_mb(release / "TEz.exe")
    installer = next((release / "bundle" / "nsis").glob("*-setup.exe"))
    info["installer"] = str(installer.relative_to(SPIKE))
    info["installer_mb"] = size_mb(installer)

    (SPIKE / "BUILD.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
