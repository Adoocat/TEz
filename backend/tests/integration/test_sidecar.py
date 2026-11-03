"""The sidecar contract from ADR 0001, exercised on a real `tez-backend serve --token-stdin`.

Token over stdin -> `TEZ_READY {"port": N}` on stdout after listen() -> 401 without the
token, 200 with it -> exit when stdin closes (the desktop app went away).
"""

import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from queue import Empty, Queue
from typing import IO

import pytest

TOKEN = "integration-token-0123456789"
START_TIMEOUT_S = 30
EXIT_TIMEOUT_S = 15


class Sidecar:
    def __init__(self, proc: subprocess.Popen[str], port: int) -> None:
        self.proc = proc
        self.port = port

    def get(self, path: str, token: str | None = None) -> tuple[int, str]:
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        if token is not None:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()


def _read_lines(stream: IO[str] | None, lines: Queue[str]) -> None:
    assert stream is not None
    for line in stream:
        lines.put(line)


@pytest.fixture
def sidecar() -> Iterator[Sidecar]:
    env = {**os.environ, "TEZ_LOG_FORMAT": "json", "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "tez", "serve", "--token-stdin"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    stdout: Queue[str] = Queue()
    stderr: Queue[str] = Queue()
    readers = [
        threading.Thread(target=_read_lines, args=(proc.stdout, stdout), daemon=True),
        threading.Thread(target=_read_lines, args=(proc.stderr, stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    try:
        assert proc.stdin is not None
        proc.stdin.write(TOKEN + "\n")
        proc.stdin.flush()
        try:
            line = stdout.get(timeout=START_TIMEOUT_S)
        except Empty:
            pytest.fail("no TEZ_READY line; stderr:\n" + "".join(stderr.queue))
        assert line.startswith("TEZ_READY "), line
        ready = json.loads(line.removeprefix("TEZ_READY "))
        yield Sidecar(proc, ready["port"])
        # Nothing but the ready line may appear on stdout: the desktop app parses it.
        assert stdout.empty(), list(stdout.queue)
        assert TOKEN not in "".join(stderr.queue)
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        for reader in readers:
            reader.join(timeout=EXIT_TIMEOUT_S)
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if pipe is not None and not pipe.closed:
                pipe.close()


def test_request_without_token_is_401(sidecar: Sidecar) -> None:
    status, body = sidecar.get("/health")

    assert status == 401
    assert json.loads(body) == {"error": {"code": "auth.invalid_token", "params": {}}}


def test_request_with_token_is_200(sidecar: Sidecar) -> None:
    status, body = sidecar.get("/health", token=TOKEN)

    assert status == 200
    assert json.loads(body)["status"] == "ok"


def test_exits_when_stdin_closes(sidecar: Sidecar) -> None:
    assert sidecar.proc.stdin is not None
    sidecar.proc.stdin.close()

    assert sidecar.proc.wait(timeout=EXIT_TIMEOUT_S) == 0


def test_refuses_to_start_without_a_token() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tez", "serve", "--token-stdin"],
        input="\n",
        capture_output=True,
        text=True,
        timeout=START_TIMEOUT_S,
        check=False,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "token" in result.stderr
