"""The search API over the service: start, follow, read back. No network: sources are fakes."""

from collections.abc import AsyncGenerator, Iterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.core.errors import ErrorCode
from tez.main import create_app
from tez.modules.library.service import Library, open_library
from tez.modules.reviews.models import ReviewMethod
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.search.providers.base import OnWait, ProviderResult, SearchProvider, SearchRequest
from tez.modules.search.providers.registry import SourceAccess, read_access
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor
from tez.modules.settings.secrets import MemorySecretStore, SecretName, SecretStoreUnavailable

TITLE = "Automated Code Review with Large Language Models: An Empirical Study"


def record(title: str = TITLE, **fields: Any) -> NormalizedRecord:
    author = RecordAuthor(display_name="Ayşe Yılmaz")
    return NormalizedRecord.model_validate(
        {"title": title, "authors": (author,), "year": 2024, **fields}
    )


class Fake:
    def __init__(self, name: str, result: ProviderResult | None, crash: bool = False) -> None:
        self.name = name
        self._result = result
        self._crash = crash

    async def search(
        self, request: SearchRequest, *, on_wait: OnWait | None = None
    ) -> ProviderResult:
        if on_wait is not None:
            on_wait(3.0)
        if self._crash or self._result is None:
            raise RuntimeError("boom")
        return self._result


ANSWERS: dict[str, Fake] = {
    "openalex": Fake(
        "openalex",
        ProviderResult(
            "openalex",
            "q-oa",
            records=(
                record(identifiers={"doi": "10.1000/a"}, abstract="Abstract text."),
                record("A Different Paper About Something Else"),
            ),
            total_reported=50,
            raw_pages=("{}",),
        ),
    ),
    "crossref": Fake(
        "crossref",
        ProviderResult(
            "crossref",
            "q-cr",
            records=(record(identifiers={"doi": "10.1000/a"}),),
            total_reported=9,
            raw_pages=("{}",),
        ),
    ),
    "arxiv": Fake("arxiv", None, crash=True),
}


@asynccontextmanager
async def fake_factory(
    names: Sequence[str], access: SourceAccess
) -> AsyncGenerator[Sequence[SearchProvider]]:
    yield [ANSWERS[name] for name in names]


@pytest.fixture
def library(tmp_path: Path) -> Library:
    return open_library(tmp_path / "lib", create=True)


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(
        token=TOKEN,
        settings=Settings(),
        library=library,
        secret_store=MemorySecretStore(),
        provider_factory=fake_factory,
    )
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def review_id(library: Library) -> str:
    with library.db.write_session() as session:
        return ReviewsRepository(session).add_review("SLR", method=ReviewMethod.PRISMA2020).id


def start(client: TestClient, review_id: str, **fields: Any) -> str:
    body = {
        "review_id": review_id,
        "query": "code review",
        "sources": ["openalex", "crossref", "arxiv"],
        **fields,
    }
    response = client.post("/searches", json=body)
    assert response.status_code == 202, response.text
    return response.json()["search_id"]


def events(client: TestClient, search_id: str) -> list[tuple[str, str]]:
    """Reads the stream to its end: (event name, data) pairs."""
    found: list[tuple[str, str]] = []
    with client.stream("GET", f"/searches/{search_id}/events") as stream:
        name = ""
        for line in stream.iter_lines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                found.append((name, line.removeprefix("data: ")))
    return found


def test_a_search_runs_and_a_crashed_source_is_only_one_row(
    client: TestClient, review_id: str
) -> None:
    search_id = start(client, review_id)

    stream = events(client, search_id)

    assert stream[-1][0] == "finished"
    assert any('"state":"done"' in data for name, data in stream if name == "source")

    overview = client.get(f"/searches/{search_id}").json()
    assert overview["review_id"] == review_id
    assert overview["query"] == "code review"
    by_source = {run["source"]: run for run in overview["runs"]}
    assert by_source["openalex"]["status"] == "ok"
    assert by_source["openalex"]["translated_query"] == "q-oa"
    assert by_source["openalex"]["total_reported"] == 50
    assert by_source["arxiv"]["status"] == "error"
    assert by_source["arxiv"]["error"]["code"] == "internal.unexpected"
    assert overview["retrieved"] == 3
    assert overview["unique"] == 2
    assert overview["duplicates"] == 1


def test_results_are_deduplicated_with_their_sources(client: TestClient, review_id: str) -> None:
    search_id = start(client, review_id)
    events(client, search_id)

    rows = client.get(f"/searches/{search_id}/results").json()

    assert len(rows) == 2
    merged = next(row for row in rows if row["doi"] == "10.1000/a")
    assert {s["source"] for s in merged["sources"]} == {"openalex", "crossref"}
    assert {s["match_method"] for s in merged["sources"]} == {"new", "doi"}
    assert merged["first_author"] == "Ayşe Yılmaz"
    assert merged["author_count"] == 1
    assert merged["abstract"] == "Abstract text."


def test_history_lists_the_searches_of_a_review_newest_first(
    client: TestClient, review_id: str
) -> None:
    first = start(client, review_id, query="first query", year_from=2020)
    events(client, first)
    second = start(client, review_id, query="second query")
    events(client, second)

    history = client.get("/searches", params={"review_id": review_id}).json()

    assert [item["search_id"] for item in history] == [second, first]
    assert history[1]["query"] == "first query"
    assert history[1]["filters"] == {"year_from": 2020, "year_to": None}
    assert history[1]["initiated_via"] == "gui"
    assert history[1]["started_at"]
    assert client.get("/searches", params={"review_id": "other"}).json() == []


def test_rows_and_counts_know_what_was_kept(client: TestClient, review_id: str) -> None:
    search_id = start(client, review_id)
    events(client, search_id)
    rows = client.get(f"/searches/{search_id}/results").json()
    assert not any(row["in_library"] or row["in_review"] for row in rows)
    kept = rows[0]["paper_id"]

    client.post("/library/papers", json={"paper_ids": [kept]})
    client.post(f"/reviews/{review_id}/records", json={"paper_ids": [kept], "search_id": search_id})

    after = {row["paper_id"]: row for row in client.get(f"/searches/{search_id}/results").json()}
    assert after[kept]["in_library"] is True
    assert after[kept]["in_review"] is True
    assert client.get(f"/searches/{search_id}").json()["in_library"] == 1


def test_events_replay_the_current_state_to_a_late_subscriber(
    client: TestClient, review_id: str
) -> None:
    search_id = start(client, review_id)
    events(client, search_id)

    again = events(client, search_id)

    assert again[-1][0] == "finished"
    assert {name for name, _ in again[:-1]} == {"source"}


def test_an_unknown_source_is_rejected(client: TestClient, review_id: str) -> None:
    response = client.post(
        "/searches", json={"review_id": review_id, "query": "x", "sources": ["google"]}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == ErrorCode.SOURCE_UNKNOWN.value


def test_an_unknown_review_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/searches", json={"review_id": "nope", "query": "x", "sources": ["crossref"]}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == ErrorCode.REVIEW_NOT_FOUND.value


@pytest.mark.parametrize(
    "fields",
    [
        {"query": "   "},
        {"sources": []},
        {"limit": 0},
        {"limit": 100000},
        {"year_from": 2024, "year_to": 2020},
    ],
)
def test_an_invalid_request_is_rejected(
    client: TestClient, review_id: str, fields: dict[str, Any]
) -> None:
    body = {"review_id": review_id, "query": "x", "sources": ["crossref"], **fields}

    assert client.post("/searches", json=body).status_code == 422


def test_an_unknown_search_is_not_found(client: TestClient) -> None:
    assert client.get("/searches/nope").status_code == 404
    assert client.get("/searches/nope/events").status_code == 404
    assert client.get("/searches/nope/results").json() == []


def test_searching_needs_the_token(client: TestClient) -> None:
    response = client.post(
        "/searches",
        headers={"Authorization": "Bearer wrong"},
        json={"review_id": "x", "query": "x", "sources": ["crossref"]},
    )

    assert response.status_code == 401


# --- access ----------------------------------------------------------------------------


def test_keys_come_from_the_keyring() -> None:
    store = MemorySecretStore()
    store.set(SecretName.OPENALEX_API_KEY, "oa-key")
    store.set(SecretName.SEMANTIC_SCHOLAR_API_KEY, "s2-key")

    assert read_access(store, "a@b.org") == SourceAccess("a@b.org", "oa-key", "s2-key")


def test_no_keyring_means_searching_without_keys() -> None:
    class NoKeyring(MemorySecretStore):
        def get(self, name: str) -> str | None:
            raise SecretStoreUnavailable

    assert read_access(NoKeyring(), None) == SourceAccess()
