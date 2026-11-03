"""S1 end-to-end checks and measurements on Windows.

usage:
  python measure.py --installer <TEz_..._setup.exe>   # install silently, test, uninstall
  python measure.py --install-dir <dir>               # test an existing install / build dir

Checks (each prints PASS/FAIL):
  1. app starts the sidecar with port+token; /health 200 with token, 401 without
  2. second launch `TEz.exe <pdf>` is forwarded to the running window, no 2nd process stays
  3. `tez` console program prints output and forwards window commands
  4. tez:// deep link reaches the running window
  5. pdf.js self-test (300 pages) completes; memory recorded
  6. graceful close (WM_CLOSE) leaves no backend/worker process
  7. forced kill (taskkill /F) leaves no backend/worker process (job object)

Results are written to RESULTS.json next to this script's parent folder.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RUN_JSON = Path(tempfile.gettempdir()) / "tez-s1" / "run.json"
SAMPLE_PDF = Path(tempfile.gettempdir()) / "tez-s1" / "sample-300.pdf"
SPIKE = Path(__file__).resolve().parent.parent
results: dict[str, object] = {}
checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def dir_size_mb(p: Path) -> float:
    return round(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1048576, 1)


def procs() -> list[dict]:
    out = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,"
            "WorkingSetSize,PrivatePageCount | ConvertTo-Json -Compress",
        ],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def descendants(root: int, table: list[dict]) -> list[dict]:
    found, frontier = [], {root}
    while frontier:
        nxt = {p["ProcessId"] for p in table if p["ParentProcessId"] in frontier} - {x["ProcessId"] for x in found}
        found += [p for p in table if p["ProcessId"] in nxt]
        frontier = nxt
    return found


def alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def count(name: str) -> int:
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"], capture_output=True, text=True).stdout
    return out.lower().count(name.lower())


def run_json() -> dict:
    try:
        return json.loads(RUN_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def wait_for(cond, timeout: float, what: str):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = cond()
        if v:
            return v
        time.sleep(0.2)
    raise TimeoutError(what)


def kill_all() -> None:
    for name in ("TEz.exe", "tez-backend.exe"):
        subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True)
    time.sleep(1)


def start_app(app: Path, *args: str) -> tuple[subprocess.Popen, float]:
    RUN_JSON.unlink(missing_ok=True)
    launched = time.time() * 1000
    p = subprocess.Popen([str(app), *args])
    return p, launched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--installer", type=Path)
    ap.add_argument("--install-dir", type=Path)
    a = ap.parse_args()

    if not SAMPLE_PDF.exists():
        subprocess.run([sys.executable, str(SPIKE / "scripts" / "gen_pdf.py")], check=True)
    kill_all()

    install_dir = a.install_dir
    if a.installer:
        results["installer_mb"] = round(a.installer.stat().st_size / 1048576, 1)
        t0 = time.time()
        subprocess.run([str(a.installer), "/S"], check=True)
        results["install_seconds"] = round(time.time() - t0, 1)
        install_dir = Path(os.environ["LOCALAPPDATA"]) / "TEz"
    assert install_dir and (install_dir / "TEz.exe").exists(), f"TEz.exe not in {install_dir}"
    results["installed_mb"] = dir_size_mb(install_dir)
    results["install_layout"] = sorted(p.name for p in install_dir.iterdir())
    app = install_dir / "TEz.exe"
    tez = install_dir / "bin" / "tez.exe"

    # 1 + 5: start with self-test, wait for backend and pdf benchmark
    p, launched = start_app(app, "--selftest")
    r = wait_for(lambda: (j := run_json()).get("first_health_ms") and j, 60, "first /health")
    startup = {
        "process_to_rust_main_ms": round(r["app_start_unix_ms"] - launched),
        "window_ready_ms": round(r.get("window_ready_ms", -1)),
        "sidecar_spawn_ms": round(r["sidecar_spawn_ms"]),
        "sidecar_ready_ms": round(r["sidecar_ready_ms"]),
        "first_health_ms": round(r["first_health_ms"]),
        "sidecar_ready_after_spawn_ms": round(r["sidecar_ready_ms"] - r["sidecar_spawn_ms"]),
    }
    results["startup"] = startup
    h = r["health"]
    check("1 sidecar /health with token", h.get("status") == "ok", f"port={r['sidecar_port']}")
    check("1 /health without token is 401", h.get("unauthorized_status") == 401)
    check("1 job object assignment", "job_assign_error" not in r, str(r.get("job_assign_error", "")))
    backend_pid, worker_pid = r["sidecar_pid"], h["worker_pid"]

    r = wait_for(lambda: (j := run_json()).get("selftest_done_ms") and j, 240, "pdf self-test")
    table = procs()
    tree = descendants(p.pid, table)
    webview = [x for x in tree if x["Name"].lower() == "msedgewebview2.exe"]
    backend = [x for x in tree if x["Name"].lower() == "tez-backend.exe"]
    app_row = next(x for x in table if x["ProcessId"] == p.pid)
    mem = {
        "app_ws_mb": round(app_row["WorkingSetSize"] / 1048576),
        "webview2_ws_mb": round(sum(x["WorkingSetSize"] for x in webview) / 1048576),
        "webview2_private_mb": round(sum(int(x["PrivatePageCount"]) for x in webview) / 1048576),
        "webview2_processes": len(webview),
        "backend_ws_mb": round(sum(x["WorkingSetSize"] for x in backend) / 1048576),
        "backend_processes": len(backend),
    }
    results["memory_after_pdf_bench"] = mem
    results["pdf_open"] = r.get("pdf_open")
    results["pdf_bench"] = r.get("pdf_bench")
    bench = r.get("pdf_bench") or {}
    check("5 pdf.js 300-page self-test", bool(bench), f"avgFps={bench.get('avgFps')} heap={bench.get('heapAfterBenchMb')}MB")

    # 2: second instance with a PDF path
    before = count("TEz.exe")
    subprocess.run([str(app), str(SAMPLE_PDF)], timeout=30)
    fwd = wait_for(lambda: run_json().get("last_forwarded"), 10, "forwarded args")
    check("2 second instance forwarded", str(SAMPLE_PDF) in fwd["args"], json.dumps(fwd["args"]))
    time.sleep(1)
    check("2 no extra TEz.exe process", count("TEz.exe") == before, f"count={count('TEz.exe')}")

    # 3: tez console program
    t = []
    for _ in range(5):
        t0 = time.perf_counter()
        out = subprocess.run([str(tez), "--help"], capture_output=True, text=True, encoding="utf-8")
        t.append((time.perf_counter() - t0) * 1000)
    results["tez_help_ms_median"] = round(statistics.median(t))
    check("3 `tez --help` prints", "Kullanım" in out.stdout)
    t = []
    for _ in range(5):
        t0 = time.perf_counter()
        out = subprocess.run([str(tez), "hello", "Demirkan"], capture_output=True, text=True, encoding="utf-8")
        t.append((time.perf_counter() - t0) * 1000)
    results["tez_hello_via_backend_ms_median"] = round(statistics.median(t))
    check("3 `tez hello` via backend prints", "Merhaba, Demirkan" in out.stdout, out.stdout.strip().splitlines()[0])
    rel_dir = SAMPLE_PDF.parent
    out = subprocess.run([str(tez), SAMPLE_PDF.name], cwd=rel_dir, capture_output=True, text=True, encoding="utf-8")
    time.sleep(2)
    fwd = run_json().get("last_forwarded", {})
    check("3 `tez <relative pdf>` forwarded as absolute", str(SAMPLE_PDF) in fwd.get("args", []), out.stdout.strip())

    # 4: deep link
    url = "tez://open?citekey=demo2024&page=4"
    # Start-Process hands the URL to the protocol handler like a browser would ('&' safe).
    subprocess.run(["powershell", "-NoProfile", "-Command", f"Start-Process '{url}'"])
    try:
        dl = wait_for(lambda: run_json().get("last_deep_link"), 10, "deep link")
        ok = any(u.startswith("tez://open") and "page=4" in u and "citekey=demo2024" in u for u in dl["args"])
        check("4 tez:// deep link forwarded (all params)", ok, json.dumps(dl["args"]))
    except TimeoutError:
        check("4 tez:// deep link forwarded", False, "timeout (scheme not registered?)")
    time.sleep(1)

    # 6: graceful close
    subprocess.run(["taskkill", "/PID", str(p.pid)], capture_output=True)
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    time.sleep(1.5)
    check("6 graceful close: backend gone", not alive(backend_pid))
    check("6 graceful close: worker gone", not alive(worker_pid))
    kill_all()

    # 7: forced kill
    p, _ = start_app(app)
    r = wait_for(lambda: (j := run_json()).get("first_health_ms") and j, 60, "first /health (2)")
    backend_pid, worker_pid = r["sidecar_pid"], r["health"]["worker_pid"]
    time.sleep(3)
    table = procs()
    webview = [x for x in descendants(p.pid, table) if x["Name"].lower() == "msedgewebview2.exe"]
    results["memory_idle_no_pdf"] = {
        "webview2_ws_mb": round(sum(x["WorkingSetSize"] for x in webview) / 1048576),
        "webview2_private_mb": round(sum(int(x["PrivatePageCount"]) for x in webview) / 1048576),
    }
    t0 = time.time()
    subprocess.run(["taskkill", "/F", "/PID", str(p.pid)], capture_output=True)
    gone = False
    while time.time() - t0 < 5:
        if not alive(backend_pid) and not alive(worker_pid):
            gone = True
            break
        time.sleep(0.1)
    results["orphan_cleanup_after_force_kill_ms"] = round((time.time() - t0) * 1000) if gone else None
    check("7 forced kill: backend + worker gone", gone)
    kill_all()

    if a.installer:
        uninst = install_dir / "uninstall.exe"
        if uninst.exists():
            subprocess.run([str(uninst), "/S"])
            time.sleep(3)
            results["uninstall_left_files"] = install_dir.exists() and any(install_dir.rglob("*.exe"))

    results["checks"] = [{"name": n, "pass": ok, "detail": d} for n, ok, d in checks]
    (SPIKE / "RESULTS.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in results.items() if k != "checks"}, indent=2, ensure_ascii=False))
    failed = [n for n, ok, _ in checks if not ok]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
