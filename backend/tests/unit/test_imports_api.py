"""Task 15 acceptance: sample files import through deduplication into a logged search run,
and the bad entries come back as a report. No network: imports never touch it.
"""

import base64
import gzip
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.library.models import IdentifierScheme
from tez.modules.library.paper_service import PaperService
from tez.modules.library.service import Library, open_library
from tez.modules.reviews.models import ReviewMethod
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.search.models import SearchRun
from tez.modules.settings.secrets import MemorySecretStore

FIXTURES = Path(__file__).parent.parent / "fixtures" / "imports"


@pytest.fixture
def library(tmp_path: Path) -> Library:
    return open_library(tmp_path / "lib", create=True)


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(
        token=TOKEN, settings=Settings(), library=library, secret_store=MemorySecretStore()
    )
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def review_id(library: Library) -> str:
    with library.db.write_session() as session:
        return ReviewsRepository(session).add_review("SLR", method=ReviewMethod.PRISMA2020).id


def file_body(name: str, data: bytes | None = None) -> dict[str, Any]:
    data = data if data is not None else (FIXTURES / name).read_bytes()
    return {"file_name": name, "content_base64": base64.b64encode(data).decode()}


def known_paper(library: Library, *, keep: bool) -> str:
    """A paper an earlier search found: the IEEE article, by DOI."""
    with library.db.write_session() as session:
        papers = PaperService(session)
        paper = papers.add(
            "Automated Code Review with Large Language Models: An Empirical Study",
            identifiers={IdentifierScheme.DOI: "10.1109/tse.2024.0012345"},
            authors=[],
            year=2024,
        )
        if keep:
            papers.keep([paper.id])
        return paper.id


def run_count(library: Library) -> int:
    with library.db.session() as session:
        return session.query(SearchRun).count()


def test_preview_says_what_an_import_would_do_and_writes_nothing(
    client: TestClient, library: Library
) -> None:
    known_paper(library, keep=True)

    response = client.post("/imports/preview", json=file_body("scopus.ris"))

    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["format"] == "ris"
    assert (preview["total"], preview["readable"]) == (5, 3)
    assert [i["code"] for i in preview["issues"]] == [
        "import.entry_no_title",
        "import.entry_truncated",
    ]
    assert (preview["new"], preview["known"], preview["in_library"]) == (2, 0, 1)
    assert preview["warnings"] == {"no_authors": 1, "no_identifier": 1, "bad_link": 1}
    first = preview["sample"][0]
    assert first["status"] == "in_library"
    assert first["match_method"] == "doi"
    assert first["first_author"] == "A. Yılmaz"
    assert run_count(library) == 0


def test_preview_marks_records_repeated_within_the_file(client: TestClient) -> None:
    text = (
        "TY  - JOUR\nTI  - Same Paper\nDO  - 10.1000/x\nER  - \n"
        "TY  - JOUR\nTI  - Same paper!\nDO  - 10.1000/X\nER  - \n"
    )

    preview = client.post("/imports/preview", json=file_body("x.ris", text.encode())).json()

    assert (preview["new"], preview["repeated"]) == (1, 1)
    assert [r["status"] for r in preview["sample"]] == ["new", "repeated"]


def test_an_import_is_logged_as_a_search_run(
    client: TestClient, library: Library, review_id: str
) -> None:
    known = known_paper(library, keep=False)
    body = {
        **file_body("ieee-xplore.bib"),
        "review_id": review_id,
        "log": {
            "source": "IEEE Xplore",
            "searched_at": "2026-11-01",
            "query": '("code review") AND (LLM)',
        },
    }

    response = client.post("/imports", json=body)

    assert response.status_code == 201, response.text
    outcome = response.json()
    assert (outcome["total"], outcome["imported"]) == (7, 4)
    assert outcome["new_papers"] == 3
    assert len(outcome["issues"]) == 3
    search_id = outcome["search_id"]

    overview = client.get(f"/searches/{search_id}").json()
    assert overview["file_name"] == "ieee-xplore.bib"
    assert overview["query"] == '("code review") AND (LLM)'
    assert overview["initiated_via"] == "gui"
    assert overview["started_at"].startswith("2026-11-01")
    (run,) = overview["runs"]
    assert run["source"] == "IEEE Xplore"
    assert run["status"] == "partial"
    assert run["error"] == {"code": "import.entries_skipped", "params": {"skipped": 3}}
    assert (run["total_reported"], run["retrieved_count"]) == (7, 4)
    assert (overview["retrieved"], overview["unique"], overview["duplicates"]) == (4, 4, 0)

    rows = client.get(f"/searches/{search_id}/results").json()
    merged = next(row for row in rows if row["paper_id"] == known)
    assert merged["sources"][0]["match_method"] == "doi"
    # Enrichment filled what the known paper lacked.
    assert merged["venue"] == "IEEE Transactions on Software Engineering"

    history = client.get("/searches", params={"review_id": review_id}).json()
    assert [h["search_id"] for h in history] == [search_id]


def test_the_imported_file_is_kept_as_the_run_snapshot(
    client: TestClient, library: Library, review_id: str
) -> None:
    body = {**file_body("scopus.ris"), "review_id": review_id, "log": {"source": "Scopus"}}

    client.post("/imports", json=body)

    with library.db.session() as session:
        run = session.query(SearchRun).one()
        assert run.snapshot_path is not None
        snapshot_path = library.path / run.snapshot_path
    with gzip.open(snapshot_path, "rt", encoding="utf-8") as file:
        snapshot = json.load(file)
    assert snapshot["file_name"] == "scopus.ris"
    assert snapshot["source"] == "Scopus"
    assert snapshot["content"] == (FIXTURES / "scopus.ris").read_text(encoding="utf-8")


def test_an_import_can_go_to_the_review_and_the_library(
    client: TestClient, library: Library, review_id: str
) -> None:
    body = {
        **file_body("scopus.ris"),
        "review_id": review_id,
        "log": {"source": "Scopus"},
        "add_to_review": True,
        "add_to_library": True,
    }

    outcome = client.post("/imports", json=body).json()

    assert (outcome["added_to_review"], outcome["added_to_library"]) == (3, 3)
    with library.db.session() as session:
        records = ReviewsRepository(session).records(review_id)
        assert {r.origin_ref for r in records} == {outcome["search_id"]}

    again = client.post("/imports", json=body).json()
    assert again["new_papers"] == 0
    assert (again["added_to_review"], again["added_to_library"]) == (0, 0)


def test_an_import_into_the_library_only_needs_no_review(
    client: TestClient, library: Library
) -> None:
    body = {**file_body("scopus.ris"), "add_to_library": True}

    outcome = client.post("/imports", json=body).json()

    assert outcome["search_id"] is None
    assert outcome["added_to_library"] == 3
    assert run_count(library) == 0


@pytest.mark.parametrize(
    "extra",
    [
        {},  # no target at all
        {"add_to_review": True},  # a review target without a review
        {"log": {"source": "IEEE Xplore"}},
    ],
)
def test_an_import_needs_a_target(client: TestClient, extra: dict[str, Any]) -> None:
    response = client.post("/imports", json={**file_body("scopus.ris"), **extra})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "request.invalid"


def test_a_file_without_records_is_refused(client: TestClient, library: Library) -> None:
    body = {**file_body("empty.bib", b"@comment{nothing here}"), "add_to_library": True}

    response = client.post("/imports", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "import.empty"
    assert run_count(library) == 0


def test_unknown_formats_and_bad_content_are_refused(client: TestClient) -> None:
    unknown = client.post("/imports/preview", json=file_body("notes.txt", b"hello"))
    assert unknown.json()["error"] == {
        "code": "import.unknown_format",
        "params": {"file_name": "notes.txt"},
    }

    bad = client.post("/imports/preview", json={"file_name": "x.bib", "content_base64": "!!"})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "import.invalid_content"


def test_an_unknown_review_is_404(client: TestClient) -> None:
    body = {**file_body("scopus.ris"), "review_id": "nope", "log": {"source": "Scopus"}}

    response = client.post("/imports", json=body)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "review.not_found"
