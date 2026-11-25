"""Task 19: metadata search (FTS5 with Turkish folding), citation keys and the paper detail.

Acceptance: a search in a 2000-paper demo library takes under 100 ms.
"""

import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.devtools.demo import make_library
from tez.main import create_app
from tez.modules.files.repository import FilesRepository
from tez.modules.library import citekeys
from tez.modules.library.models import IdentifierScheme, Paper
from tez.modules.library.paper_service import PaperService
from tez.modules.library.repository import AuthorInput
from tez.modules.library.service import Library, open_library
from tez.modules.settings.secrets import MemorySecretStore


def make_client(library: Library) -> TestClient:
    app = create_app(
        token=TOKEN, settings=Settings(), library=library, secret_store=MemorySecretStore()
    )
    return TestClient(app, headers=AUTH, raise_server_exceptions=False)


@pytest.fixture
def library(tmp_path: Path) -> Library:
    return open_library(tmp_path / "lib", create=True)


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    with make_client(library) as c:
        yield c


def add(
    library: Library,
    title: str,
    *,
    authors: tuple[str, ...] = ("Ayşe Yılmaz",),
    keep: bool = True,
    identifiers: dict[IdentifierScheme, str] | None = None,
    **fields: Any,
) -> str:
    with library.db.write_session() as session:
        service = PaperService(session)
        paper = service.add(
            title,
            identifiers=identifiers or {},
            authors=[AuthorInput(display_name=name, family=name.split()[-1]) for name in authors],
            **fields,
        )
        if keep:
            service.keep([paper.id])
        return paper.id


def hits(client: TestClient, query: str) -> list[str]:
    response = client.get("/papers/search", params={"q": query})
    assert response.status_code == 200, response.text
    return response.json()["paper_ids"]


# --- search ---------------------------------------------------------------------------


def test_title_author_abstract_venue_and_doi_are_searchable(
    client: TestClient, library: Library
) -> None:
    paper = add(
        library,
        "Automated Code Review with Large Language Models",
        authors=("Mehmet Çelik",),
        abstract="We study reviewer fatigue in industry.",
        venue="ICSE",
        identifiers={IdentifierScheme.DOI: "10.1145/3597503.3639187"},
    )
    add(library, "Something Else Entirely", authors=("Jane Doe",))

    for query in ("code review", "celik", "fatigue", "icse", "3597503", "auto rev", "LARGE"):
        assert hits(client, query) == [paper], query


def test_turkish_letters_fold_both_ways(client: TestClient, library: Library) -> None:
    paper = add(library, "Işık Kaynakları ve Görüş Açısı", authors=("İlker Şahin",))

    for query in ("ışık", "ISIK", "isik", "IŞIK", "ilker", "İLKER", "sahin", "görüş", "gorus"):
        assert hits(client, query) == [paper], query


def test_every_word_must_match_and_titles_rank_first(client: TestClient, library: Library) -> None:
    in_title = add(library, "Refactoring with Language Models")
    in_abstract = add(library, "A Study", abstract="On refactoring and language models.")
    add(library, "Refactoring Alone")

    assert hits(client, "refactoring models") == [in_title, in_abstract]
    assert hits(client, "   ") == []
    assert hits(client, '"*)(') == []  # FTS syntax in the query is just ignored


def test_the_index_follows_enrichment_and_deletion(client: TestClient, library: Library) -> None:
    paper = add(library, "Code Review Study")
    assert hits(client, "flakiness") == []

    with library.db.write_session() as session:
        PaperService(session).fill_missing(
            paper, identifiers={IdentifierScheme.ARXIV: "2401.01234"}, abstract="Flakiness."
        )
    assert hits(client, "flakiness") == [paper]
    assert hits(client, "2401") == [paper]

    with library.db.write_session() as session:
        stored = session.get(Paper, paper)
        assert stored is not None
        session.delete(stored)  # through the ORM: bulk SQL deletes bypass the index upkeep
    assert hits(client, "code review") == []


def test_a_library_without_an_index_is_indexed_when_opened(tmp_path: Path) -> None:
    library = open_library(tmp_path / "lib", create=True)
    paper = add(library, "Mining Software Repositories")
    library.close()
    raw = sqlite3.connect(tmp_path / "lib" / "library.sqlite")
    raw.execute("DELETE FROM paper_fts")
    raw.commit()
    raw.close()

    reopened = open_library(tmp_path / "lib")
    with make_client(reopened) as client:
        assert hits(client, "mining") == [paper]


# --- citation keys ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("family", "year", "title", "key"),
    [
        ("Çelik", 2024, "On the Use of LLMs for Review", "celik2024use"),
        ("van der Berg", 2019, "BERT-style Models", "berg2019bertstyle"),
        ("Şahin", None, "Işık ve Gölge", "sahinisik"),
        (None, 2020, "The A", "anon2020"),
    ],
)
def test_citation_keys_are_ascii_author_year_word(
    family: str | None, year: int | None, title: str, key: str
) -> None:
    assert citekeys.base_key(family, year, title) == key


def test_kept_papers_get_unique_keys(client: TestClient, library: Library) -> None:
    first = add(library, "Automated Review", authors=("Ayşe Yılmaz",), year=2024)
    second = add(library, "Automated Testing", authors=("Ali Yılmaz",), year=2024)
    candidate = add(library, "Automated Things", keep=False, year=2024)

    keys = {p["id"]: p["citekey"] for p in client.get("/papers").json()}

    assert keys == {first: "yilmaz2024automated", second: "yilmaz2024automateda"}
    assert client.get(f"/papers/{candidate}").json()["citekey"] is None


def test_papers_kept_before_keys_existed_get_one_on_open(tmp_path: Path) -> None:
    library = open_library(tmp_path / "lib", create=True)
    paper = add(library, "Old Paper", year=2021)
    raw = sqlite3.connect(library.path / "library.sqlite")
    library.close()
    raw.execute("UPDATE paper SET citekey = NULL")
    raw.commit()
    raw.close()

    reopened = open_library(tmp_path / "lib")
    with make_client(reopened) as client:
        assert client.get(f"/papers/{paper}").json()["citekey"] == "yilmaz2021old"


def test_a_citation_key_can_be_edited_if_valid_and_free(
    client: TestClient, library: Library
) -> None:
    first = add(library, "First", year=2024)
    second = add(library, "Second", year=2024)

    changed = client.patch(f"/papers/{first}", json={"citekey": "yilmaz:llm-review"})
    assert changed.json()["citekey"] == "yilmaz:llm-review"
    taken = client.patch(f"/papers/{second}", json={"citekey": "yilmaz:llm-review"})
    assert (taken.status_code, taken.json()["error"]["code"]) == (409, "citekey.taken")
    invalid = client.patch(f"/papers/{second}", json={"citekey": "has space"})
    assert (invalid.status_code, invalid.json()["error"]["code"]) == (422, "citekey.invalid")
    assert hits(client, "llm review") == [first]  # the key is searchable too


# --- the paper detail ------------------------------------------------------------------


def test_the_detail_has_authors_identifiers_files_and_versions(
    client: TestClient, library: Library
) -> None:
    published = add(
        library,
        "Code Review at Scale",
        authors=("Ayşe Yılmaz", "Jane Doe"),
        year=2024,
        venue="ICSE",
        identifiers={IdentifierScheme.DOI: "10.1145/1"},
    )
    preprint = add(library, "Code Review at Scale", keep=False, year=2023)
    with library.db.write_session() as session:
        PaperService(session).link_versions(preprint, published)
        FilesRepository(session).add_attachment(
            published, rel_path="files/aa/x.pdf", sha256="a" * 64, file_name="scale.pdf"
        )
    tag = client.post("/tags", json={"name": "ölçek"}).json()
    client.post(f"/tags/{tag['id']}/papers", json={"paper_ids": [published]})

    detail = client.get(f"/papers/{published}").json()

    assert [a["display_name"] for a in detail["authors"]] == ["Ayşe Yılmaz", "Jane Doe"]
    assert detail["identifiers"] == {"doi": "10.1145/1"}
    assert detail["tag_ids"] == [tag["id"]]
    assert [a["file_name"] for a in detail["attachments"]] == ["scale.pdf"]
    assert detail["related"] == [
        {
            "paper_id": preprint,
            "title": "Code Review at Scale",
            "year": 2023,
            "relation": "preprint",
        }
    ]
    back = client.get(f"/papers/{preprint}").json()["related"]
    assert back[0]["relation"] == "published_version"
    assert client.get("/papers/nope").status_code == 404


# --- acceptance ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def demo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("demo") / "library"
    make_library(path, 2000)
    return path


@pytest.mark.timing
def test_task_19_acceptance_search_in_2000_papers_under_100_ms(demo: Path) -> None:
    library = open_library(demo)
    with make_client(library) as client:
        assert len(client.get("/papers").json()) == 2000
        queries = ["code review", "yilmaz", "refact", "large language models", "isil", "icse"]
        client.get("/papers/search", params={"q": "warm up"})
        for query in queries:
            started = time.perf_counter()
            response = client.get("/papers/search", params={"q": query})
            round_trip_ms = (time.perf_counter() - started) * 1000
            assert response.status_code == 200
            assert response.json()["paper_ids"], query
            assert response.json()["elapsed_ms"] < 100, query
            assert round_trip_ms < 100, (query, round_trip_ms)
