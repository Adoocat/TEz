"""Quick check of the backend contract without Tauri.

usage: python check_backend.py <command...>
e.g.   python check_backend.py backend/.venv/Scripts/python.exe -m tez_backend
       python check_backend.py backend/dist/tez-backend/tez-backend.exe
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

TOKEN = "spike-token"


def get(url: str, token: str | None) -> tuple[int, str]:
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main() -> int:
    cmd = [os.path.abspath(sys.argv[1]), *sys.argv[2:], "serve"]
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    assert p.stdin and p.stdout
    p.stdin.write(TOKEN + "\n")
    p.stdin.flush()
    line = p.stdout.readline()
    t_ready = time.perf_counter()
    assert line.startswith("TEZ_READY "), line
    port = json.loads(line.split(" ", 1)[1])["port"]
    base = f"http://127.0.0.1:{port}"
    code, _ = get(base + "/health", None)
    t_health = time.perf_counter()
    code_ok, body = get(base + "/health", TOKEN)
    health = json.loads(body)
    print(f"ready after      {1000 * (t_ready - t0):7.0f} ms")
    print(f"first /health    {1000 * (t_health - t0):7.0f} ms")
    print(f"no token  -> {code} (want 401)")
    print(f"with token-> {code_ok} {health}")

    worker_pid = health["worker_pid"]
    p.stdin.close()  # simulate parent death: stdin EOF
    p.wait(timeout=5)
    time.sleep(1.5)
    alive = subprocess.run(
        ["tasklist", "/FI", f"PID eq {worker_pid}", "/NH"], capture_output=True, text=True
    ).stdout
    worker_gone = str(worker_pid) not in alive
    print(f"after stdin EOF: serve exit={p.returncode}, worker gone={worker_gone}")
    return 0 if code == 401 and code_ok == 200 and worker_gone else 1


if __name__ == "__main__":
    sys.exit(main())
