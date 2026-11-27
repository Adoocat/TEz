"""Task 56: sections and references read by GROBID, an optional service on this computer.

Acceptance: tests use a recorded response (no network); without GROBID nothing breaks. The
answer below has the shape GROBID 0.8 gives with head and biblStruct coordinates.
"""

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tests.pdfs import make_text_pdf
from tez.core.config import Settings
from tez.core.errors import ErrorCode, TezError
from tez.main import create_app
from tez.modules.jobs.handlers import registry
from tez.modules.library.models import IdentifierScheme
from tez.modules.library.paper_service import PaperService
from tez.modules.library.repository import LibraryRepository
from tez.modules.library.service import Library, open_library
from tez.modules.settings.secrets import MemorySecretStore
from tez.modules.structure import grobid, tei
from tez.worker import Worker

RECORDED = (Path(__file__).parent.parent / "fixtures" / "grobid" / "storks.tei.xml").read_text(
    encoding="utf-8"
)


class Recorded:
    """GROBID's answer, recorded; remembers what it was sent."""

    def __init__(self, answer: str | TezError = RECORDED) -> None:
        self.answer = answer
        self.sent: list[bytes] = []

    def process(self, pdf: bytes) -> str:
        self.sent.append(pdf)
        if isinstance(self.answer, TezError):
            raise self.answer
        return self.answer


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


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Recorded:
    recorded = Recorded()
    urls: list[str] = []

    def client_for(url: str) -> Recorded:
        urls.append(url)
        return recorded

    monkeypatch.setattr(grobid, "client_for", client_for)
    return recorded


def run_jobs(library: Library) -> None:
    worker = Worker(library.db, registry, lease=timedelta(seconds=30))
    while worker.run_once():
        pass


def upload(client: TestClient, library: Library) -> str:
    made = client.post(
        "/pdfs", params={"file_name": "storks.pdf"}, content=make_text_pdf([["Leylekler"]])
    )
    assert made.status_code == 201, made.text
    run_jobs(library)
    return made.json()["attachment_id"]


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


# --- reading the answer ----------------------------------------------------------------------


def test_sections_with_their_types_and_pages() -> None:
    found = tei.parse(RECORDED)
    assert [(s.type, s.heading, s.page_start, s.page_end) for s in found.sections] == [
        ("abstract", "Abstract", 1, 1),
        ("intro", "1. Giriş", 1, 2),
        ("method", "2. Yöntem", 2, 3),
        ("results", "3. Bulgular", 3, 5),
        ("discussion", "4. Tartışma ve Sonuç", 5, 5),
        ("other", "Teşekkür", None, None),
    ]


def test_references_with_what_grobid_read() -> None:
    first, second = tei.parse(RECORDED).references
    assert first.title == "White stork nesting on chimneys"
    assert first.authors == ["Ayşe Yılmaz", "John Smith"]
    assert (first.year, first.doi, first.page) == (2019, "10.5555/stork.2019.7", 6)
    assert first.raw_text.startswith("Yılmaz, A., Smith, J. (2019).")
    assert (second.title, second.year, second.doi, second.authors) == (
        "Kuşların göçü",
        2008,
        None,
        ["Mehmet Kaya"],
    )


@pytest.mark.parametrize(
    ("heading", "kind"),
    [
        ("2.1 Materials and Methods", "method"),
        ("ARAŞTIRMA DESENİ", "method"),
        ("Findings", "results"),
        ("SINIRLILIKLAR", "discussion"),
        ("Background", "intro"),
        ("Ekler", "other"),
    ],
)
def test_section_types_in_turkish_and_english(heading: str, kind: str) -> None:
    assert tei.section_type(heading) == kind


def test_not_tei_is_refused() -> None:
    with pytest.raises(ValueError, match="TEI"):
        tei.parse("<html>Service Unavailable")


# --- off by default, and nothing breaks ------------------------------------------------------


def test_without_grobid_it_is_off(client: TestClient, library: Library) -> None:
    attachment = upload(client, library)
    assert ok(client.get("/grobid")) == {"configured": False}
    refused = client.post(f"/attachments/{attachment}/structure")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "grobid.off"
    empty = ok(client.get(f"/attachments/{attachment}/structure"))
    assert empty == {"read_at": None, "error": None, "sections": [], "references": []}


@pytest.mark.parametrize(
    "url",
    [
        "http://lab.example.edu:8070",
        "https://192.168.1.5:8070",
        "ftp://localhost:8070",
        "localhost",
    ],
)
def test_only_an_address_on_this_computer_is_taken(client: TestClient, url: str) -> None:
    assert client.patch("/settings", json={"grobid_url": url}).status_code == 422


# --- reading a paper ---------------------------------------------------------------------------


def test_a_paper_is_read_and_its_references_matched(
    client: TestClient, library: Library, fake: Recorded
) -> None:
    with library.db.write_session() as session:
        cited = LibraryRepository(session).add_paper(
            "White stork nesting on chimneys",
            year=2019,
            identifiers=[(IdentifierScheme.DOI, "10.5555/stork.2019.7")],
        )
        PaperService(session).keep([cited.id])
    attachment = upload(client, library)
    ok(client.patch("/settings", json={"grobid_url": "http://localhost:8070"}))
    assert ok(client.get("/grobid")) == {"configured": True}

    queued = ok(client.post(f"/attachments/{attachment}/structure"), 202)
    assert queued["job_id"]
    run_jobs(library)

    assert len(fake.sent) == 1 and fake.sent[0].startswith(b"%PDF")
    read = ok(client.get(f"/attachments/{attachment}/structure"))
    assert read["read_at"] is not None and read["error"] is None
    assert [s["heading"] for s in read["sections"]][:3] == ["Abstract", "1. Giriş", "2. Yöntem"]
    references = read["references"]
    assert [r["matched_paper_id"] for r in references] == [cited.id, None]
    assert references[1]["title"] == "Kuşların göçü"

    # Reading again replaces what was read.
    ok(client.post(f"/attachments/{attachment}/structure"), 202)
    run_jobs(library)
    assert len(ok(client.get(f"/attachments/{attachment}/structure"))["sections"]) == 6


def test_grobid_gone_is_recorded_not_raised(
    client: TestClient, library: Library, fake: Recorded
) -> None:
    attachment = upload(client, library)
    ok(client.patch("/settings", json={"grobid_url": "http://127.0.0.1:8070"}))
    fake.answer = TezError(ErrorCode.GROBID_UNREACHABLE, {"url": "http://127.0.0.1:8070"})
    ok(client.post(f"/attachments/{attachment}/structure"), 202)
    run_jobs(library)
    read = ok(client.get(f"/attachments/{attachment}/structure"))
    assert (read["read_at"], read["error"], read["sections"]) == (None, "grobid.unreachable", [])
    # The rest of the app does not notice.
    assert ok(client.get(f"/attachments/{attachment}"))["id"] == attachment

    # A garbled answer is recorded as a failure too.
    fake.answer = "<html>Service Unavailable"
    ok(client.post(f"/attachments/{attachment}/structure"), 202)
    run_jobs(library)
    assert ok(client.get(f"/attachments/{attachment}/structure"))["error"] == "grobid.failed"


def test_the_http_client_says_why_it_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    def refused(*_: object, **__: object) -> None:
        raise httpx2.ConnectError("refused")

    monkeypatch.setattr(httpx2, "post", refused)
    with pytest.raises(TezError) as caught:
        grobid.HttpGrobid("http://localhost:8070/").process(b"%PDF")
    assert caught.value.code is ErrorCode.GROBID_UNREACHABLE

    def busy(*_: object, **__: object) -> httpx2.Response:
        return httpx2.Response(503, text="busy")

    monkeypatch.setattr(httpx2, "post", busy)
    with pytest.raises(TezError) as caught:
        grobid.HttpGrobid("http://localhost:8070").process(b"%PDF")
    assert (caught.value.code, caught.value.params) == (ErrorCode.GROBID_FAILED, {"status": 503})
