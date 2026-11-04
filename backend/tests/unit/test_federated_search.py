"""Task 13 acceptance: one source crashes, the others still arrive, the error is on record."""

import asyncio
import gzip
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from tez.core.errors import ErrorCode, TezError
from tez.modules.library.models import IdentifierScheme, Paper, PaperRelation, VenueType
from tez.modules.library.service import Library, open_library
from tez.modules.reviews.models import ReviewMethod
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.search.models import InitiatedVia, MatchMethod, RunStatus, SearchRun
from tez.modules.search.providers.base import OnWait, ProviderResult, SearchRequest
from tez.modules.search.repository import SearchRepository
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor, SourceState
from tez.modules.search.service import SourceUpdate, run_search

TITLE = "Automated Code Review with Large Language Models: An Empirical Study"


def record(title: str = TITLE, **fields: object) -> NormalizedRecord:
    author = RecordAuthor(display_name="Ayşe Yılmaz")
    return NormalizedRecord.model_validate(
        {"title": title, "authors": (author,), "year": 2024, **fields}
    )


class Fake:
    """A source with a canned answer."""

    def __init__(
        self,
        name: str,
        records: tuple[NormalizedRecord, ...] = (),
        *,
        error: TezError | None = None,
        crash: Exception | None = None,
        wait: float | None = None,
    ) -> None:
        self.name = name
        self._result = ProviderResult(
            name,
            f"translated for {name}",
            records=records,
            total_reported=len(records) + 5,
            raw_pages=(f'{{"raw": "{name}"}}',) if records else (),
            error=error,
        )
        self._crash = crash
        self._wait = wait
        self.requests: list[SearchRequest] = []

    async def search(
        self, request: SearchRequest, *, on_wait: OnWait | None = None
    ) -> ProviderResult:
        self.requests.append(request)
        if self._wait is not None and on_wait is not None:
            on_wait(self._wait)
        if self._crash is not None:
            raise self._crash
        return self._result


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    opened = open_library(tmp_path / "lib", create=True)
    yield opened
    opened.close()


@pytest.fixture
def review_id(library: Library) -> str:
    with library.db.write_session() as session:
        return ReviewsRepository(session).add_review("SLR", method=ReviewMethod.KITCHENHAM_SLR).id


def search(library: Library, review_id: str, *providers: Fake, **kwargs: object) -> str:
    request = SearchRequest("code review", year_from=2020)
    return asyncio.run(
        run_search(library.db, library.path, review_id, request, providers, **kwargs)  # type: ignore[arg-type]
    )


def runs(library: Library, search_id: str) -> dict[str, SearchRun]:
    with library.db.session() as session:
        found = session.scalars(select(SearchRun).where(SearchRun.search_id == search_id))
        return {run.source: run for run in found}


def papers(library: Library) -> list[Paper]:
    with library.db.session() as session:
        return list(session.scalars(select(Paper)))


def test_a_crashing_source_does_not_stop_the_others_and_is_on_record(
    library: Library, review_id: str
) -> None:
    updates: list[SourceUpdate] = []

    search_id = search(
        library,
        review_id,
        Fake("good", (record(identifiers={"doi": "10.1000/a"}),)),
        Fake("crashing", crash=RuntimeError("boom")),
        Fake("rejected", error=TezError(ErrorCode.SOURCE_TIMEOUT, {"source": "rejected"})),
        listener=updates.append,
    )

    found = runs(library, search_id)
    assert found["good"].status is RunStatus.OK
    assert found["good"].retrieved_count == 1
    assert found["crashing"].status is RunStatus.ERROR
    assert json.loads(found["crashing"].error or "")["code"] == "internal.unexpected"
    assert found["rejected"].status is RunStatus.ERROR
    assert json.loads(found["rejected"].error or "")["code"] == "source.timeout"
    assert len(papers(library)) == 1

    final = {
        u.source: u for u in updates if u.state not in (SourceState.WAITING, SourceState.SEARCHING)
    }
    assert final["good"].state is SourceState.DONE
    assert final["crashing"].state is SourceState.FAILED
    assert final["rejected"].error_code == "source.timeout"


def test_partial_results_are_kept_and_marked(library: Library, review_id: str) -> None:
    source = Fake(
        "paged",
        (record(),),
        error=TezError(ErrorCode.SOURCE_KEY_REQUIRED, {"source": "paged"}),
    )

    found = runs(library, search(library, review_id, source))["paged"]

    assert found.status is RunStatus.PARTIAL
    assert found.retrieved_count == 1


def test_a_run_records_what_was_asked(library: Library, review_id: str) -> None:
    search_id = search(library, review_id, Fake("a", (record(),)), initiated_via=InitiatedVia.CLI)

    run = runs(library, search_id)["a"]
    assert run.translated_query == "translated for a"
    assert run.total_reported == 6
    assert run.initiated_via is InitiatedVia.CLI
    assert run.review_id == review_id
    with library.db.session() as session:
        queries = SearchRepository(session).queries(review_id)
    assert [q.query_text for q in queries] == ["code review"]
    assert queries[0].filters_json == {"year_from": 2020, "year_to": None}
    assert run.query_id == queries[0].id


def test_repeating_a_search_reuses_its_query_but_is_a_new_set_of_runs(
    library: Library, review_id: str
) -> None:
    first = search(library, review_id, Fake("a", (record(),)))
    second = search(library, review_id, Fake("a", (record(),)))

    assert first != second
    assert runs(library, first)["a"].query_id == runs(library, second)["a"].query_id
    assert len(papers(library)) == 1


def test_the_raw_answer_goes_to_a_snapshot_in_the_library(library: Library, review_id: str) -> None:
    run = runs(library, search(library, review_id, Fake("a", (record(),))))["a"]

    assert run.snapshot_path is not None
    assert run.snapshot_path.startswith("snapshots/")
    with gzip.open(library.path / run.snapshot_path, "rt", encoding="utf-8") as file:
        snapshot = json.load(file)
    assert snapshot["source"] == "a"
    assert snapshot["translated_query"] == "translated for a"
    assert snapshot["pages"] == ['{"raw": "a"}']


def test_a_snapshot_that_cannot_be_written_does_not_lose_the_run(
    library: Library, review_id: str
) -> None:
    (library.path / "snapshots").rmdir()
    (library.path / "snapshots").write_text("in the way")

    run = runs(library, search(library, review_id, Fake("a", (record(),))))["a"]

    assert run.status is RunStatus.OK
    assert run.snapshot_path is None


def test_a_failed_source_has_no_snapshot(library: Library, review_id: str) -> None:
    run = runs(library, search(library, review_id, Fake("a", crash=RuntimeError())))["a"]

    assert run.snapshot_path is None


def test_sources_are_deduplicated_against_each_other(library: Library, review_id: str) -> None:
    doi = {"doi": "https://doi.org/10.1000/ABC"}
    search_id = search(
        library,
        review_id,
        Fake("a", (record(identifiers=doi), record("A Different Paper About Something Else"))),
        Fake("b", (record(identifiers={"doi": "10.1000/abc"}),)),
    )

    with library.db.session() as session:
        repository = SearchRepository(session)
        found = runs(library, search_id)
        methods = {
            source: [r.match_method for r in repository.results(run.id)]
            for source, run in found.items()
        }
    assert len(papers(library)) == 2
    # Either source may answer first; the second one's copy is the duplicate.
    assert sorted(m.value for ms in methods.values() for m in ms) == ["doi", "new", "new"]


def test_a_paper_keeps_its_values_and_gains_what_it_lacks(library: Library, review_id: str) -> None:
    search(
        library,
        review_id,
        Fake("a", (record(identifiers={"doi": "10.1000/a"}, venue="ICSE"),)),
    )
    search(
        library,
        review_id,
        Fake(
            "b",
            (
                record(
                    identifiers={"doi": "10.1000/a", "s2": "abc"},
                    venue="Other Venue",
                    abstract="Now known.",
                ),
            ),
        ),
    )

    with library.db.session() as session:
        repository_papers = list(session.scalars(select(Paper)))
        assert len(repository_papers) == 1
        paper = repository_papers[0]
        assert paper.venue == "ICSE"
        assert paper.abstract == "Now known."
        assert {i.scheme: i.value for i in paper.identifiers} == {
            IdentifierScheme.DOI: "10.1000/a",
            IdentifierScheme.S2: "abc",
        }


def test_identifiers_are_stored_normalized(library: Library, review_id: str) -> None:
    search(
        library,
        review_id,
        Fake("a", (record(identifiers={"doi": "https://doi.org/10.1000/ABC"}),)),
    )

    with library.db.session() as session:
        paper = session.scalars(select(Paper)).one()
        assert paper.identifiers[0].value == "10.1000/abc"


def test_a_preprint_and_its_publication_are_linked(library: Library, review_id: str) -> None:
    search(
        library,
        review_id,
        Fake("a", (record(identifiers={"arxiv": "2401.00001v2"}, venue_type=VenueType.PREPRINT),)),
    )
    search(
        library,
        review_id,
        Fake("b", (record(identifiers={"doi": "10.1000/a"}, venue_type=VenueType.CONFERENCE),)),
    )

    with library.db.session() as session:
        found = list(session.scalars(select(Paper)))
        relation = session.scalars(select(PaperRelation)).one()
        by_type = {p.venue_type: p.id for p in found}
    assert relation.from_paper_id == by_type[VenueType.PREPRINT]
    assert relation.to_paper_id == by_type[VenueType.CONFERENCE]


def test_a_record_holding_ids_of_two_known_papers_does_not_break_the_run(
    library: Library, review_id: str
) -> None:
    """DOI wins the match, and the arXiv id stays with the preprint that already has it."""
    search(
        library,
        review_id,
        Fake(
            "first",
            (
                record(identifiers={"arxiv": "2401.00001"}, venue_type=VenueType.PREPRINT),
                record("A Quite Different Published Paper Title", identifiers={"doi": "10.1000/a"}),
            ),
        ),
    )

    search_id = search(
        library,
        review_id,
        Fake("both", (record(identifiers={"doi": "10.1000/a", "arxiv": "2401.00001"}),)),
    )

    assert runs(library, search_id)["both"].status is RunStatus.OK
    assert len(papers(library)) == 2


def test_an_unusable_identifier_cannot_merge_papers(library: Library, review_id: str) -> None:
    search(
        library,
        review_id,
        Fake(
            "a",
            (
                record("First Quite Distinct Paper Title Here", identifiers={"doi": "n/a"}),
                record("Second Rather Unrelated Article Name", identifiers={"doi": "n/a"}),
            ),
        ),
    )

    assert len(papers(library)) == 2


def test_progress_is_reported_for_each_source(library: Library, review_id: str) -> None:
    updates: list[SourceUpdate] = []

    search(library, review_id, Fake("a", (record(),), wait=7.0), listener=updates.append)

    assert [u.state for u in updates] == [
        SourceState.WAITING,
        SourceState.SEARCHING,
        SourceState.RATE_LIMITED,
        SourceState.DONE,
    ]
    assert updates[2].wait_seconds == 7.0
    assert updates[3].retrieved == 1
    assert updates[3].total_reported == 6


def test_a_storage_failure_is_recorded_and_forgets_what_it_created(
    library: Library, review_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = SearchRepository.add_run
    calls: list[str] = []

    def failing_once(self: SearchRepository, *args: Any, **kwargs: Any) -> SearchRun:
        calls.append(kwargs["source"])
        if len(calls) == 1:
            raise OperationalError("insert", {}, Exception("disk full"))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(SearchRepository, "add_run", failing_once)

    search_id = search(library, review_id, Fake("a", (record(),)))

    run = runs(library, search_id)["a"]
    assert run.status is RunStatus.ERROR
    assert json.loads(run.error or "")["code"] == "internal.unexpected"
    assert papers(library) == []  # Its paper went with the failed transaction.


def test_a_paper_lost_with_a_failed_transaction_is_not_matched_later(
    library: Library, review_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = SearchRepository.add_run
    calls: list[str] = []

    def failing_once(self: SearchRepository, *args: Any, **kwargs: Any) -> SearchRun:
        calls.append(kwargs["source"])
        if len(calls) == 1:
            raise OperationalError("insert", {}, Exception("disk full"))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(SearchRepository, "add_run", failing_once)

    search_id = search(library, review_id, Fake("a", (record(),)), Fake("b", (record(),)))

    found = runs(library, search_id)
    assert {run.status for run in found.values()} == {RunStatus.OK, RunStatus.ERROR}
    assert len(papers(library)) == 1


def test_every_result_keeps_its_rank(library: Library, review_id: str) -> None:
    source = Fake(
        "a",
        (
            record("First Quite Distinct Paper Title Here"),
            record("Second Rather Unrelated Article Name"),
        ),
    )

    run = runs(library, search(library, review_id, source))["a"]

    with library.db.session() as session:
        results = SearchRepository(session).results(run.id)
    assert [r.rank for r in results] == [1, 2]
    assert all(r.match_method is MatchMethod.NEW for r in results)
