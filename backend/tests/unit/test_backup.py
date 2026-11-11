"""Task 21 acceptance: a library restored from its backup is the same library.

Damaged or hostile backups are refused, and nothing half-restored is left behind.
"""

import base64
import json
import zipfile
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tests.pdfs import make_pdf
from tez.__main__ import main
from tez.core.config import Settings
from tez.core.errors import ErrorCode, TezError
from tez.main import create_app
from tez.modules.backup.service import (
    MANIFEST,
    create_backup,
    list_backups,
    restore_backup,
)
from tez.modules.jobs.handlers import registry
from tez.modules.library.service import Library, open_library
from tez.modules.settings.secrets import MemorySecretStore
from tez.worker import Worker

RIS = b"""TY  - JOUR
TI  - Automated Code Review with Large Language Models
AU  - Y\xc4\xb1lmaz, Ay\xc5\x9fe
PY  - 2024
DO  - 10.1109/tse.2024.1
ER  -
"""


def make_client(library: Library) -> TestClient:
    app = create_app(
        token=TOKEN, settings=Settings(), library=library, secret_store=MemorySecretStore()
    )
    return TestClient(app, headers=AUTH, raise_server_exceptions=False)


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    """A library with a bit of everything: an imported search run, a PDF, a collection."""
    opened = open_library(tmp_path / "lib", create=True)
    with make_client(opened) as client:
        review = client.post("/reviews", json={"title": "SLR", "method": "prisma2020"}).json()
        client.post(
            "/imports",
            json={
                "file_name": "scopus.ris",
                "content_base64": base64.b64encode(RIS).decode(),
                "review_id": review["id"],
                "log": {"source": "Scopus"},
                "add_to_library": True,
            },
        )
        client.post(
            "/pdfs",
            params={"file_name": "paper.pdf"},
            content=make_pdf(3),
            headers={"Content-Type": "application/pdf"},
        )
        collection = client.post("/collections", json={"name": "Tez"}).json()
        paper_ids = [p["id"] for p in client.get("/papers").json()]
        client.post(f"/collections/{collection['id']}/papers", json={"paper_ids": paper_ids})
    yield open_library(tmp_path / "lib")


def snapshot(library: Library) -> dict[str, object]:
    with make_client(library) as client:
        return {
            "papers": sorted((p["title"], p["citekey"]) for p in client.get("/papers").json()),
            "collections": [
                (c["name"], c["paper_count"]) for c in client.get("/collections").json()
            ],
            "search": client.get("/papers/search", params={"q": "yilmaz"}).json()["paper_ids"],
            "runs": len(client.get("/searches", params={"review_id": _review(client)}).json()),
        }


def _review(client: TestClient) -> str:
    return client.get("/reviews").json()[0]["id"]


def test_task_21_acceptance_a_restored_backup_is_the_same_library(
    library: Library, tmp_path: Path
) -> None:
    before = snapshot(library)
    files_before = {
        p.relative_to(library.path).as_posix(): p.read_bytes()
        for p in (library.path / "files").rglob("*.pdf")
    }

    backup = create_backup(library.path)
    library.close()
    restored = restore_backup(backup, tmp_path / "restored")

    assert (restored.papers, restored.attachments, restored.files) == (2, 1, 1)
    reopened = open_library(tmp_path / "restored")
    assert snapshot(reopened) == before
    files_after = {
        p.relative_to(reopened.path).as_posix(): p.read_bytes()
        for p in (reopened.path / "files").rglob("*.pdf")
    }
    assert files_after == files_before
    assert list((reopened.path / "snapshots").glob("*.json.gz"))
    reopened.close()


def test_a_backup_holds_a_manifest_with_checksums(library: Library) -> None:
    backup = create_backup(library.path)

    with zipfile.ZipFile(backup) as archive:
        manifest = json.loads(archive.read(MANIFEST))
        names = set(archive.namelist())
        pdf_entry = next(i for i in archive.infolist() if i.filename.endswith(".pdf"))
    assert manifest["format"] == 1
    assert manifest["schema_revision"] is not None
    assert (manifest["papers"], manifest["attachments"]) == (2, 1)
    assert {e["path"] for e in manifest["entries"]} | {MANIFEST} == names
    assert pdf_entry.compress_type == zipfile.ZIP_STORED
    assert not any(name.startswith(("derived/", ".tez/", "backups/")) for name in names)
    library.close()


def test_backups_are_listed_newest_first(library: Library) -> None:
    first = create_backup(library.path)
    second = first.with_name(first.name.replace("Z.zip", "Y.zip"))  # sorts after
    first.rename(second)
    create_backup(library.path)

    listed = list_backups(library.path)

    assert len(listed) == 2
    assert listed[0].papers == 2
    library.close()


def tamper(backup: Path, target: Path, change: dict[str, bytes]) -> Path:
    """A copy of `backup` with some entries replaced."""
    with zipfile.ZipFile(backup) as source, zipfile.ZipFile(target, "w") as sink:
        for info in source.infolist():
            sink.writestr(info, change.get(info.filename, source.read(info.filename)))
        for name, data in change.items():
            if name not in source.namelist():
                sink.writestr(name, data)
    return target


def test_a_damaged_file_is_refused_and_nothing_is_left(library: Library, tmp_path: Path) -> None:
    backup = create_backup(library.path)
    with zipfile.ZipFile(backup) as archive:
        pdf = next(name for name in archive.namelist() if name.endswith(".pdf"))
    damaged = tamper(backup, tmp_path / "damaged.zip", {pdf: b"%PDF-1.4 not the same"})

    with pytest.raises(TezError) as caught:
        restore_backup(damaged, tmp_path / "restored")

    assert caught.value.code is ErrorCode.BACKUP_DAMAGED
    assert caught.value.params == {"entry": pdf}
    assert not (tmp_path / "restored").exists()
    library.close()


def test_an_entry_escaping_the_folder_is_refused(library: Library, tmp_path: Path) -> None:
    backup = create_backup(library.path)
    with zipfile.ZipFile(backup) as archive:
        manifest = json.loads(archive.read(MANIFEST))
    manifest["entries"].append({"path": "../evil.txt", "size": 1, "sha256": "0" * 64})
    hostile = tamper(backup, tmp_path / "hostile.zip", {MANIFEST: json.dumps(manifest).encode()})

    with pytest.raises(TezError) as caught:
        restore_backup(hostile, tmp_path / "restored")

    assert caught.value.code is ErrorCode.BACKUP_DAMAGED
    assert not (tmp_path / "evil.txt").exists()
    library.close()


def test_restore_needs_an_empty_folder_and_a_backup(library: Library, tmp_path: Path) -> None:
    backup = create_backup(library.path)
    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "x.txt").write_text("keep me", encoding="utf-8")

    with pytest.raises(TezError) as caught:
        restore_backup(backup, busy)
    assert caught.value.code is ErrorCode.LIBRARY_NOT_EMPTY
    assert (busy / "x.txt").read_text(encoding="utf-8") == "keep me"

    not_zip = tmp_path / "not.zip"
    not_zip.write_bytes(b"hello")
    with pytest.raises(TezError) as caught:
        restore_backup(not_zip, tmp_path / "other")
    assert caught.value.code is ErrorCode.BACKUP_DAMAGED
    library.close()


def test_the_api_backs_up_in_the_background(library: Library) -> None:
    with make_client(library) as client:
        started = client.post("/backups")
        assert started.status_code == 202
        worker = Worker(library.db, registry, lease=timedelta(seconds=30))
        while worker.run_once():
            pass

        job = client.get(f"/jobs/{started.json()['job_id']}").json()
        assert (job["status"], job["progress"]) == ("done", 1.0)
        (listed,) = client.get("/backups").json()
        assert listed["file_name"].startswith("TEz-backup-")
        assert (listed["papers"], listed["attachments"]) == (2, 1)


def test_the_restore_command_restores_and_migrates(
    library: Library, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = create_backup(library.path)
    library.close()

    with pytest.raises(SystemExit) as exited:
        main(["restore", str(backup), str(tmp_path / "restored")])

    assert exited.value.code == 0
    assert "restored 2 papers and 1 files" in capsys.readouterr().out
    with pytest.raises(SystemExit) as again:
        main(["restore", str(backup), str(tmp_path / "restored")])
    assert again.value.code == 3
    assert "library.not_empty" in capsys.readouterr().err
