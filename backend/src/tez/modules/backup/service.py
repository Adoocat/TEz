"""Backups of a whole library as one zip file, and restoring them (plan, Task 21).

A backup holds a consistent copy of the database, taken with SQLite's online backup API while
the app runs, the stored files (`files/`) and the raw search answers (`snapshots/`). A manifest
records the schema revision, counts and a SHA-256 of every entry. `derived/` is left out: it
can be produced again from the files.

Restoring never touches an open library. It unpacks into a new, empty folder, checks every
entry against the manifest and the database's own integrity, and only then opens the folder,
which also brings an older schema up to date.
"""

import hashlib
import json
import logging
import shutil
import sqlite3
import tempfile
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast

from tez import __version__
from tez.core.errors import ErrorCode, TezError
from tez.modules.jobs.registry import JobContext

logger = logging.getLogger(__name__)

BACKUP_JOB = "library.backup"
MANIFEST = "tez-backup.json"
FORMAT = 1
DATABASE_FILE = "library.sqlite"
BACKUP_FOLDER = "backups"
NAME_PREFIX = "TEz-backup-"
# Folders copied whole. PDFs are already compressed, so they are stored, not deflated.
_CONTENT_FOLDERS = ("files", "snapshots")
_STORED_SUFFIXES = frozenset({".pdf", ".gz", ".zip"})
_CHUNK = 1024 * 1024
_LIBRARY_FOLDERS = ("files", "derived", "snapshots", "backups", ".tez")

Progress = Callable[[float], None]


def _ignore(_: float) -> None:
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_database(source: Path, target: Path) -> None:
    """A consistent copy, even while another process writes (WAL)."""
    reader = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    writer = sqlite3.connect(target)
    try:
        reader.backup(writer)
    finally:
        writer.close()
        reader.close()


def _check_integrity(database: Path) -> None:
    connection = sqlite3.connect(database)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    finally:
        connection.close()
    if result is None or result[0] != "ok":
        detail = result[0] if result else "no answer"
        raise TezError(ErrorCode.BACKUP_DAMAGED, {"entry": DATABASE_FILE, "detail": detail})


def _database_facts(database: Path) -> dict[str, Any]:
    connection = sqlite3.connect(database)
    try:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        papers = connection.execute(
            "SELECT count(*) FROM paper WHERE library_added_at IS NOT NULL"
        ).fetchone()
        attachments = connection.execute("SELECT count(*) FROM attachment").fetchone()
    finally:
        connection.close()
    return {
        "schema_revision": revision[0] if revision else None,
        "papers": papers[0] if papers else 0,
        "attachments": attachments[0] if attachments else 0,
    }


def _content_files(library_path: Path) -> Iterator[tuple[Path, str]]:
    for folder in _CONTENT_FOLDERS:
        root = library_path / folder
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            # Half-written files (".part") belong to an operation still running.
            if path.is_file() and not path.name.startswith("."):
                yield path, path.relative_to(library_path).as_posix()


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    size: int
    created_at: datetime
    schema_revision: str | None
    papers: int | None
    attachments: int | None
    app_version: str | None


def create_backup(library_path: Path, *, report: Progress = _ignore) -> Path:
    """Write `backups/TEz-backup-<UTC time>.zip`; returns its path."""
    created = datetime.now(UTC)
    folder = library_path / BACKUP_FOLDER
    folder.mkdir(exist_ok=True)
    target = folder / f"{NAME_PREFIX}{created.strftime('%Y%m%dT%H%M%SZ')}.zip"
    partial = target.with_name(f".{target.name}.part")
    content = list(_content_files(library_path))
    total = sum(path.stat().st_size for path, _ in content) or 1
    done = 0
    with tempfile.TemporaryDirectory(dir=library_path / ".tez") as scratch:
        database = Path(scratch) / DATABASE_FILE
        _copy_database(library_path / DATABASE_FILE, database)
        _check_integrity(database)
        report(0.05)
        entries: list[dict[str, Any]] = [
            {"path": DATABASE_FILE, "size": database.stat().st_size, "sha256": _sha256(database)}
        ]
        try:
            with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(database, DATABASE_FILE)
                for path, name in content:
                    stored = path.suffix.lower() in _STORED_SUFFIXES
                    archive.write(path, name, compress_type=zipfile.ZIP_STORED if stored else None)
                    size = path.stat().st_size
                    entries.append({"path": name, "size": size, "sha256": _sha256(path)})
                    done += size
                    report(0.05 + 0.9 * done / total)
                manifest = {
                    "format": FORMAT,
                    "app_version": __version__,
                    "created_at": created.isoformat(timespec="seconds"),
                    **_database_facts(database),
                    "entries": entries,
                }
                archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
    report(1.0)
    logger.info("backup written", extra={"backup": str(target), "entries": len(entries)})
    return target


def _read_manifest(archive: zipfile.ZipFile) -> dict[str, Any]:
    try:
        manifest: Any = json.loads(archive.read(MANIFEST))
    except (KeyError, ValueError) as exc:
        raise TezError(ErrorCode.BACKUP_DAMAGED, {"entry": MANIFEST}) from exc
    if not isinstance(manifest, dict):
        raise TezError(ErrorCode.BACKUP_DAMAGED, {"entry": MANIFEST})
    found = cast(dict[str, Any], manifest)
    if found.get("format") != FORMAT:
        raise TezError(ErrorCode.BACKUP_UNSUPPORTED, {"format": found.get("format")})
    return found


def list_backups(library_path: Path) -> list[BackupInfo]:
    """The library's backup zips, newest first. An unreadable one is listed without details."""
    found: list[BackupInfo] = []
    for path in sorted((library_path / BACKUP_FOLDER).glob(f"{NAME_PREFIX}*.zip"), reverse=True):
        stat = path.stat()
        details: dict[str, Any] = {}
        try:
            with zipfile.ZipFile(path) as archive:
                details = _read_manifest(archive)
        except (TezError, zipfile.BadZipFile, OSError):
            logger.warning("unreadable backup", extra={"backup": str(path)}, exc_info=True)
        created = details.get("created_at")
        found.append(
            BackupInfo(
                path=path,
                size=stat.st_size,
                created_at=(
                    datetime.fromisoformat(created)
                    if isinstance(created, str)
                    else datetime.fromtimestamp(stat.st_mtime, UTC)
                ),
                schema_revision=details.get("schema_revision"),
                papers=details.get("papers"),
                attachments=details.get("attachments"),
                app_version=details.get("app_version"),
            )
        )
    return found


def _safe_name(name: str) -> PurePosixPath:
    """Entry names stay inside the target: no absolute paths, no "..", no drive letters."""
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or ":" in name or "\\" in name:
        raise TezError(ErrorCode.BACKUP_DAMAGED, {"entry": name})
    return path


@dataclass(frozen=True)
class RestoreResult:
    path: Path
    schema_revision: str | None
    papers: int
    attachments: int
    files: int


def restore_backup(backup: Path, target: Path) -> RestoreResult:
    """Unpack a backup into `target` (missing or empty) and check it. Nothing else changes."""
    target = target.absolute()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise TezError(ErrorCode.LIBRARY_NOT_EMPTY, {"path": str(target)}, status=409)
    try:
        archive = zipfile.ZipFile(backup)
    except (OSError, zipfile.BadZipFile) as exc:
        raise TezError(ErrorCode.BACKUP_DAMAGED, {"entry": backup.name}) from exc
    created_target = not target.exists()
    try:
        with archive:
            manifest = _read_manifest(archive)
            entries = cast(list[dict[str, Any]], manifest.get("entries") or [])
            for entry in entries:
                name = str(entry.get("path", ""))
                destination = target.joinpath(*_safe_name(name).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with archive.open(name) as source, destination.open("wb") as sink:
                        shutil.copyfileobj(source, sink, _CHUNK)
                except KeyError as exc:
                    raise TezError(ErrorCode.BACKUP_DAMAGED, {"entry": name}) from exc
                if _sha256(destination) != entry.get("sha256"):
                    raise TezError(ErrorCode.BACKUP_DAMAGED, {"entry": name})
        for folder in _LIBRARY_FOLDERS:
            (target / folder).mkdir(exist_ok=True)
        _check_integrity(target / DATABASE_FILE)
    except BaseException:
        # A half-restored folder is worse than none: take it away again.
        if created_target:
            shutil.rmtree(target, ignore_errors=True)
        else:
            for child in target.iterdir():
                shutil.rmtree(child) if child.is_dir() else child.unlink()
        raise
    facts = _database_facts(target / DATABASE_FILE)
    logger.info("backup restored", extra={"backup": str(backup), "target": str(target)})
    return RestoreResult(
        path=target,
        schema_revision=facts["schema_revision"],
        papers=facts["papers"],
        attachments=facts["attachments"],
        files=sum(1 for e in entries if str(e.get("path", "")).startswith("files/")),
    )


def backup_job(payload: dict[str, object], ctx: JobContext) -> None:
    """The `library.backup` job."""
    del payload
    create_backup(ctx.library_path, report=ctx.report)
