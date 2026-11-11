"""Task 23 acceptance: `tez search`, `import`, `add` and `export` end to end, in both modes.

"direct": no app has the library, so the command opens it under the lock.
"api": a real API server (uvicorn on a socket) has the library and has published itself in
`.tez/instance.json`; the command must go through it. The same assertions hold in both.
No network: search sources are fakes, the keyring is in memory.
"""

import json
import socket
import threading
import time
from collections.abc import AsyncGenerator, Iterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from typer.testing import CliRunner

from tests.conftest import TOKEN
from tests.pdfs import make_pdf
from tez.cli import access as cli_access
from tez.cli.i18n import Messages, translate_click
from tez.cli.main import build_app
from tez.core.config import Settings
from tez.core.db import Database
from tez.main import create_app
from tez.modules.importers.bibtex import parse_bibtex
from tez.modules.library.service import open_library
from tez.modules.reviews import service as reviews_service
from tez.modules.reviews.models import ReviewMethod
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.search import queries
from tez.modules.search.providers.base import OnWait, ProviderResult, SearchProvider, SearchRequest
from tez.modules.search.providers.registry import SourceAccess
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor
from tez.modules.settings.secrets import MemorySecretStore

FIXTURES = Path(__file__).parent.parent / "fixtures" / "imports"


def record(title: str, doi: str) -> NormalizedRecord:
    return NormalizedRecord.model_validate(
        {
            "title": title,
            "authors": (RecordAuthor(display_name="Ayşe Yılmaz", family="Yılmaz"),),
            "year": 2024,
            "identifiers": {"doi": doi},
        }
    )


class FakeSource:
    def __init__(self, name: str, records: tuple[NormalizedRecord, ...], crash: bool = False):
        self.name = name
        self._records = records
        self._crash = crash

    async def search(
        self, request: SearchRequest, *, on_wait: OnWait | None = None
    ) -> ProviderResult:
        if self._crash:
            raise RuntimeError("boom")
        return ProviderResult(self.name, f"{self.name}:{request.query}", records=self._records)


SOURCES = {
    "openalex": FakeSource(
        "openalex",
        (record("LLM Code Review at Scale", "10.1000/a"), record("Reviewer Fatigue", "10.1000/b")),
    ),
    "crossref": FakeSource("crossref", (record("LLM Code Review at Scale", "10.1000/a"),)),
    "arxiv": FakeSource("arxiv", (), crash=True),
}


@asynccontextmanager
async def fake_providers(
    names: Sequence[str], access: SourceAccess
) -> AsyncGenerator[Sequence[SearchProvider]]:
    yield [SOURCES[name] for name in names]


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_access, "PROVIDERS", fake_providers)
    monkeypatch.setattr(cli_access, "SECRETS", MemorySecretStore)


@pytest.fixture
def library_path(tmp_path: Path) -> Path:
    path = tmp_path / "TEz Library"
    library = open_library(path, create=True)
    with library.db.write_session() as session:
        ReviewsRepository(session).add_review(
            "LLM Kod İnceleme SLR", method=ReviewMethod.PRISMA2020
        )
    library.close()
    return path


def serve(library_path: Path) -> Iterator[None]:
    """The desktop app's backend in miniature: owns the library and publishes its API."""
    library = open_library(library_path)
    app = create_app(
        token=TOKEN,
        settings=Settings(),
        library=library,
        secret_store=MemorySecretStore(),
        provider_factory=fake_providers,
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(64)
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started, "API server did not start"
    library.publish_api(url=f"http://127.0.0.1:{port}", token=TOKEN)
    try:
        yield
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()


@pytest.fixture(params=["direct", "api"])
def mode(request: pytest.FixtureRequest, library_path: Path) -> Iterator[str]:
    if request.param == "api":
        yield from (request.param for _ in serve(library_path))
    else:
        yield request.param


def tez(library: Path, *args: str, lang: str = "en") -> tuple[int, Any, str]:
    """Run `tez --json ...`; returns the exit code, the JSON document and stderr."""
    result = CliRunner().invoke(
        build_app(Messages("en" if lang == "en" else "tr")),
        ["--library", str(library), "--json", *args],
    )
    stdout = result.stdout.strip()
    return result.exit_code, json.loads(stdout) if stdout else None, result.stderr


def test_search_records_a_cli_search_and_reports_a_failed_source(
    mode: str, library_path: Path
) -> None:
    code, out, _ = tez(library_path, "search", "code review", "--sources", "oa,crossref,arxiv")

    assert out["mode"] == mode
    assert code == 2  # arxiv failed, the others answered
    search = out["search"]
    assert search["initiated_via"] == "cli"
    assert (search["retrieved"], search["unique"], search["duplicates"]) == (3, 2, 1)
    statuses = {run["source"]: run["status"] for run in search["runs"]}
    assert statuses == {"openalex": "ok", "crossref": "ok", "arxiv": "error"}


def test_search_with_every_source_ok_exits_0(mode: str, library_path: Path) -> None:
    code, out, _ = tez(library_path, "search", "code review", "-s", "openalex")

    assert code == 0
    assert out["search"]["runs"][0]["translated_query"] == "openalex:code review"


def test_import_logs_the_file_as_a_cli_search_run(mode: str, library_path: Path) -> None:
    code, out, _ = tez(
        library_path,
        "import",
        str(FIXTURES / "scopus.ris"),
        "--source",
        "Scopus",
        "--searched-at",
        "2026-11-01",
        "--query",
        "code review",
    )

    assert code == 2  # two entries of the sample are broken on purpose
    outcome = out["import"]
    assert (outcome["total"], outcome["imported"], outcome["added_to_review"]) == (5, 3, 3)
    assert len(outcome["issues"]) == 2
    # Read the record straight from the file: SQLite lets readers in while the app writes.
    db = Database(library_path / "library.sqlite")
    try:
        review_id = reviews_service.list_reviews(db)[0].id
        (run,) = queries.history(db, review_id)
    finally:
        db.close()
    assert (run.file_name, run.initiated_via, run.query) == ("scopus.ris", "cli", "code review")


def test_add_stores_pdfs_once_files_them_and_reports_bad_ones(
    mode: str, library_path: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "papers"
    folder.mkdir()
    (folder / "kim-2024.pdf").write_bytes(make_pdf(2, tag="kim"))
    (folder / "copy-of-kim.pdf").write_bytes(make_pdf(2, tag="kim"))
    (folder / "notes.pdf").write_text("not a pdf", encoding="utf-8")

    code, out, _ = tez(library_path, "add", str(folder), "--collection", "Tez")

    assert code == 2
    by_name = {Path(r["path"]).name: r for r in out["results"]}
    # The two files hold the same bytes: one is stored, the other is the same paper.
    statuses = {by_name[n]["added"]["status"] for n in ("kim-2024.pdf", "copy-of-kim.pdf")}
    assert statuses == {"added", "duplicate"}
    assert by_name["notes.pdf"]["error"]["code"] == "pdf.not_a_pdf"
    assert out["collection"]["name"] == "Tez"

    again, out, _ = tez(library_path, "add", str(folder / "kim-2024.pdf"), "-c", "tez")
    assert again == 0
    assert out["results"][0]["added"]["status"] == "duplicate"
    assert out["collection"]["id"]  # the same collection, found by its folded name


def test_export_writes_bibtex_that_reads_back(
    mode: str, library_path: Path, tmp_path: Path
) -> None:
    tez(library_path, "import", str(FIXTURES / "ieee-xplore.bib"), "--source", "IEEE Xplore")
    target = tmp_path / "refs.bib"

    code, out, _ = tez(
        library_path, "export", "--review", "llm kod inceleme slr", "-o", str(target)
    )

    assert code == 0
    assert (out["export"]["count"], out["export"]["format"]) == (4, "bibtex")
    parsed = parse_bibtex(target.read_text(encoding="utf-8"))
    assert parsed.issues == []
    assert "Automated Code Review with Large Language Models: An Empirical Study" in {
        e.record.title for e in parsed.entries
    }


def test_errors_have_codes_and_exit_1(mode: str, library_path: Path) -> None:
    code, out, _ = tez(library_path, "search", "x", "--sources", "google")
    assert (code, out["error"]["code"]) == (1, "source.unknown")

    code, out, _ = tez(library_path, "search", "x", "--review", "no such review")
    assert (code, out["error"]["code"]) == (1, "review.not_found")

    code, out, _ = tez(library_path, "import", "missing.ris", "--source", "Scopus")
    assert (code, out["error"]["code"]) == (1, "import.file_not_found")


def test_several_reviews_need_one_named(library_path: Path) -> None:
    library = open_library(library_path)
    with library.db.write_session() as session:
        ReviewsRepository(session).add_review("Second", method=ReviewMethod.KITCHENHAM_SLR)
    library.close()

    code, out, _ = tez(library_path, "search", "x")

    assert (code, out["error"]["code"]) == (1, "cli.review_required")
    assert '"Second"' in out["error"]["params"]["reviews"]


def test_a_library_held_by_another_command_is_busy(library_path: Path) -> None:
    holder = open_library(library_path, kind="cli")  # a headless command: no API to share
    try:
        code, out, _ = tez(library_path, "export")
    finally:
        holder.close()

    assert (code, out["error"]["code"]) == (1, "cli.library_busy")


def test_a_missing_library_is_reported_in_the_users_language(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        build_app(Messages("tr")), ["--library", str(tmp_path / "yok"), "export"]
    )

    assert result.exit_code == 1
    assert "Kütüphane bulunamadı" in result.stderr


def test_help_is_in_turkish_and_english() -> None:
    english = CliRunner().invoke(build_app(Messages("en")), ["search", "--help"])
    translate_click("tr")
    turkish = CliRunner().invoke(build_app(Messages("tr")), ["search", "--help"])

    assert "Search the sources and record the search in a review" in english.stdout
    assert "Kaynaklarda arar ve aramayı review'a kaydeder" in turkish.stdout
    assert "Seçenekler" in turkish.stdout
    assert "Bu yardımı gösterir ve çıkar." in turkish.stdout
    for command in ("search", "import", "add", "export"):
        assert CliRunner().invoke(build_app(Messages("tr")), [command, "--help"]).exit_code == 0
