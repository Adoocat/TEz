import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from tez.core import migrations
from tez.core.errors import ErrorCode, TezError
from tez.modules.library.service import (
    INSTANCE_FILE,
    Library,
    create_library,
    find_instance,
    open_library,
)

LIBRARY_DIRS = ("files", "derived", "snapshots", "backups", ".tez")


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "TEz Library"


@pytest.fixture
def library(path: Path) -> Iterator[Library]:
    create_library(path)
    lib = open_library(path)
    yield lib
    lib.close()


def error_code(exc: pytest.ExceptionInfo[TezError]) -> ErrorCode:
    return exc.value.code


# --- create / open ---------------------------------------------------------------------


def test_create_builds_the_folder_layout(path: Path) -> None:
    create_library(path)

    assert (path / "library.sqlite").is_file()
    for name in LIBRARY_DIRS:
        assert (path / name).is_dir(), name


def test_create_in_an_existing_empty_folder(path: Path) -> None:
    path.mkdir()

    create_library(path)

    assert (path / "library.sqlite").is_file()


def test_create_refuses_a_non_empty_folder(path: Path) -> None:
    path.mkdir()
    (path / "thesis.docx").write_bytes(b"x")

    with pytest.raises(TezError) as exc:
        create_library(path)

    assert error_code(exc) is ErrorCode.LIBRARY_NOT_EMPTY
    assert not (path / "library.sqlite").exists()


def test_open_migrates_to_the_latest_schema(library: Library) -> None:
    assert library.info().schema_revision == migrations.head_revision()


@pytest.mark.parametrize("make", ["missing", "empty_folder", "other_folder"])
def test_open_something_that_is_not_a_library(path: Path, make: str) -> None:
    if make != "missing":
        path.mkdir()
    if make == "other_folder":
        (path / "notes.txt").write_text("hi", encoding="utf-8")

    with pytest.raises(TezError) as exc:
        open_library(path)

    assert error_code(exc) is ErrorCode.LIBRARY_NOT_FOUND
    assert exc.value.params == {"path": str(path)}


def test_open_with_create_makes_a_missing_library(path: Path) -> None:
    lib = open_library(path, create=True)
    try:
        assert (path / "library.sqlite").is_file()
    finally:
        lib.close()


def test_info(library: Library, path: Path) -> None:
    info = library.info()

    assert info.path == str(path)
    assert info.name == "TEz Library"


def test_path_with_turkish_letters(tmp_path: Path) -> None:
    path = tmp_path / "Doktora Tezi — Şükrü İğdır"
    lib = open_library(path, create=True)
    try:
        assert lib.info().name == "Doktora Tezi — Şükrü İğdır"
    finally:
        lib.close()


# --- lock (acceptance: a second open gives a clear error) ------------------------------


def test_second_open_is_refused_with_who_holds_it(library: Library, path: Path) -> None:
    with pytest.raises(TezError) as exc:
        open_library(path)

    assert error_code(exc) is ErrorCode.LIBRARY_LOCKED
    assert exc.value.status == 409
    params = exc.value.params
    assert params["path"] == str(path)
    assert params["pid"] == os.getpid()
    assert params["kind"] == "app"
    assert params["host"]
    assert params["since"]


def test_refused_open_leaves_the_first_one_intact(library: Library, path: Path) -> None:
    with pytest.raises(TezError):
        open_library(path)

    instance = find_instance(path)
    assert instance is not None
    assert instance.pid == os.getpid()


def test_close_releases_the_lock(library: Library, path: Path) -> None:
    library.close()

    again = open_library(path)
    again.close()


def test_close_is_idempotent(library: Library) -> None:
    library.close()
    library.close()


def test_lock_is_released_when_the_holder_process_dies(path: Path) -> None:
    create_library(path)
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import os, sys, pathlib\n"
            "from tez.modules.library.service import open_library\n"
            "library = open_library(pathlib.Path(sys.argv[1]))\n"
            "print(os.getpid(), flush=True)\n"
            "sys.stdin.read()\n",
            str(path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        # The interpreter's own pid: on Windows a venv python.exe is a launcher process.
        holder_pid = int(holder.stdout.readline())
        with pytest.raises(TezError) as exc:
            open_library(path)
        assert exc.value.params["pid"] == holder_pid
        # A hard kill: no clean-up runs, so only the OS can release the lock.
        os.kill(holder_pid, getattr(signal, "SIGKILL", signal.SIGTERM))
        _wait_until_gone(holder_pid)
    finally:
        holder.kill()
        holder.wait()
        for pipe in (holder.stdin, holder.stdout):
            if pipe is not None:
                pipe.close()

    assert (path / INSTANCE_FILE).exists()  # stale file left behind by the crash
    assert find_instance(path) is None  # ...and ignored, because nobody holds the lock
    lib = open_library(path)
    try:
        instance = find_instance(path)
        assert instance is not None
        assert instance.pid == os.getpid()
    finally:
        lib.close()


def _wait_until_gone(pid: int, timeout_s: float = 10) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _alive(pid):
            return
        time.sleep(0.05)
    pytest.fail(f"process {pid} did not exit")


def _alive(pid: int) -> bool:
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True
        ).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


# --- discovery file -------------------------------------------------------------------


def test_closed_library_has_no_instance(path: Path) -> None:
    create_library(path)

    assert find_instance(path) is None


def test_instance_without_api(library: Library, path: Path) -> None:
    instance = find_instance(path)

    assert instance is not None
    assert instance.kind == "app"
    assert instance.api is None


def test_instance_with_api_lets_the_cli_connect(library: Library, path: Path) -> None:
    library.publish_api(url="http://127.0.0.1:51234", token="secret-token")

    instance = find_instance(path)

    assert instance is not None
    assert instance.api is not None
    assert instance.api.url == "http://127.0.0.1:51234"
    assert instance.api.token == "secret-token"


def test_close_removes_the_instance_file(library: Library, path: Path) -> None:
    library.close()

    assert not (path / INSTANCE_FILE).exists()


def test_instance_file_is_readable_only_by_the_user(library: Library, path: Path) -> None:
    library.publish_api(url="http://127.0.0.1:51234", token="secret-token")
    instance_file = path / INSTANCE_FILE

    if sys.platform == "win32":
        acl = subprocess.run(
            ["icacls", str(instance_file)], capture_output=True, text=True, check=True
        ).stdout
        entries = [line for line in acl.splitlines() if ":(" in line]
        assert len(entries) == 1, acl  # only the current user; inheritance removed
        assert "(I)" not in acl
        assert os.environ["USERNAME"].lower() in entries[0].lower()
    else:
        assert instance_file.stat().st_mode & 0o777 == 0o600


def test_instance_file_is_valid_json(library: Library, path: Path) -> None:
    data = json.loads((path / INSTANCE_FILE).read_text(encoding="utf-8"))

    assert data["pid"] == os.getpid()
    assert data["version"]
    assert data["started_at"].endswith("+00:00")


# --- schema versions ------------------------------------------------------------------


def stamp(path: Path, revision: str) -> None:
    with sqlite3.connect(path / "library.sqlite") as conn:
        conn.execute("UPDATE alembic_version SET version_num = ?", (revision,))
    conn.close()


def test_library_from_a_newer_tez_is_refused(path: Path) -> None:
    create_library(path)
    stamp(path, "9999")

    with pytest.raises(TezError) as exc:
        open_library(path)

    assert error_code(exc) is ErrorCode.LIBRARY_TOO_NEW
    assert exc.value.params["revision"] == "9999"
    # Refused before taking over: the lock is free again.
    assert find_instance(path) is None


@pytest.fixture
def newer_migrations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[], str]:
    """Installs a copy of the real migrations plus one more revision, as a TEz update would."""

    def install() -> str:
        return _install_newer_migrations(tmp_path, monkeypatch)

    return install


def _install_newer_migrations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    scripts = tmp_path / "scripts"
    shutil.copytree(
        migrations.MIGRATIONS_DIR, scripts, ignore=shutil.ignore_patterns("__pycache__")
    )
    (scripts / "versions" / "9001_next.py").write_text(
        'revision = "9001"\n'
        f"down_revision = {migrations.head_revision()!r}\n"
        "branch_labels = None\n"
        "depends_on = None\n"
        "from alembic import op\n"
        "def upgrade():\n"
        '    op.execute("CREATE TABLE added_later (id INTEGER)")\n'
        "def downgrade():\n"
        '    op.execute("DROP TABLE added_later")\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(migrations, "MIGRATIONS_DIR", scripts)
    return "9001"


def test_upgrade_takes_a_backup_first(path: Path, newer_migrations: Callable[[], str]) -> None:
    old_head = migrations.head_revision()
    create_library(path)
    new_head = newer_migrations()

    lib = open_library(path)
    try:
        assert lib.info().schema_revision == new_head
    finally:
        lib.close()

    (backup,) = (path / "backups").iterdir()
    assert backup.name.startswith(f"library-{old_head}-")
    assert backup.suffix == ".sqlite"
    with sqlite3.connect(backup) as conn:
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    conn.close()
    assert version == (old_head,)
    assert "added_later" not in tables


def test_no_backup_when_already_current(library: Library, path: Path) -> None:
    library.close()

    open_library(path).close()

    assert list((path / "backups").iterdir()) == []
