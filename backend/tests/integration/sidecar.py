"""Runs a real `tez-backend serve --token-stdin` the way the desktop app does (ADR 0001)."""

import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from queue import Empty, Queue
from typing import IO, Any

import pytest

START_TIMEOUT_S = 30
EXIT_TIMEOUT_S = 15


def _read_lines(stream: IO[str] | None, lines: Queue[str]) -> None:
    assert stream is not None
    for line in stream:
        lines.put(line)


class SidecarProcess:
    def __init__(self, proc: subprocess.Popen[str]) -> None:
        self.proc = proc
        self.stdout: Queue[str] = Queue()
        self.stderr: Queue[str] = Queue()
        self.port: int | None = None
        # From TEZ_READY. Not proc.pid: on Windows a venv's python.exe is a launcher that
        # runs the real interpreter as a child process.
        self.pid: int | None = None

    def first_line(self) -> tuple[str, dict[str, Any]]:
        """The handshake line: ("TEZ_READY", {...}) or ("TEZ_ERROR", {...})."""
        try:
            line = self.stdout.get(timeout=START_TIMEOUT_S)
        except Empty:
            pytest.fail("no handshake line; stderr:\n" + self.stderr_text())
        kind, _, payload = line.strip().partition(" ")
        data: dict[str, Any] = json.loads(payload)
        if kind == "TEZ_READY":
            self.port = data["port"]
            self.pid = data["pid"]
        return kind, data

    def stderr_text(self) -> str:
        return "".join(self.stderr.queue)

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path: str, token: str | None = None) -> tuple[int, str]:
        request = urllib.request.Request(self.url(path))
        if token is not None:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()


@contextmanager
def run_sidecar(
    token: str, *args: str, env: dict[str, str] | None = None
) -> Iterator[SidecarProcess]:
    env = {**os.environ, "TEZ_LOG_FORMAT": "json", "PYTHONUNBUFFERED": "1", **(env or {})}
    proc = subprocess.Popen(
        [sys.executable, "-m", "tez", "serve", "--token-stdin", *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    sidecar = SidecarProcess(proc)
    readers = [
        threading.Thread(target=_read_lines, args=(proc.stdout, sidecar.stdout), daemon=True),
        threading.Thread(target=_read_lines, args=(proc.stderr, sidecar.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    try:
        assert proc.stdin is not None
        proc.stdin.write(token + "\n")
        proc.stdin.flush()
        yield sidecar
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        for reader in readers:
            reader.join(timeout=EXIT_TIMEOUT_S)
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if pipe is not None and not pipe.closed:
                pipe.close()
