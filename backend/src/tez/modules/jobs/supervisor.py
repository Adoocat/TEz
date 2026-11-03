"""The API process starts the worker process and restarts it when it dies (plan, "Mimari")."""

import json
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

from tez.modules.jobs.schemas import WorkerStatus

logger = logging.getLogger(__name__)

MAX_BACKOFF_S = 30.0
# A worker that ran this long before dying resets the back-off: it was not a crash loop.
STABLE_AFTER_S = 60.0
STOP_TIMEOUT_S = 10.0


def worker_command(library: Path) -> list[str]:
    if getattr(sys, "frozen", False):  # PyInstaller build: the same binary, another mode
        return [sys.executable, "worker", "--library", str(library)]
    return [sys.executable, "-m", "tez", "worker", "--library", str(library)]


class WorkerSupervisor:
    def __init__(self, library: Path) -> None:
        self.library = library
        self._proc: subprocess.Popen[str] | None = None
        self._pid: int | None = None
        self._restarts = 0
        self._stopping = threading.Event()
        self._lock = threading.Lock()
        self._monitor: threading.Thread | None = None

    def start(self) -> None:
        self._spawn()
        self._monitor = threading.Thread(target=self._watch, name="worker-supervisor", daemon=True)
        self._monitor.start()

    def stop(self) -> None:
        """Ask the worker to stop (stdin EOF), then kill it if it does not."""
        self._stopping.set()
        with self._lock:
            proc = self._proc
        if proc is not None:
            _close_quietly(proc)
            try:
                proc.wait(timeout=STOP_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                logger.warning("worker did not stop; killing it", extra={"pid": self._pid})
                proc.kill()
                proc.wait()
        if self._monitor is not None:
            self._monitor.join(timeout=STOP_TIMEOUT_S)

    def status(self) -> WorkerStatus:
        with self._lock:
            alive = self._proc is not None and self._proc.poll() is None
            return WorkerStatus(
                alive=alive, pid=self._pid if alive else None, restarts=self._restarts
            )

    def _spawn(self) -> None:
        proc = subprocess.Popen(
            worker_command(self.library),
            stdin=subprocess.PIPE,  # kept open; EOF tells the worker to stop
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        with self._lock:
            self._proc, self._pid = proc, None
        threading.Thread(target=self._read_stdout, args=(proc,), daemon=True).start()

    def _read_stdout(self, proc: subprocess.Popen[str]) -> None:
        # The worker announces its own pid: on Windows a venv's python.exe is a launcher,
        # so proc.pid is not the process that runs the jobs.
        assert proc.stdout is not None
        with proc.stdout:
            for line in proc.stdout:
                kind, _, payload = line.strip().partition(" ")
                if kind == "TEZ_WORKER_READY":
                    pid = int(json.loads(payload)["pid"])
                    with self._lock:
                        if self._proc is proc:
                            self._pid = pid
                    logger.info("worker running", extra={"pid": pid})

    def _watch(self) -> None:
        backoff = 1.0
        while True:
            with self._lock:
                proc = self._proc
            assert proc is not None
            started = time.monotonic()
            code = proc.wait()
            _close_quietly(proc)
            if self._stopping.is_set():
                return
            if time.monotonic() - started > STABLE_AFTER_S:
                backoff = 1.0
            logger.error("worker exited; restarting", extra={"exit_code": code, "in_s": backoff})
            if self._stopping.wait(backoff):
                return
            backoff = min(backoff * 2, MAX_BACKOFF_S)
            with self._lock:
                self._restarts += 1
            self._spawn()


def _close_quietly(proc: subprocess.Popen[str]) -> None:
    if proc.stdin is not None and not proc.stdin.closed:
        try:
            proc.stdin.close()
        except OSError:
            logger.debug("worker stdin already closed", exc_info=True)
