"""`tez-backend` entry point.

Only the development `serve` mode exists for now; the sidecar contract from ADR 0001
(random port, token over stdin, worker child) arrives in Task 3, `worker` in Task 6b.
"""

import argparse
from pathlib import Path

import uvicorn


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="tez-backend")
    modes = parser.add_subparsers(dest="mode", required=True)
    serve = modes.add_parser("serve", help="run the API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--reload", action="store_true", help="restart on code changes (dev)")
    args = parser.parse_args(argv)

    if args.mode == "serve":
        # Watch only the package; the default (cwd) would scan node_modules and target/.
        reload_dirs = [str(Path(__file__).parent)] if args.reload else None
        uvicorn.run(
            "tez.main:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=args.reload,
            reload_dirs=reload_dirs,
        )


if __name__ == "__main__":
    main()
