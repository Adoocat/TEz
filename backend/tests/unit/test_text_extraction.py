"""Task 43 acceptance: broken, encrypted and scanned PDFs are marked and crash nothing; running
the same job twice does not duplicate text; files added before this task are read too."""

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from tests.conftest import AUTH, TOKEN
from tests.pdfs import broken_pdf, encrypted_pdf, make_pdf, make_text_pdf
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.files import service as files_service
from tez.modules.files.models import Attachment
from tez.modules.fulltext import extraction
from tez.modules.fulltext import service as fulltext_service
from tez.modules.fulltext.extraction import clean_char, extract_pages, readable
from tez.modules.fulltext.models import TextChunk
from tez.modules.fulltext.repository import FulltextRepository
from tez.modules.jobs.handlers import registry
from tez.modules.jobs.models import JobStatus, ProcessingJob
from tez.modules.jobs.registry import JobContext
from tez.modules.library.service import Library, open_library
from tez.modules.settings.secrets import MemorySecretStore
from tez.worker import Worker


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    opened = open_library(tmp_path / "lib", create=True)
    yield opened
    opened.close()


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(
        token=TOKEN, settings=Settings(), library=library, secret_store=MemorySecretStore()
    )
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


def add(library: Library, data: bytes, name: str = "paper.pdf") -> str:
    return files_service.add_pdf(library.db, library.path, data, name).attachment_id


def run_jobs(library: Library) -> None:
    worker = Worker(library.db, registry, lease=timedelta(seconds=30))
    while worker.run_once():
        pass


def pages(library: Library, attachment_id: str) -> list[str]:
    with library.db.session() as session:
        return [chunk.text for chunk in FulltextRepository(session).pages(attachment_id)]


def test_every_page_is_read_in_order(library: Library) -> None:
    attachment = add(library, make_text_pdf([["İstanbul'da ışık", "iki satır"], ["Second page"]]))

    run_jobs(library)

    first, second = pages(library, attachment)
    assert readable(first) == "İstanbul'da ışık\niki satır"
    assert readable(second) == "Second page"
    with library.db.session() as session:
        rows = FulltextRepository(session).pages(attachment)
        assert [(r.page_index, r.ord, r.char_start, r.char_end) for r in rows] == [
            (0, 0, 0, len(first)),
            (1, 1, 0, len(second)),
        ]


def test_running_the_job_twice_does_not_duplicate_the_text(library: Library) -> None:
    attachment = add(library, make_text_pdf([["One"], ["Two"]]))
    run_jobs(library)
    before = pages(library, attachment)

    with library.db.write_session() as session:
        files_service.queue_extraction(session, attachment)
    run_jobs(library)

    assert pages(library, attachment) == before
    with library.db.session() as session:
        assert session.query(TextChunk).count() == 2


def test_a_scanned_pdf_is_marked_and_has_empty_pages(client: TestClient, library: Library) -> None:
    attachment = add(library, make_pdf(2, text=None), "scan.pdf")

    run_jobs(library)

    assert client.get(f"/attachments/{attachment}").json()["text_status"] == "needs_ocr"
    assert [text.strip() for text in pages(library, attachment)] == ["", ""]


def test_text_after_the_first_pages_still_counts(client: TestClient, library: Library) -> None:
    # The inspection looks at three pages; a thesis can open with more scanned ones.
    attachment = add(library, make_text_pdf([[], [], [], [], ["Text at last"]]))

    run_jobs(library)

    assert client.get(f"/attachments/{attachment}").json()["text_status"] == "ok"


@pytest.mark.parametrize(
    ("data", "code"), [(broken_pdf(), "pdf.unreadable"), (encrypted_pdf(), "pdf.encrypted")]
)
def test_a_file_that_does_not_open_is_marked_and_the_next_one_works(
    client: TestClient, library: Library, data: bytes, code: str
) -> None:
    bad = add(library, data, "bad.pdf")
    good = add(library, make_text_pdf([["Fine"]]), "good.pdf")

    run_jobs(library)

    view = client.get(f"/attachments/{bad}").json()
    assert (view["text_status"], view["error"]["code"]) == ("failed", code)
    assert pages(library, bad) == []
    assert [readable(t) for t in pages(library, good)] == ["Fine"]
    with library.db.session() as session:
        assert all(j.status is JobStatus.DONE for j in session.query(ProcessingJob))


def test_a_file_lost_before_extraction_is_marked(client: TestClient, library: Library) -> None:
    attachment = add(library, make_text_pdf([["Here"]]))
    run_jobs(library)
    for path in (library.path / "files").rglob("*.pdf"):
        path.unlink()
    with library.db.write_session() as session:
        files_service.queue_extraction(session, attachment)

    run_jobs(library)

    assert client.get(f"/attachments/{attachment}").json()["error"]["code"] == "pdf.missing"


def test_a_file_that_crashes_the_worker_is_marked_on_its_last_attempt(
    client: TestClient, library: Library, monkeypatch: pytest.MonkeyPatch
) -> None:
    attachment = add(library, make_text_pdf([["Crash"]]))

    class ProcessDied(BaseException):
        """Stands in for PDFium taking the process down: nothing after it runs."""

    def crash(*_: object, **__: object) -> None:
        raise ProcessDied

    monkeypatch.setattr(fulltext_service, "extract_pages", crash)
    ctx = JobContext("job", db=library.db, attempt=3, max_attempts=3)
    with pytest.raises(ProcessDied):
        fulltext_service.extract_text({"attachment_id": attachment}, ctx)

    view = client.get(f"/attachments/{attachment}").json()
    assert view["error"] == {"code": "pdf.crashed", "params": {"attempts": 3}}


def test_a_page_that_cannot_be_read_is_empty_and_the_others_stay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "three.pdf"
    path.write_bytes(make_text_pdf([["One"], ["Two"], ["Three"]]))
    real = extraction._page_text  # pyright: ignore[reportPrivateUsage]

    def fail_on_second(document: object, index: int) -> str:
        if index == 1:
            raise extraction.PdfiumError("broken page")
        return real(document, index)

    monkeypatch.setattr(extraction, "_page_text", fail_on_second)

    found = extract_pages(path)

    assert found is not None
    assert [readable(page.text) for page in found] == ["One", "", "Three"]


def test_a_job_taken_away_writes_nothing(library: Library) -> None:
    attachment = add(library, make_text_pdf([["One"], ["Two"]]))
    ctx = JobContext("job", db=library.db)
    ctx.cancel()

    fulltext_service.extract_text({"attachment_id": attachment}, ctx)

    assert pages(library, attachment) == []


def test_files_added_before_are_read_when_the_library_opens(tmp_path: Path) -> None:
    path = tmp_path / "lib"
    library = open_library(path, create=True)
    old = add(library, make_text_pdf([["Old paper"]]), "old.pdf")
    failed = add(library, broken_pdf(), "bad.pdf")
    run_jobs(library)
    with library.db.write_session() as session:
        session.execute(update(Attachment).values(text_version=None))
        session.query(TextChunk).delete()
    library.close()

    library = open_library(path)
    run_jobs(library)

    assert [readable(t) for t in pages(library, old)] == ["Old paper"]
    assert pages(library, failed) == []
    library.close()
    # Read by the current extractor: nothing to queue the next time.
    library = open_library(path)
    with library.db.session() as session:
        active = session.query(ProcessingJob).filter_by(status=JobStatus.QUEUED).count()
    assert active == 0
    library.close()


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_a_rotated_page_reads_in_order(tmp_path: Path, angle: int) -> None:
    path = tmp_path / "rotated.pdf"
    lines = ["First line of the page", "second line follows", "third line ends"]
    path.write_bytes(make_text_pdf([lines], rotate=angle))

    found = extract_pages(path)

    assert found is not None
    assert readable(found[0].text) == "\n".join(lines)


def test_ligature_codes_without_a_unicode_map_are_repaired(tmp_path: Path) -> None:
    path = tmp_path / "t1.pdf"
    path.write_bytes(make_text_pdf([["e\x1ecient o\x1ece \x1cndings"]], raw_codes=True))

    found = extract_pages(path)

    assert found is not None
    assert readable(found[0].text) == "efficient office findings"


@pytest.mark.parametrize("code", [0, 0x02, 0x07, 0xD800, 0xFFFE, 0x110000, 0x1F600, 65])
def test_every_code_becomes_one_storable_character(code: int) -> None:
    char = clean_char(code)

    assert len(char) == 1
    char.encode("utf-8")


def test_readable_joins_broken_words_and_spaces() -> None:
    text = "inter­\r\ndisciplinary  ofﬁce\r\n\r\n  next   line "

    assert readable(text) == "interdisciplinary office\nnext line"
