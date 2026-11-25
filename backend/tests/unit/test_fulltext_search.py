"""Task 44 acceptance: Turkish letters fold both ways; a search in 2000 papers' PDFs takes under
200 ms; a result names the page the passage is on."""

import random
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.conftest import AUTH, TOKEN
from tests.pdfs import make_text_pdf
from tez.core.config import Settings
from tez.devtools.demo import make_library
from tez.main import create_app
from tez.modules.files import service as files_service
from tez.modules.files.models import Attachment
from tez.modules.files.repository import FilesRepository
from tez.modules.fulltext import service as fulltext_service
from tez.modules.fulltext.extraction import PageText
from tez.modules.fulltext.repository import FulltextRepository
from tez.modules.fulltext.search_index import snippet
from tez.modules.jobs.registry import JobContext
from tez.modules.library.models import Paper
from tez.modules.library.paper_service import PaperService
from tez.modules.library.service import Library, open_library
from tez.modules.settings.secrets import MemorySecretStore
from tez.shared.text import fold, fold_with_map
from tez.shared.textsearch import Segment, parse


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    opened = open_library(tmp_path / "lib", create=True)
    yield opened
    opened.close()


def make_client(library: Library) -> TestClient:
    app = create_app(
        token=TOKEN, settings=Settings(), library=library, secret_store=MemorySecretStore()
    )
    return TestClient(app, headers=AUTH, raise_server_exceptions=False)


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    with make_client(library) as c:
        yield c


def add(library: Library, name: str, *pages: list[str]) -> tuple[str, str]:
    """A PDF whose text has been read; (paper id, attachment id)."""
    added = files_service.add_pdf(library.db, library.path, make_text_pdf(list(pages)), name)
    ctx = JobContext("job", db=library.db)
    fulltext_service.extract_text({"attachment_id": added.attachment_id}, ctx)
    return added.paper_id, added.attachment_id


def search(client: TestClient, q: str, **body: object) -> dict[str, Any]:
    response = client.post("/fulltext/search", json={"q": q, **body})
    assert response.status_code == 200, response.text
    return response.json()


def titles(found: dict[str, Any]) -> list[str]:
    return [paper["title"] for paper in found["papers"]]


def shown(page: dict[str, Any]) -> str:
    return "".join(part["text"] for part in page["snippet"])


def hits(page: dict[str, Any]) -> list[str]:
    return [part["text"] for part in page["snippet"] if part["hit"]]


def test_a_result_has_the_page_and_the_passage(client: TestClient, library: Library) -> None:
    paper, attachment = add(
        library, "study.pdf", ["Introduction only"], ["The interviews lasted", "an hour each."]
    )

    found = search(client, "interviews hour")

    assert (found["total_papers"], found["total_pages"]) == (1, 1)
    result = found["papers"][0]
    assert (result["paper_id"], result["title"], result["page_hits"]) == (paper, "study", 1)
    page = result["pages"][0]
    assert (page["attachment_id"], page["page"]) == (attachment, 2)
    assert shown(page) == "The interviews lasted an hour each."
    assert hits(page) == ["interviews", "hour"]


@pytest.mark.parametrize("query", ["ışık", "IŞIK", "isik", "Işık", "İSİK", "Istanbul", "İSTANBUL"])
def test_turkish_letters_fold_both_ways(client: TestClient, library: Library, query: str) -> None:
    add(library, "tr.pdf", ["İstanbul'da IŞIK kirliliği"])
    add(library, "other.pdf", ["Unrelated words"])

    found = search(client, query)

    assert titles(found) == ["tr"]
    assert len(hits(found["papers"][0]["pages"][0])) == 1


def test_words_match_by_their_beginning_and_all_must_be_on_the_page(
    client: TestClient, library: Library
) -> None:
    add(library, "one.pdf", ["Reviewers met"], ["and the methodology followed"])
    add(library, "two.pdf", ["Reviewers described the methodology"])

    assert sorted(titles(search(client, "review"))) == ["one", "two"]
    assert titles(search(client, "review method")) == ["two"]
    assert titles(search(client, "viewers")) == []


def test_a_quoted_phrase_must_match_exactly(client: TestClient, library: Library) -> None:
    add(library, "apart.pdf", ["grounded in a theory"])
    add(library, "together.pdf", ["We used Grounded Theory here"])

    found = search(client, '"grounded theory"')

    assert titles(found) == ["together"]
    assert hits(found["papers"][0]["pages"][0]) == ["Grounded Theory"]
    assert titles(search(client, '"grounded theor"')) == []


def test_a_word_broken_over_two_lines_is_found_whole_and_in_halves(
    client: TestClient, library: Library
) -> None:
    added = files_service.add_pdf(library.db, library.path, make_text_pdf([["x"]]), "broken.pdf")
    page = PageText(0, "an inter­\r\ndisciplinary and cost­\r\nbenefit study")
    with library.db.write_session() as session:
        FulltextRepository(session).replace(added.attachment_id, [page])

    for query in ("interdisciplinary", "benefit", "cost"):
        assert titles(search(client, query)) == ["broken"], query


def test_only_the_asked_papers_and_never_the_trash_or_candidates(
    client: TestClient, library: Library
) -> None:
    first, _ = add(library, "first.pdf", ["shared word"])
    second, _ = add(library, "second.pdf", ["shared word too"])
    third, _ = add(library, "third.pdf", ["shared word three"])
    with library.db.write_session() as session:
        trashed = session.get(Paper, third)
        assert trashed is not None
        trashed.deleted_at = trashed.created_at

    assert search(client, "shared")["total_papers"] == 2
    assert [p["paper_id"] for p in search(client, "shared", paper_ids=[second])["papers"]] == [
        second
    ]
    with library.db.write_session() as session:
        candidate = session.get(Paper, first)
        assert candidate is not None
        candidate.library_added_at = None
    assert [p["paper_id"] for p in search(client, "shared")["papers"]] == [second]
    assert search(client, "shared", paper_ids=[])["total_papers"] == 0


def test_a_paper_shows_its_best_pages_and_counts_the_rest(
    client: TestClient, library: Library
) -> None:
    add(library, "many.pdf", *[[f"term on page {n}"] for n in range(1, 6)])

    found = search(client, "term", limit=1)

    paper = found["papers"][0]
    assert (paper["page_hits"], len(paper["pages"]), found["total_pages"]) == (5, 3, 5)


@pytest.mark.parametrize("query", ['"', "***", "AND OR", 'NEAR("a"', "a AND (", "-", "''", "col:x"])
def test_odd_queries_are_just_words(client: TestClient, library: Library, query: str) -> None:
    add(library, "x.pdf", ["plain text"])

    search(client, query)


def test_the_index_follows_the_text(client: TestClient, library: Library) -> None:
    _, attachment = add(library, "a.pdf", ["first words"])
    with library.db.write_session() as session:
        FulltextRepository(session).replace(attachment, [PageText(0, "second words")])

    assert search(client, "first")["total_papers"] == 0
    assert search(client, "second")["total_papers"] == 1

    with library.db.write_session() as session:
        session.delete(session.get(Attachment, attachment))
    assert search(client, "second")["total_papers"] == 0
    with library.db.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM chunk_fts")).scalar_one() == 0


def test_an_index_that_does_not_cover_the_text_is_rebuilt_on_open(tmp_path: Path) -> None:
    path = tmp_path / "lib"
    library = open_library(path, create=True)
    add(library, "a.pdf", ["one"], ["two findable"])
    with library.db.write_session() as session:
        session.execute(text("INSERT INTO chunk_fts (chunk_fts) VALUES ('delete-all')"))
    library.close()

    library = open_library(path)
    with make_client(library) as client:
        assert search(client, "findable")["papers"][0]["pages"][0]["page"] == 2


def find(client: TestClient, attachment: str, q: str) -> dict[str, Any]:
    response = client.get(f"/attachments/{attachment}/find", params={"q": q})
    assert response.status_code == 200, response.text
    return response.json()


def test_find_in_one_document_counts_per_page(client: TestClient, library: Library) -> None:
    _, attachment = add(
        library, "doc.pdf", ["Işık and ışık", "then the long"], ["nothing"], ["sentence IŞIK."]
    )

    assert find(client, attachment, "isik") == {
        "text": "ready",
        "pages": [{"page": 1, "matches": 2}, {"page": 3, "matches": 1}],
        "total": 3,
    }
    # A match may run over the end of a line.
    assert find(client, attachment, "IŞIK  then the")["total"] == 1
    assert find(client, attachment, "zzz") == {"text": "ready", "pages": [], "total": 0}


def test_find_says_when_there_is_no_text_yet_or_at_all(
    client: TestClient, library: Library
) -> None:
    waiting = files_service.add_pdf(
        library.db, library.path, make_text_pdf([["soon"]]), "new.pdf"
    ).attachment_id
    _, scan = add(library, "scan.pdf", [])

    assert find(client, waiting, "soon")["text"] == "pending"
    assert find(client, scan, "soon")["text"] == "none"
    assert client.get("/attachments/nope/find", params={"q": "x"}).status_code == 404


def test_parse_splits_words_and_phrases() -> None:
    parsed = [(term.words, term.phrase) for term in parse('Peer-review "Işık Hızı" open')]

    assert parsed == [
        (("peer",), False),
        (("review",), False),
        (("isik", "hizi"), True),
        (("open",), False),
    ]


def test_a_snippet_is_cut_at_words_and_marks_every_match() -> None:
    page = "lead " * 60 + "the target word and another target here " + "tail " * 60

    parts = snippet(page, parse("target"))

    whole = "".join(part.text for part in parts)
    assert whole.startswith("…lead") and whole.endswith("…")
    assert [part.text for part in parts if part.hit] == ["target", "target"]
    assert len(whole) < 320
    assert snippet("nothing here", parse("absent")) == [Segment("nothing here", hit=False)]


def test_fold_with_map_agrees_with_fold_and_points_back() -> None:
    sample = "Straße İĞNE ﬁkir é é ½"

    folded, origin = fold_with_map(sample)

    assert folded == fold(sample)
    assert len(folded) == len(origin)
    at = folded.index("fikir")
    assert sample[origin[at]] == "ﬁ" and sample[origin[at + 2]] == "k"


# --- acceptance ------------------------------------------------------------------------

# fmt: off
_WORDS = [
    "method", "study", "result", "review", "interview", "theory", "data", "analysis", "model",
    "participant", "school", "history", "language", "patient", "trial", "archive", "policy",
    "evidence", "measure", "sample", "öğretmen", "çalışma", "ışık", "yöntem", "bulgu",
]
# fmt: on


@pytest.fixture(scope="module")
def big(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """2000 papers with a 12-page PDF's worth of text each: 24 000 pages."""
    path = tmp_path_factory.mktemp("big") / "library"
    make_library(path, 2000)
    rng = random.Random(44)
    library = open_library(path)
    with library.db.write_session() as session:
        files = FilesRepository(session)
        for number, paper_id in enumerate(sorted(PaperService(session).library_ids())):
            sha = f"{number:064d}"
            attachment = files.add_attachment(paper_id, rel_path=f"files/{sha}.pdf", sha256=sha)
            pages = [
                PageText(index, " ".join(rng.choices(_WORDS, k=350)) + f" rare{number}x{index}")
                for index in range(12)
            ]
            FulltextRepository(session).replace(attachment.id, pages)
    library.close()
    return path


@pytest.mark.timing
def test_task_44_acceptance_search_in_2000_papers_under_200_ms(big: Path) -> None:
    library = open_library(big)
    with make_client(library) as client:
        search(client, "warm up")
        for query in (
            "rare1500x7",
            "öğretmen",
            '"interview theory"',
            "method analysis isik",
            "mod",
        ):
            # The best of five: the limit is the search's, not the machine's other work.
            took: list[float] = []
            found: dict[str, Any] = {}
            for _ in range(5):
                started = time.perf_counter()
                found = search(client, query)
                took.append((time.perf_counter() - started) * 1000)
            assert found["papers"], query
            print(query, found["total_pages"], round(min(took)), found["elapsed_ms"])
            assert min(took) < 200, (query, took)
