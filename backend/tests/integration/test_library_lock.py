"""Task 5 acceptance: a second open of the same library gives a clear error.

Two real sidecars, as two desktop windows would start them. The second one must not
start serving; it reports `TEZ_ERROR` with a code the UI can translate, and who holds it.
"""

import json
from pathlib import Path

from tests.integration.sidecar import EXIT_TIMEOUT_S, run_sidecar
from tez.modules.library.service import find_instance

TOKEN = "integration-token-0123456789"
EXIT_LIBRARY_ERROR = 3


def test_second_window_on_the_same_library_gets_library_locked(tmp_path: Path) -> None:
    library = tmp_path / "TEz Library"
    args = ("--library", str(library), "--create")

    with run_sidecar(TOKEN, *args) as first:
        assert first.first_line()[0] == "TEZ_READY"

        with run_sidecar("other-token-0123456789", *args) as second:
            kind, data = second.first_line()
            assert second.proc.wait(timeout=EXIT_TIMEOUT_S) == EXIT_LIBRARY_ERROR

        assert kind == "TEZ_ERROR"
        assert data["code"] == "library.locked"
        assert data["params"]["pid"] == first.pid
        assert data["params"]["kind"] == "app"
        assert data["params"]["path"] == str(library)

        # The first window is unaffected and still serves.
        status, body = first.get("/library", token=TOKEN)
        assert status == 200
        assert json.loads(body)["path"] == str(library)


def test_running_sidecar_is_discoverable_by_the_cli(tmp_path: Path) -> None:
    library = tmp_path / "TEz Library"

    with run_sidecar(TOKEN, "--library", str(library), "--create") as sidecar:
        sidecar.first_line()

        instance = find_instance(library)
        assert instance is not None
        assert instance.pid == sidecar.pid
        assert instance.api is not None
        assert instance.api.url == f"http://127.0.0.1:{sidecar.port}"
        assert instance.api.token == TOKEN

        # Closing stdin is a clean shutdown: the discovery file goes away.
        assert sidecar.proc.stdin is not None
        sidecar.proc.stdin.close()
        assert sidecar.proc.wait(timeout=EXIT_TIMEOUT_S) == 0

    assert find_instance(library) is None
    assert not (library / ".tez" / "instance.json").exists()


def test_missing_library_without_create_is_reported(tmp_path: Path) -> None:
    library = tmp_path / "nowhere"

    with run_sidecar(TOKEN, "--library", str(library)) as sidecar:
        kind, data = sidecar.first_line()
        assert sidecar.proc.wait(timeout=EXIT_TIMEOUT_S) == EXIT_LIBRARY_ERROR

    assert kind == "TEZ_ERROR"
    assert data == {"code": "library.not_found", "params": {"path": str(library)}}
