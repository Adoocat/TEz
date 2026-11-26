"""The sidecar contract from ADR 0001, exercised on a real `tez-backend serve --token-stdin`.

Token over stdin -> `TEZ_READY {"port": N}` on stdout after listen() -> 401 without the
token, 200 with it -> exit when stdin closes (the desktop app went away).
"""

import json
import subprocess
import sys
from collections.abc import Iterator

import pytest

from tests.integration.sidecar import (
    EXIT_TIMEOUT_S,
    START_TIMEOUT_S,
    SidecarProcess,
    run_sidecar,
)

# Each test starts the backend as a process and waits for it against a deadline: run alone
# (`pnpm check`), not beside eleven other test processes.
pytestmark = pytest.mark.timing

TOKEN = "integration-token-0123456789"


@pytest.fixture
def sidecar() -> Iterator[SidecarProcess]:
    with run_sidecar(TOKEN) as process:
        kind, _ = process.first_line()
        assert kind == "TEZ_READY"
        yield process
        # Nothing but the ready line may appear on stdout: the desktop app parses it.
        assert process.stdout.empty(), list(process.stdout.queue)
        assert TOKEN not in process.stderr_text()


def test_request_without_token_is_401(sidecar: SidecarProcess) -> None:
    status, body = sidecar.get("/health")

    assert status == 401
    assert json.loads(body) == {"error": {"code": "auth.invalid_token", "params": {}}}


def test_request_with_token_is_200(sidecar: SidecarProcess) -> None:
    status, body = sidecar.get("/health", token=TOKEN)

    assert status == 200
    assert json.loads(body)["status"] == "ok"


def test_exits_when_stdin_closes(sidecar: SidecarProcess) -> None:
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
