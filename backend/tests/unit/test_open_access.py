"""Task 17: open-access PDFs are found (arXiv, Unpaywall, the source's link) and downloaded as a
background job whose progress the UI follows. No network: HTTP goes to a mock transport.

The Unpaywall answers here follow its documented v2 schema (best_oa_location, oa_locations,
url_for_pdf); see ADR 0012.
"""

import asyncio
from collections.abc import Callable, Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tests.pdfs import make_pdf
from tez.core.config import Settings
from tez.core.errors import ErrorCode, TezError
from tez.main import create_app
from tez.modules.files import open_access
from tez.modules.files.models import Attachment
from tez.modules.files.open_access import Candidate, PaperRef, find_and_store
from tez.modules.jobs.handlers import registry
from tez.modules.jobs.models import JobStatus, ProcessingJob
from tez.modules.jobs.registry import JobFailed
from tez.modules.library.models import IdentifierScheme, Paper
from tez.modules.library.paper_service import PaperService
from tez.modules.library.service import Library, open_library
from tez.modules.settings import service as settings_service
from tez.modules.settings.schemas import SettingsPatch
from tez.modules.settings.secrets import MemorySecretStore
from tez.shared.http import HttpClient, SourcePolicy
from tez.worker import Worker

PDF = make_pdf(2, tag="oa")
LANDING_PAGE = b"<!doctype html><html><body>Sign in to read</body></html>"
DOI = "10.1145/3597503.3639187"


def unpaywall_answer(*pdf_urls: str | None) -> dict[str, Any]:
    locations = [
        {"url": "https://landing", "url_for_pdf": url, "host_type": "repository"}
        for url in pdf_urls
    ]
    return {
        "doi": DOI,
        "is_oa": bool(locations),
        "best_oa_location": locations[0] if locations else None,
        "oa_locations": locations,
    }


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    opened = open_library(tmp_path / "lib", create=True)
    yield opened
    opened.close()  # The app closes it too when a test uses the client; twice is harmless.


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(
        token=TOKEN, settings=Settings(), library=library, secret_store=MemorySecretStore()
    )
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


def add_paper(
    library: Library, *, doi: str | None = None, arxiv: str | None = None, oa_url: str | None = None
) -> str:
    identifiers: dict[IdentifierScheme, str] = {}
    if doi:
        identifiers[IdentifierScheme.DOI] = doi
    if arxiv:
        identifiers[IdentifierScheme.ARXIV] = arxiv
    with library.db.write_session() as session:
        return (
            PaperService(session)
            .add("LLM code review", identifiers=identifiers, authors=[], oa_url=oa_url)
            .id
        )


# --- Unpaywall's answer -------------------------------------------------------------


def test_unpaywall_pdf_links_come_best_first_without_repeats() -> None:
    answer = unpaywall_answer("https://a/x.pdf", None, "https://b/y.pdf", "https://a/x.pdf")

    found = open_access.unpaywall_candidates(answer)

    assert found == [
        Candidate("https://a/x.pdf", "unpaywall"),
        Candidate("https://b/y.pdf", "unpaywall"),
    ]
    assert open_access.unpaywall_candidates({"is_oa": False, "best_oa_location": None}) == []
    assert open_access.unpaywall_candidates("not json object") == []


# --- choosing and trying candidates --------------------------------------------------


class FakeAccess:
    def __init__(self, files: dict[str, bytes | TezError], unpaywall: list[str] | TezError):
        self.files = files
        self._unpaywall = unpaywall
        self.tried: list[str] = []

    async def unpaywall(self, doi: str) -> list[Candidate]:
        if isinstance(self._unpaywall, TezError):
            raise self._unpaywall
        return [Candidate(url, "unpaywall") for url in self._unpaywall]

    async def download(
        self, candidate: Candidate, on_progress: Callable[[int, int | None], None]
    ) -> bytes:
        self.tried.append(candidate.url)
        found = self.files.get(candidate.url, TezError(ErrorCode.SOURCE_REJECTED, {"status": 404}))
        if isinstance(found, TezError):
            raise found
        on_progress(len(found) // 2, len(found))
        on_progress(len(found), len(found))
        return found


def ref(paper_id: str, **fields: Any) -> PaperRef:
    values: dict[str, Any] = {"doi": None, "arxiv_id": None, "oa_url": None, "title": "LLM review"}
    return PaperRef(paper_id=paper_id, **{**values, **fields})


def run(library: Library, paper: PaperRef, access: FakeAccess, *, has_email: bool = True):
    progress: list[float] = []
    added = asyncio.run(
        find_and_store(library.db, paper, access, has_email=has_email, report=progress.append)
    )
    return added, progress


def test_arxiv_comes_first_and_the_pdf_is_attached(library: Library) -> None:
    paper_id = add_paper(library, doi=DOI, arxiv="2401.01234")
    access = FakeAccess({"https://arxiv.org/pdf/2401.01234": PDF}, ["https://repo/x.pdf"])

    added, progress = run(library, ref(paper_id, doi=DOI, arxiv_id="2401.01234"), access)

    assert access.tried == ["https://arxiv.org/pdf/2401.01234"]
    assert added.status == "added"
    assert added.paper_id == paper_id
    assert added.file_name == "arXiv-2401.01234.pdf"
    assert progress and 0 < progress[0] < progress[-1] < 1
    with library.db.session() as session:
        attachment = session.get(Attachment, added.attachment_id)
        assert attachment is not None and attachment.source == "arxiv"


def test_a_landing_page_is_skipped_for_the_next_candidate(library: Library) -> None:
    paper_id = add_paper(library, doi=DOI)
    access = FakeAccess(
        {"https://publisher/x.pdf": LANDING_PAGE, "https://repo/x.pdf": PDF},
        ["https://publisher/x.pdf", "https://repo/x.pdf"],
    )

    added, _ = run(library, ref(paper_id, doi=DOI), access)

    assert access.tried == ["https://publisher/x.pdf", "https://repo/x.pdf"]
    assert added.file_name == "10.1145_3597503.3639187.pdf"


def test_the_search_sources_link_is_the_last_resort(library: Library) -> None:
    paper_id = add_paper(library, oa_url="https://source/oa.pdf")
    access = FakeAccess({"https://source/oa.pdf": PDF}, [])

    added, _ = run(library, ref(paper_id, oa_url="https://source/oa.pdf"), access)

    assert added.status == "added"


def test_no_free_copy_ends_the_job_without_retrying(library: Library) -> None:
    paper_id = add_paper(library, doi=DOI)
    access = FakeAccess({"https://publisher/x.pdf": LANDING_PAGE}, ["https://publisher/x.pdf"])

    with pytest.raises(JobFailed) as caught:
        run(library, ref(paper_id, doi=DOI), access)

    assert (caught.value.code, caught.value.retry) == ("pdf.no_open_access", False)
    assert caught.value.params == {"tried": 1}


def test_a_network_failure_is_retried_later(library: Library) -> None:
    paper_id = add_paper(library, doi=DOI)
    timeout = TezError(ErrorCode.SOURCE_TIMEOUT, {"source": "unpaywall"})

    with pytest.raises(JobFailed) as caught:
        run(library, ref(paper_id, doi=DOI), FakeAccess({}, timeout))

    assert (caught.value.code, caught.value.retry) == ("source.timeout", True)


def test_a_doi_without_an_email_asks_for_one(library: Library) -> None:
    paper_id = add_paper(library, doi=DOI)

    with pytest.raises(JobFailed) as caught:
        run(library, ref(paper_id, doi=DOI), FakeAccess({}, []), has_email=False)

    assert caught.value.code == "source.email_required"


# --- the HTTP download ---------------------------------------------------------------

FAST = SourcePolicy("test", requests_per_second=1000)


def http_with(handler: Callable[[httpx2.Request], httpx2.Response]) -> HttpClient:
    async def no_sleep(_: float) -> None:
        return None

    return HttpClient(transport=httpx2.MockTransport(handler), sleep=no_sleep)


def test_a_download_streams_and_reports_progress() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=PDF, headers={"Content-Type": "application/pdf"})

    seen: list[tuple[int, int | None]] = []

    async def go() -> bytes:
        async with http_with(handler) as http:
            found = await http.download(
                FAST,
                "https://x/a.pdf",
                max_bytes=10_000_000,
                on_progress=lambda done, total: seen.append((done, total)),
            )
            return found.content

    assert asyncio.run(go()) == PDF
    assert seen[-1] == (len(PDF), len(PDF))


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx2.Response(404), ErrorCode.SOURCE_REJECTED),
        (httpx2.Response(503), ErrorCode.SOURCE_UNAVAILABLE),
        (httpx2.Response(429, headers={"Retry-After": "5"}), ErrorCode.SOURCE_RATE_LIMITED),
        (httpx2.Response(200, content=b"x" * 2000), ErrorCode.SOURCE_TOO_LARGE),
    ],
)
def test_download_failures_have_codes(response: httpx2.Response, code: ErrorCode) -> None:
    async def go() -> None:
        async with http_with(lambda _: response) as http:
            await http.download(FAST, "https://x/a.pdf", max_bytes=1000)

    with pytest.raises(TezError) as caught:
        asyncio.run(go())

    assert caught.value.code is code


# --- the API and the job, end to end -------------------------------------------------


def fake_network(monkeypatch: pytest.MonkeyPatch, routes: dict[str, httpx2.Response]) -> list[str]:
    """The worker's HttpClient talks to these routes instead of the internet."""
    asked: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        url = str(request.url.copy_with(query=None))
        asked.append(str(request.url))
        return routes.get(url, httpx2.Response(404))

    real = HttpClient

    def offline(**kwargs: Any) -> HttpClient:
        return real(transport=httpx2.MockTransport(handler), **kwargs)

    monkeypatch.setattr(open_access, "HttpClient", offline)
    return asked


def run_jobs(library: Library) -> None:
    worker = Worker(library.db, registry, lease=timedelta(seconds=30))
    while worker.run_once():
        pass


def test_the_api_queues_one_job_per_paper_and_the_worker_downloads(
    client: TestClient, library: Library, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_service.update_settings(library.db, SettingsPatch(sources_email="me@uni.edu.tr"))
    with_doi = add_paper(library, doi=DOI)
    nowhere = add_paper(library)
    asked = fake_network(
        monkeypatch,
        {
            f"https://api.unpaywall.org/v2/{DOI}": httpx2.Response(
                200, json=unpaywall_answer("https://repo.example/paper.pdf")
            ),
            "https://repo.example/paper.pdf": httpx2.Response(
                200, content=PDF, headers={"Content-Type": "application/pdf"}
            ),
        },
    )

    response = client.post("/pdfs/open-access", json={"paper_ids": [with_doi, nowhere]})

    assert response.status_code == 202, response.text
    queued = response.json()
    assert (len(queued["job_ids"]), queued["already_have_pdf"], queued["no_source"]) == (1, 0, 1)
    with library.db.session() as session:
        assert all(session.get(Paper, p).library_added_at for p in (with_doi, nowhere))  # type: ignore[union-attr]

    run_jobs(library)

    assert f"https://api.unpaywall.org/v2/{DOI}?email=me%40uni.edu.tr" in asked
    job = client.get(f"/jobs/{queued['job_ids'][0]}").json()
    assert (job["status"], job["progress"]) == ("done", 1.0)
    (attachment,) = client.get(f"/papers/{with_doi}/attachments").json()
    assert attachment["source"] == "unpaywall"
    assert (attachment["page_count"], attachment["text_status"]) == (2, "ok")  # inspected too

    again = client.post("/pdfs/open-access", json={"paper_ids": [with_doi]}).json()
    assert (again["job_ids"], again["already_have_pdf"]) == ([], 1)


def test_a_paper_with_no_free_copy_shows_why_in_its_job(
    client: TestClient, library: Library, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_service.update_settings(library.db, SettingsPatch(sources_email="me@uni.edu.tr"))
    paper_id = add_paper(library, doi=DOI)
    fake_network(
        monkeypatch,
        {f"https://api.unpaywall.org/v2/{DOI}": httpx2.Response(200, json=unpaywall_answer())},
    )
    job_id = client.post("/pdfs/open-access", json={"paper_ids": [paper_id]}).json()["job_ids"][0]

    run_jobs(library)

    with library.db.session() as session:
        job = session.get(ProcessingJob, job_id)
        assert job is not None
        assert job.status is JobStatus.FAILED
        assert job.attempts == 1  # not retried: the answer would not change
    assert client.get(f"/jobs/{job_id}").json()["error"] == {
        "code": "pdf.no_open_access",
        "params": {"tried": 0},
    }


def test_unknown_papers_are_404(client: TestClient) -> None:
    response = client.post("/pdfs/open-access", json={"paper_ids": ["nope"]})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "paper.not_found"
