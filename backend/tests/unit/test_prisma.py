"""Task 34: PRISMA 2020 counts, derived from the append-only records.

Acceptance: hand-counted example reviews; the invariants between boxes; counts follow a
corrected decision. Also Task 33's "not retrieved" box and Task 37's theses box.
"""

import asyncio
import base64
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
from tez.modules.prisma.schemas import Branch, PrismaCounts
from tez.modules.search import queries
from tez.modules.search.models import RunMethod
from tez.modules.search.providers.base import DEFAULT_LIMIT, OnWait, ProviderResult
from tez.modules.search.schemas import NormalizedRecord
from tez.modules.snowballing import service as snowballing
from tez.modules.snowballing.sources import CitationSource, Direction, Seed


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    opened = open_library(tmp_path / "lib", create=True)
    yield opened
    opened.close()


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(token=TOKEN, settings=Settings(), library=library)
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


def ris(*titles: str) -> str:
    return "".join(
        f"TY  - JOUR\nTI  - Paper {t}\nDO  - 10.5555/{t}\nPY  - 2024\nER  - \n" for t in titles
    )


class Review:
    """A review built through the API, with helpers named after what a user does."""

    def __init__(self, client: TestClient, library: Library) -> None:
        self.client = client
        self.library = library
        self.id: str = client.post("/reviews", json={"title": "SLR"}).json()["id"]
        self.papers: dict[str, str] = {}
        self.criteria: dict[str, str] = {}

    def criterion(self, kind: str, code: str, stage: str | None = None) -> None:
        made = self.client.post(
            f"/reviews/{self.id}/criteria",
            json={"kind": kind, "code": code, "text": code, "stage": stage},
        ).json()
        self.criteria[code] = made["id"]

    def search(self, source: str, *titles: str, take: tuple[str, ...] = ()) -> None:
        """A database export, logged as a run; `take` goes into the review."""
        response = self.client.post(
            "/imports",
            json={
                "file_name": f"{source}.ris",
                "content_base64": base64.b64encode(ris(*titles).encode()).decode(),
                "review_id": self.id,
                "log": {"source": source},
            },
        )
        assert response.status_code in (200, 201), response.text
        self._learn_titles()
        ids = [self.papers[t] for t in take]
        if ids:
            self.client.post(f"/reviews/{self.id}/records", json={"paper_ids": ids})

    def grey(self, title: str, kind: str = "thesis") -> None:
        added = self.client.post(
            f"/reviews/{self.id}/grey-literature",
            json={
                "kind": kind,
                "source": "By hand",
                "title": f"Paper {title}",
                "doi": f"10.5555/{title}",
            },
        )
        assert added.status_code == 201, added.text
        self.papers[title] = added.json()["paper_id"]

    def snowball(self, seed: str, *found: str) -> None:
        """A backward round from `seed` whose source answers `found`."""
        plan = snowballing.RoundPlan(
            review_id=self.id,
            search_id=f"snow-{seed}",
            round=1,
            seeds=(self.papers[seed],),
            directions=(Direction.BACKWARD,),
            sources=("openalex",),
            limit=50,
        )
        source = FixedCitations([f"Paper {t}" for t in found], [f"10.5555/{t}" for t in found])
        sources: dict[str, CitationSource] = {"openalex": source}
        asyncio.run(snowballing.run_round(self.library.db, self.library.path, plan, sources))
        self._learn_titles()

    def decide(self, stage: str, title: str, decision: str, reason: str | None = None) -> None:
        response = self.client.post(
            f"/reviews/{self.id}/screening/{stage}/decisions",
            json={
                "paper_id": self.papers[title],
                "decision": decision,
                "criterion_id": self.criteria[reason] if reason else None,
            },
        )
        assert response.status_code == 201, response.text

    def counts(self) -> PrismaCounts:
        response = self.client.get(f"/reviews/{self.id}/prisma")
        assert response.status_code == 200, response.text
        return PrismaCounts.model_validate(response.json())

    def _learn_titles(self) -> None:
        """Map short titles to the papers the review's runs found."""
        runs = queries.runs_by_method(self.library.db, self.id, list(RunMethod))
        with self.library.db.session() as session:
            cards = PaperService(session).cards({p for run in runs for p in run.paper_ids})
        for paper_id, card in cards.items():
            self.papers.setdefault(card.paper.title.removeprefix("Paper "), paper_id)


class FixedCitations:
    name = "openalex"

    def __init__(self, titles: list[str], dois: list[str]) -> None:
        self.records = tuple(
            NormalizedRecord(title=t, identifiers={IdentifierScheme.DOI: d})
            for t, d in zip(titles, dois, strict=True)
        )

    async def citations(
        self,
        seed: Seed,
        direction: Direction,
        *,
        limit: int = DEFAULT_LIMIT,
        on_wait: OnWait | None = None,
    ) -> ProviderResult:
        return ProviderResult(self.name, f"cited_by:{seed.paper_id}", records=self.records)


def flow(branch: Branch) -> dict[str, Any]:
    return branch.model_dump(exclude={"excluded_reports", "sources", "methods"})


def assert_invariants(branch: Branch) -> None:
    assert branch.identified == branch.duplicates + branch.not_taken + branch.screened
    assert branch.screened == branch.excluded + branch.awaiting_screening + branch.sought
    assert branch.sought == branch.not_retrieved + branch.assessed + branch.awaiting_full_text
    assert branch.assessed == sum(r.count for r in branch.excluded_reports) + branch.included


@pytest.fixture
def example(client: TestClient, library: Library) -> Review:
    """The hand-counted review of this file (see the expected numbers below)."""
    review = Review(client, library)
    review.criterion("exclusion", "E1", "title_abstract")
    review.criterion("exclusion", "E2", "full_text")
    # Databases: Scopus A B C D, Web of Science B C E; E is never taken into the review.
    review.search("Scopus", "A", "B", "C", "D", take=("A", "B", "C", "D"))
    review.search("Web of Science", "B", "C", "E")
    # Other methods: a thesis T by hand, and A again as a web page (a duplicate).
    review.grey("T")
    review.grey("A", kind="web_page")
    # Title-abstract decisions, then snowballing from A: F is new, B is already in.
    review.decide("title_abstract", "A", "include")
    review.decide("title_abstract", "B", "include")
    review.decide("title_abstract", "C", "exclude", "E1")
    review.snowball("A", "F", "B")
    review.decide("title_abstract", "T", "include")
    review.decide("title_abstract", "F", "maybe")
    # Full text.
    review.decide("full_text", "A", "include")
    review.decide("full_text", "B", "not_retrieved")
    review.decide("full_text", "T", "exclude", "E2")
    return review


def test_a_hand_counted_review(example: Review) -> None:
    counts = example.counts()

    assert flow(counts.databases) == {
        "identified": 7,  # 4 + 3
        "unlogged": 0,
        "duplicates": 2,  # B and C again
        "not_taken": 1,  # E
        "screened": 4,
        "excluded": 1,  # C
        "awaiting_screening": 1,  # D
        "sought": 2,  # A, B
        "not_retrieved": 1,  # B
        "assessed": 1,
        "awaiting_full_text": 0,
        "included": 1,  # A
    }
    assert [(s.source, s.runs, s.identified) for s in counts.databases.sources] == [
        ("Scopus", 1, 4),
        ("Web of Science", 1, 3),
    ]
    assert flow(counts.other_methods) == {
        "identified": 4,  # T, A (web page), F and B (snowballing)
        "unlogged": 0,
        "duplicates": 2,  # A and B came through the databases
        "not_taken": 0,
        "screened": 2,  # T, F
        "excluded": 0,
        "awaiting_screening": 0,
        "sought": 2,
        "not_retrieved": 0,
        "assessed": 1,  # T
        "awaiting_full_text": 1,  # F (maybe at title-abstract, not decided at full text)
        "included": 0,
    }
    # The thesis by hand sits in the theses box; snowballing is counted per round.
    assert [(m.method, m.round, m.identified) for m in counts.other_methods.methods] == [
        ("website", None, 1),
        ("thesis", None, 1),
        ("citation_backward", 1, 2),
    ]
    assert [(r.code, r.count) for r in counts.other_methods.excluded_reports] == [("E2", 1)]
    assert counts.included == 1


def test_the_boxes_add_up(example: Review) -> None:
    counts = example.counts()

    assert_invariants(counts.databases)
    assert_invariants(counts.other_methods)
    assert counts.databases.identified == sum(s.identified for s in counts.databases.sources)
    assert counts.other_methods.identified == sum(
        m.identified for m in counts.other_methods.methods
    )


def test_counts_follow_a_corrected_decision(example: Review) -> None:
    example.decide("full_text", "A", "exclude", "E2")  # was include
    example.decide("title_abstract", "B", "exclude", "E1")  # B leaves full text

    counts = example.counts()

    assert (counts.databases.included, counts.included) == (0, 0)
    assert [(r.code, r.count) for r in counts.databases.excluded_reports] == [("E2", 1)]
    assert (counts.databases.excluded, counts.databases.sought) == (2, 1)
    assert counts.databases.not_retrieved == 0
    assert_invariants(counts.databases)


def test_an_empty_review_counts_nothing(client: TestClient, library: Library) -> None:
    counts = Review(client, library).counts()

    assert counts.databases.identified == counts.other_methods.identified == 0
    assert counts.included == 0
    assert client.get("/reviews/missing/prisma").status_code == 404


def test_repeated_imports_of_a_saved_search_are_all_counted(
    client: TestClient, library: Library
) -> None:
    review = Review(client, library)
    review.search("Scopus", "A", "B", take=("A", "B"))
    review.search("Scopus", "A", "B", "C", take=("C",))

    counts = review.counts()

    assert [(s.source, s.runs, s.identified) for s in counts.databases.sources] == [
        ("Scopus", 2, 5)
    ]
    assert (counts.databases.duplicates, counts.databases.screened) == (2, 3)
