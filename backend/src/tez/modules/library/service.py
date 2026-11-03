"""Library folder: create, open exclusively, discover who has it open.

One process at a time owns a library: the desktop app's backend or a headless CLI command.
Ownership is an OS file lock on `.tez/lock`; `.tez/instance.json` says who the owner is and,
when it serves the API, where the CLI can reach it (plan, "Terminal ve sistem entegrasyonu").
"""

import logging
import os
import socket
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from tez import __version__
from tez.core import migrations
from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.core.filelock import FileLock, is_locked
from tez.core.private_file import write_private_text
from tez.modules.library.schemas import ApiEndpoint, Instance, InstanceKind, LibraryInfo

logger = logging.getLogger(__name__)

DATABASE_FILE = "library.sqlite"
LOCK_FILE = Path(".tez") / "lock"
INSTANCE_FILE = Path(".tez") / "instance.json"
_FOLDERS = ("files", "derived", "snapshots", "backups", ".tez")


class Library:
    """An open library. Holds the lock until `close()` (or until the process ends)."""

    def __init__(self, path: Path, db: Database, lock: FileLock, instance: Instance) -> None:
        self.path = path
        self.db = db
        self._lock = lock
        self._instance = instance

    def info(self) -> LibraryInfo:
        revision = migrations.current_revision(self.db)
        assert revision is not None
        return LibraryInfo(path=str(self.path), name=self.path.name, schema_revision=revision)

    def publish_api(self, *, url: str, token: str) -> None:
        """Let CLI commands find this process's API instead of opening the database."""
        self._instance = self._instance.model_copy(
            update={"api": ApiEndpoint(url=url, token=token)}
        )
        _write_instance(self.path, self._instance)

    def close(self) -> None:
        if not self._lock.held:
            return
        (self.path / INSTANCE_FILE).unlink(missing_ok=True)
        self.db.close()
        self._lock.release()
        logger.info("library closed", extra={"library": str(self.path)})


def create_library(path: Path) -> None:
    """Make a new, empty library in a folder that is missing or empty."""
    path = path.absolute()
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise TezError(ErrorCode.LIBRARY_NOT_EMPTY, {"path": str(path)}, status=409)
    for name in _FOLDERS:
        (path / name).mkdir(parents=True, exist_ok=True)
    db = Database(path / DATABASE_FILE)
    try:
        migrations.migrate(db)
    finally:
        db.close()
    logger.info("library created", extra={"library": str(path)})


def open_library(path: Path, *, kind: InstanceKind = "app", create: bool = False) -> Library:
    """Open a library exclusively, bringing its schema up to date.

    Raises `TezError` with `library.not_found`, `library.locked` (with who holds it) or
    `library.too_new`. With `create`, a missing or empty folder becomes a new library.
    """
    path = path.absolute()
    if create and (not path.exists() or (path.is_dir() and not any(path.iterdir()))):
        create_library(path)
    if not (path / DATABASE_FILE).is_file():
        raise TezError(ErrorCode.LIBRARY_NOT_FOUND, {"path": str(path)}, status=404)
    (path / ".tez").mkdir(exist_ok=True)

    lock = FileLock(path / LOCK_FILE)
    if not lock.try_acquire():
        raise _locked_error(path)

    db = Database(path / DATABASE_FILE)
    try:
        _upgrade_schema(path, db)
        instance = Instance(
            pid=os.getpid(),
            kind=kind,
            host=socket.gethostname(),
            started_at=datetime.now(UTC).isoformat(timespec="seconds"),
            version=__version__,
        )
        _write_instance(path, instance)
    except BaseException:
        db.close()
        lock.release()
        raise
    logger.info("library opened", extra={"library": str(path)})
    return Library(path, db, lock, instance)


def find_instance(path: Path) -> Instance | None:
    """Who has the library open, or None if nobody does.

    A leftover `instance.json` from a crashed process is ignored: only the lock counts.
    """
    path = path.absolute()
    if not is_locked(path / LOCK_FILE):
        return None
    instance = _read_instance(path)
    if instance is None:
        # Locked, but the owner has not written (or has just removed) its file.
        raise TezError(ErrorCode.LIBRARY_LOCKED, {"path": str(path)}, status=409)
    return instance


def _upgrade_schema(path: Path, db: Database) -> None:
    current = migrations.current_revision(db)
    if current is not None and not migrations.is_known_revision(current):
        raise TezError(
            ErrorCode.LIBRARY_TOO_NEW, {"path": str(path), "revision": current}, status=409
        )
    if current is not None and current != migrations.head_revision():
        _backup(path, current)
    migrations.migrate(db)


def _backup(path: Path, revision: str) -> Path:
    """Copy the database before a schema upgrade (SQLite online backup, WAL-safe)."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = path / "backups" / f"library-{revision}-{stamp}.sqlite"
    target.parent.mkdir(exist_ok=True)
    source = sqlite3.connect(path / DATABASE_FILE)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    logger.info("library backed up before upgrade", extra={"backup": str(target)})
    return target


def _locked_error(path: Path) -> TezError:
    params: dict[str, object] = {"path": str(path)}
    instance = _read_instance(path)
    if instance is not None:
        params |= {
            "pid": instance.pid,
            "kind": instance.kind,
            "host": instance.host,
            "since": instance.started_at,
        }
    return TezError(ErrorCode.LIBRARY_LOCKED, params, status=409)


def _write_instance(path: Path, instance: Instance) -> None:
    write_private_text(path / INSTANCE_FILE, instance.model_dump_json(indent=2) + "\n")


def _read_instance(path: Path) -> Instance | None:
    try:
        return Instance.model_validate_json((path / INSTANCE_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValidationError):
        logger.warning("unreadable instance file", extra={"library": str(path)}, exc_info=True)
        return None
