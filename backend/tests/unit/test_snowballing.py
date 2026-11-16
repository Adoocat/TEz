"""Task 36: snowballing rounds. Sources are fakes here; test_citations.py checks the real
ones against recorded responses.

Acceptance: a paper already in the review is not taken in again; rounds are numbered and
counted per round for PRISMA's other-methods branch; new papers enter screening.
"""

import asyncio
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.core.errors import ErrorCode, TezError
from tez.main import create_app
from tez.modules.jobs.models import ProcessingJob
from tez.modules.library.models import IdentifierScheme
from tez.modules.library.repository import LibraryRepository
from tez.modules.library.service import Library, open_library
from tez.modules.reviews import service as reviews_service
from tez.modules.reviews.models import Decision, RecordOrigin, ReviewMethod, ScreeningStage
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.screening.service import ScreeningService
from tez.modules.search.providers.base import DEFAULT_LIMIT, OnWait, ProviderResult
from tez.modules.search.schemas import NormalizedRecord
from tez.modules.snowballing import service
from tez.modules.snowballing.sources import CitationSource, Direction, Seed

TA = ScreeningStage.TITLE_ABSTRACT


class FakeSource:
    """Answers from a table: (source DOI of the seed, direction) -> papers."""

    def __init__(self, name: str, answers: Mapping[tuple[str, Direction], list[str]]) -> None:
        self.name = name
        self.answers = answers
        self.asked: list[tuple[str, Direction]] = []

    async def citations(
        self,
        seed: Seed,
        direction: Direction,
        *,
        limit: int = DEFAULT_LIMIT,
        on_wait: OnWait | None = None,
    ) -> ProviderResult:
        doi = seed.identifiers.get(IdentifierScheme.DOI, "")
        self.asked.append((doi, direction))
        titles = self.answers.get((doi, direction), [])
        records = tuple(
            NormalizedRecord(title=title, identifiers={IdentifierScheme.DOI: doi_of(title)})
            for title in titles[:limit]
        )
        return ProviderResult(self.name, f"{direction}:{doi}", records=records)


def doi_of(title: str) -> str:
    return f"10.5555/{title.lower().replace(' ', '-')}"


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    opened = open_library(tmp_path / "lib", create=True)
    yield opened
    opened.close()


def paper(library: Library, title: str) -> str:
    with library.db.write_session() as session:
        return (
            LibraryRepository(session)
            .add_paper(title, identifiers=[(IdentifierScheme.DOI, doi_of(title))])
            .id
        )


def review_with(library: Library, *titles: str, include: bool = True) -> tuple[str, list[str]]:
    ids = [paper(library, title) for title in titles]
    with library.db.write_session() as session:
        reviews = ReviewsRepository(session)
        review = reviews.add_review("SLR", method=ReviewMethod.PRISMA2020).id
        for paper_id in ids:
            reviews.add_record(review, paper_id, RecordOrigin.DATABASE, "search-1")
        if include:
            for paper_id in ids:
                ScreeningService(session).decide(review, paper_id, TA, Decision.INCLUDE)
    return review, ids


def run(library: Library, plan: service.RoundPlan, *sources: FakeSource) -> None:
    by_name: dict[str, CitationSource] = {s.name: s for s in sources}
    asyncio.run(service.run_round(library.db, library.path, plan, by_name))


def start(
    library: Library,
    review: str,
    seeds: list[str],
    directions: tuple[Direction, ...] = (Direction.BACKWARD,),
    sources: tuple[str, ...] = ("openalex",),
) -> service.RoundPlan:
    started = service.start_round(
        library.db, review, seeds, list(directions), list(sources), limit=50
    )
    with library.db.session() as session:
        job = session.get(ProcessingJob, started.job_id)
        assert job is not None
        return service.RoundPlan.of(job.payload_json)


def origins(library: Library, review: str) -> dict[str, tuple[RecordOrigin, str | None]]:
    return {
        r.paper_id: (r.origin, r.origin_ref) for r in reviews_service.records(library.db, review)
    }


def test_a_round_takes_new_papers_in_once_with_their_seed(library: Library) -> None:
    review, (seed, kept) = review_with(library, "Seed paper", "Already here")
    source = FakeSource(
        "openalex",
        {(doi_of("Seed paper"), Direction.BACKWARD): ["Cited one", "Already here", "Cited one"]},
    )

    plan = start(library, review, [seed])
    run(library, plan, source)

    records = origins(library, review)
    new = [p for p in records if p not in (seed, kept)]
    assert len(new) == 1
    assert records[new[0]] == (RecordOrigin.CITATION_BACKWARD, seed)
    # The paper already in the review keeps its first origin.
    assert records[kept] == (RecordOrigin.DATABASE, "search-1")
    # The new paper waits in the title-abstract queue.
    with library.db.session() as session:
        assert new[0] in ScreeningService(session).queue(review, TA)


def test_rounds_are_numbered_and_counted_per_round(library: Library) -> None:
    review, (seed,) = review_with(library, "Seed paper")
    source = FakeSource(
        "openalex",
        {
            (doi_of("Seed paper"), Direction.FORWARD): ["Citing A", "Citing B"],
            (doi_of("Citing A"), Direction.FORWARD): ["Citing C", "Seed paper"],
        },
    )
    first = start(library, review, [seed], (Direction.FORWARD,))
    run(library, first, source)
    # Round 1's finds are screened in, so they can seed round 2.
    with library.db.write_session() as session:
        for paper_id in [
            r.paper_id for r in reviews_service.records(library.db, review) if r.paper_id != seed
        ]:
            ScreeningService(session).decide(review, paper_id, TA, Decision.INCLUDE)
    by_title = {s.title: s for s in service.seeds(library.db, review)}
    second = start(library, review, [by_title["Citing A"].paper_id], (Direction.FORWARD,))
    run(library, second, source)

    assert (first.round, second.round) == (1, 2)
    assert [
        (c.round, c.identified, c.unique, c.added) for c in service.round_counts(library.db, review)
    ] == [(1, 2, 2, 2), (2, 2, 2, 1)]
    seeds = {s.title: (s.round, s.followed) for s in service.seeds(library.db, review)}
    assert seeds["Seed paper"] == (0, [Direction.FORWARD])
    assert seeds["Citing A"] == (1, [Direction.FORWARD])
    assert seeds["Citing B"] == (1, [])


def test_a_retried_round_does_not_ask_or_add_again(library: Library) -> None:
    review, (seed,) = review_with(library, "Seed paper")
    source = FakeSource("openalex", {(doi_of("Seed paper"), Direction.BACKWARD): ["Cited one"]})
    plan = start(library, review, [seed])

    run(library, plan, source)
    run(library, plan, source)

    assert len(source.asked) == 1
    assert len(reviews_service.records(library.db, review)) == 2
    [view] = service.rounds(library.db, review)
    assert (view.identified, view.added, view.already_in_review) == (1, 1, 0)


def test_both_sources_and_directions_are_runs_of_one_action(library: Library) -> None:
    review, (seed,) = review_with(library, "Seed paper")
    answers = {
        (doi_of("Seed paper"), Direction.BACKWARD): ["Cited one"],
        (doi_of("Seed paper"), Direction.FORWARD): ["Citing one", "Cited one"],
    }
    plan = start(
        library,
        review,
        [seed],
        (Direction.BACKWARD, Direction.FORWARD),
        ("openalex", "semantic_scholar"),
    )

    run(library, plan, FakeSource("openalex", answers), FakeSource("semantic_scholar", answers))

    [view] = service.rounds(library.db, review)
    assert len(view.runs) == 4
    assert (view.identified, view.unique, view.added) == (6, 2, 2)


@pytest.mark.parametrize(
    ("seeds", "sources", "code"),
    [
        (["not-in-review"], ("openalex",), ErrorCode.SNOWBALL_SEED_NOT_IN_REVIEW),
        (None, ("openalex",), ErrorCode.SNOWBALL_SEED_NOT_INCLUDED),
        (None, ("google_scholar",), ErrorCode.SOURCE_UNKNOWN),
    ],
)
def test_a_round_needs_included_seeds_and_known_sources(
    library: Library, seeds: list[str] | None, sources: tuple[str, ...], code: ErrorCode
) -> None:
    review, ids = review_with(library, "Seed paper", include=False)

    with pytest.raises(TezError) as caught:
        start(library, review, seeds or ids, sources=sources)

    assert caught.value.code is code


def test_the_api_queues_a_round_and_lists_seeds_and_rounds(library: Library) -> None:
    review, (seed,) = review_with(library, "Seed paper")
    app = create_app(token=TOKEN, settings=Settings(), library=library)
    with TestClient(app, headers=AUTH) as client:
        seeds = client.get(f"/reviews/{review}/snowball/seeds").json()
        started = client.post(
            f"/reviews/{review}/snowball",
            json={"paper_ids": [seed], "directions": ["forward"], "sources": ["openalex"]},
        )
        listed = client.get(f"/reviews/{review}/snowball").json()

    assert [(s["paper_id"], s["included_at"], s["traceable"]) for s in seeds] == [
        (seed, "title_abstract", True)
    ]
    assert started.status_code == 202
    assert started.json()["round"] == 1
    assert listed == []  # nothing has run yet: the worker takes the job
