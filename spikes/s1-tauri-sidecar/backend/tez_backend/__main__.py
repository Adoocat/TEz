"""S1 spike backend: one binary, three modes (serve / worker / cli).

Throwaway code. It exists only to measure packaging and process management.

serve:  reads the auth token from the first stdin line, binds 127.0.0.1:0,
        prints `TEZ_READY {"port": N}` on stdout, starts a worker child and
        exits when stdin reaches EOF (parent died).
worker: dummy job loop; exits when its stdin reaches EOF (serve died).
cli:    prints to the console to prove a console program can write output.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time

T0 = time.perf_counter()


def _child_cmd(mode: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, mode]
    return [sys.executable, "-m", "tez_backend", mode]


def _exit_on_stdin_eof(on_exit: "callable[[], None] | None" = None) -> None:
    def watch() -> None:
        try:
            while sys.stdin.readline():
                pass
        except (OSError, ValueError) as exc:  # stdin closed abruptly
            print(f"stdin watcher stopped: {exc!r}", file=sys.stderr)
        if on_exit is not None:
            on_exit()
        os._exit(0)

    threading.Thread(target=watch, daemon=True, name="stdin-eof").start()


def serve() -> int:
    token = os.environ.pop("TEZ_TOKEN", None) or sys.stdin.readline().strip()
    if not token:
        print("no token on stdin", file=sys.stderr)
        return 1

    worker = subprocess.Popen(
        _child_cmd("worker"),
        stdin=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    def kill_worker() -> None:
        if worker.poll() is None:
            worker.kill()

    _exit_on_stdin_eof(kill_worker)

    # Heavy imports after the token handshake so we can time them separately.
    t_import = time.perf_counter()
    import uvicorn
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse

    import_ms = (time.perf_counter() - t_import) * 1000

    app = FastAPI()

    @app.middleware("http")
    async def require_token(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method != "OPTIONS" and request.headers.get("authorization") != f"Bearer {token}":
            return JSONResponse({"error": {"code": "auth.invalid_token", "params": {}}}, status_code=401)
        return await call_next(request)

    # Added last = outermost, so even 401 responses carry CORS headers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://tauri.localhost", "http://localhost:1420"],
        allow_methods=["GET"],
        allow_headers=["Authorization", "Range"],
        expose_headers=["Accept-Ranges", "Content-Range", "Content-Length"],
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "pid": os.getpid(),
            "worker_pid": worker.pid,
            "worker_alive": worker.poll() is None,
            "import_ms": round(import_ms, 1),
            "uptime_ms": round((time.perf_counter() - T0) * 1000, 1),
        }

    sample = os.environ.get("TEZ_SAMPLE_PDF") or os.path.join(
        os.environ.get("TEMP", "."), "tez-s1", "sample-300.pdf"
    )

    @app.get("/files/sample.pdf")
    def sample_pdf() -> FileResponse:
        return FileResponse(sample, media_type="application/pdf")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    # listen() before announcing the port: connections made right after
    # TEZ_READY wait in the backlog instead of being refused.
    sock.listen(128)
    port = sock.getsockname()[1]
    config = uvicorn.Config(app, log_level="warning", access_log=False)
    server = uvicorn.Server(config)

    print("TEZ_READY " + json.dumps({"port": port, "pid": os.getpid()}), flush=True)
    server.run(sockets=[sock])
    kill_worker()
    return 0


def worker() -> int:
    _exit_on_stdin_eof()
    while True:
        time.sleep(1)


def cli(args: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except AttributeError:
        pass
    if args[:1] == ["hello"]:
        name = args[1] if len(args) > 1 else "dünya"
        print(f"Merhaba, {name}! (tez-backend cli, pid {os.getpid()})")
        print(f"İlk çıktıya kadar: {(time.perf_counter() - T0) * 1000:.0f} ms (yorumlayıcı açılışı hariç)")
        return 0
    print("kullanım: tez-backend cli hello [ad]", file=sys.stderr)
    return 1


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "serve":
        return serve()
    if mode == "worker":
        return worker()
    if mode == "cli":
        return cli(sys.argv[2:])
    print("usage: tez-backend serve|worker|cli ...", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
