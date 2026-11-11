"""`tez-backend` entry point.

`serve` runs the API in one of three ways:

- `serve --token-stdin`: sidecar for the desktop app (ADR 0001). Reads the token from the
  first stdin line, binds a free port, prints `TEZ_READY {"port": N}` on stdout after
  `listen()`, and shuts down when stdin closes (the app went away).
- `serve`: web mode. Generates a token and prints the address and token, like Jupyter.
- `serve --reload`: development. Like web mode, plus code reload, open API docs, console
  logs and a development library in `backend/.dev/` unless `--library` says otherwise.

`--library <folder>` opens a library exclusively (`--create` makes it if missing). If that
fails, the sidecar prints `TEZ_ERROR {"code": ..., "params": ...}` instead of `TEZ_READY`
and every mode exits with status 3.

`worker --library <folder>` runs queued jobs; `serve` starts it as a child process when a
library is open (`tez.worker`). `cli ...` runs the `tez` terminal command (Task 23).

`restore <backup.zip> <folder>` unpacks a backup into a new library folder, checks it, and
brings its schema up to date (Task 21).
"""

import argparse
import json
import logging
import os
import secrets
import socket
import sys
import threading
from datetime import timedelta
from pathlib import Path

import uvicorn

from tez.core.config import Settings
from tez.core.errors import TezError
from tez.core.logging import configure_logging
from tez.main import DEV_LIBRARY_ENV, DEV_TOKEN_ENV, DEV_URL_ENV, create_app
from tez.modules.library.service import Library, open_library
from tez.worker import run_worker_process

logger = logging.getLogger("tez.serve")

EXIT_LIBRARY_ERROR = 3
# backend/.dev/ next to src/; only `serve --reload` from a source checkout uses it.
DEV_LIBRARY = Path(__file__).resolve().parents[2] / ".dev" / "TEz Library"


def main(argv: list[str] | None = None) -> None:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments[:1] == ["cli"]:
        # The packaged `tez` console program forwards here (plan: a thin console shell).
        from tez.cli.main import main as cli_main

        cli_main(arguments[1:])
        return
    parser = argparse.ArgumentParser(prog="tez-backend")
    modes = parser.add_subparsers(dest="mode", required=True)
    serve = modes.add_parser("serve", help="run the API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, help="default: 8787, or a free port with --token-stdin")
    started_by = serve.add_mutually_exclusive_group()
    started_by.add_argument(
        "--token-stdin", action="store_true", help="sidecar mode for the desktop app"
    )
    started_by.add_argument("--reload", action="store_true", help="restart on code changes (dev)")
    serve.add_argument("--library", type=Path, help="library folder to open")
    serve.add_argument("--create", action="store_true", help="create the library if missing")
    worker = modes.add_parser("worker", help="run queued jobs (started by serve)")
    worker.add_argument("--library", type=Path, required=True, help="library folder")
    restore = modes.add_parser("restore", help="restore a backup into a new library folder")
    restore.add_argument("backup", type=Path, help="a TEz-backup-*.zip file")
    restore.add_argument("folder", type=Path, help="a new or empty folder")
    args = parser.parse_args(argv)

    if args.mode == "restore":
        sys.exit(_restore(args.backup, args.folder))

    if args.mode == "worker":
        settings = Settings()
        configure_logging(settings)
        sys.exit(
            run_worker_process(
                args.library,
                lease=timedelta(seconds=settings.job_lease_seconds),
                poll_interval=settings.worker_poll_seconds,
            )
        )
    if args.mode == "serve":
        if args.token_stdin:
            sys.exit(_serve_sidecar(args.host, args.port or 0, args.library, create=args.create))
        _serve_web(
            args.host, args.port or 8787, args.library, create=args.create, reload=args.reload
        )


def _serve_web(
    host: str, port: int, library_path: Path | None, *, create: bool, reload: bool
) -> None:
    token = secrets.token_urlsafe(32)
    url = f"http://{host}:{port}"
    if reload:
        print(f"TEz API: {url}  token: {token}", flush=True)
        # The reloaded child process builds the app from these (see create_dev_app).
        os.environ[DEV_TOKEN_ENV] = token
        os.environ[DEV_URL_ENV] = url
        os.environ[DEV_LIBRARY_ENV] = str(library_path or DEV_LIBRARY)
        os.environ.setdefault("TEZ_LOG_FORMAT", "console")
        configure_logging(Settings())
        print(f"API docs (dev, no token needed): http://{host}:{port}/docs", flush=True)
        uvicorn.run(
            "tez.main:create_dev_app",
            factory=True,
            host=host,
            port=port,
            reload=True,
            # Watch only the package; the default (cwd) would scan node_modules and target/.
            reload_dirs=[str(Path(__file__).parent)],
            log_config=None,
            access_log=False,
        )
        return

    settings = Settings()
    configure_logging(settings)
    try:
        library = _open(library_path, create=create)
    except TezError as error:
        details = ", ".join(f"{key} {value}" for key, value in error.params.items())
        print(f"tez-backend: {error.code.value}: {details}", file=sys.stderr)
        sys.exit(EXIT_LIBRARY_ERROR)
    print(f"TEz API: {url}  token: {token}", flush=True)
    try:
        if library is not None:
            library.publish_api(url=url, token=token)
        app = create_app(token=token, settings=settings, library=library, start_worker=True)
        uvicorn.run(app, host=host, port=port, log_config=None, access_log=False)
    finally:
        if library is not None:
            library.close()


def _serve_sidecar(host: str, port: int, library_path: Path | None, *, create: bool) -> int:
    token = sys.stdin.readline().strip()
    if not token:
        print("tez-backend: no token on stdin (serve --token-stdin)", file=sys.stderr)
        return 2

    settings = Settings()
    configure_logging(settings)
    try:
        library = _open(library_path, create=create)
    except TezError as error:
        # The desktop app shows this in the UI's language; see the TEZ_READY contract.
        message = {"code": error.code.value, "params": error.params}
        print("TEZ_ERROR " + json.dumps(message, default=str), flush=True)
        return EXIT_LIBRARY_ERROR
    try:
        return _run_sidecar(host, port, token, settings, library)
    finally:
        if library is not None:
            library.close()


def _restore(backup: Path, folder: Path) -> int:
    from tez.modules.backup.service import restore_backup

    configure_logging(Settings())
    try:
        restored = restore_backup(backup, folder)
        # Opening migrates a backup made by an older version, and indexes it.
        open_library(restored.path).close()
    except TezError as error:
        details = ", ".join(f"{key} {value}" for key, value in error.params.items())
        print(f"tez-backend: {error.code.value}: {details}", file=sys.stderr)
        return EXIT_LIBRARY_ERROR
    print(
        f"restored {restored.papers} papers and {restored.files} files "
        f"(schema {restored.schema_revision}) into {restored.path}",
        flush=True,
    )
    return 0


def _open(library_path: Path | None, *, create: bool) -> Library | None:
    return None if library_path is None else open_library(library_path, create=create)


def _run_sidecar(
    host: str, port: int, token: str, settings: Settings, library: Library | None
) -> int:
    app = create_app(token=token, settings=settings, library=library, start_worker=True)
    server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False))

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))
    # listen() before announcing: a request sent right after TEZ_READY waits in the backlog
    # instead of being refused (ADR 0001).
    sock.listen(128)
    bound_port: int = sock.getsockname()[1]
    if library is not None:
        library.publish_api(url=f"http://{host}:{bound_port}", token=token)

    def stop_when_stdin_closes() -> None:
        try:
            while sys.stdin.readline():
                pass
        except (OSError, ValueError):
            logger.warning("stdin watcher failed; shutting down", exc_info=True)
        logger.info("stdin closed; shutting down")
        server.should_exit = True

    threading.Thread(target=stop_when_stdin_closes, daemon=True, name="stdin-eof").start()
    print("TEZ_READY " + json.dumps({"port": bound_port, "pid": os.getpid()}), flush=True)
    server.run(sockets=[sock])
    return 0


if __name__ == "__main__":
    main()
