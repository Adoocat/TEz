"""Snowballing as worker jobs, recorded like searches (plan, Task 36; Wohlin 2014).

A round asks each source, for each seed paper and direction, for the seed's references
(backward) or the papers citing it (forward). Every answer is a `search_run` (method
`citation_backward` or `citation_forward`, the round number, the seed), so PRISMA counts
snowballing from the same append-only record as database searches. The papers found are
matched against the library like search results; those not yet in the review become
`review_record`s with the citation origin and the seed in `origin_ref`, and so enter
screening. A paper already in the review is never taken in twice.

Rounds are numbered: a seed from a database search (or added by hand) is round 0, a seed
found by round n is round n, and a round's number is one more than its latest seed's.
"""

import asyncio
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tez.core.db import Database, utcnow
from tez.core.errors import ErrorCode, TezError
from tez.modules.jobs import service as jobs_service
from tez.modules.jobs.registry import JobContext
from tez.modules.library.models import IdentifierScheme
from tez.modules.library.paper_service import PaperService
from tez.modules.reviews import service as reviews_service
from tez.modules.reviews.models import RecordOrigin
from tez.modules.screening import service as screening_service
from tez.modules.search import queries as search_queries
from tez.modules.search import service as search_service
from tez.modules.search.models import CITATION_METHODS, InitiatedVia, RunMethod
from tez.modules.search.providers.base import ProviderResult
from tez.modules.search.providers.registry import read_access
from tez.modules.search.queries import RunFacts
from tez.modules.settings import service as settings_service
from tez.modules.settings.secrets import KeyringSecretStore
from tez.modules.snowballing.schemas import (
    RoundCount,
    SnowballRoundView,
    SnowballRunView,
    SnowballSeed,
    SnowballStarted,
)
from tez.modules.snowballing.sources import (
    CITATION_SOURCES,
    CitationSource,
    Direction,
    Seed,
    open_citation_sources,
)
from tez.shared.ids import new_id

logger = logging.getLogger(__name__)

SNOWBALL_JOB = "snowball.round"

METHODS = {
    Direction.BACKWARD: RunMethod.CITATION_BACKWARD,
    Direction.FORWARD: RunMethod.CITATION_FORWARD,
}
DIRECTIONS = {method: direction for direction, method in METHODS.items()}
ORIGINS = {
    RunMethod.CITATION_BACKWARD: RecordOrigin.CITATION_BACKWARD,
    RunMethod.CITATION_FORWARD: RecordOrigin.CITATION_FORWARD,
}
_TRACEABLE = (
    IdentifierScheme.OPENALEX,
    IdentifierScheme.S2,
    IdentifierScheme.DOI,
    IdentifierScheme.ARXIV,
)


@dataclass(frozen=True)
class RoundPlan:
    """What one snowballing action asks for; the job's payload."""

    review_id: str
    search_id: str
    round: int
    seeds: tuple[str, ...]
    directions: tuple[Direction, ...]
    sources: tuple[str, ...]
    limit: int
    initiated_via: InitiatedVia = InitiatedVia.GUI

    def payload(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "search_id": self.search_id,
            "round": self.round,
            "seeds": list(self.seeds),
            "directions": [d.value for d in self.directions],
            "sources": list(self.sources),
            "limit": self.limit,
            "initiated_via": self.initiated_via.value,
        }

    @classmethod
    def of(cls, payload: Mapping[str, Any]) -> "RoundPlan":
        return cls(
            review_id=str(payload["review_id"]),
            search_id=str(payload["search_id"]),
            round=int(payload["round"]),
            seeds=tuple(str(s) for s in payload["seeds"]),
            directions=tuple(Direction(d) for d in payload["directions"]),
            sources=tuple(str(s) for s in payload["sources"]),
            limit=int(payload["limit"]),
            initiated_via=InitiatedVia(payload.get("initiated_via", "gui")),
        )


def _citation_runs(db: Database, review_id: str) -> list[RunFacts]:
    return search_queries.runs_by_method(db, review_id, CITATION_METHODS)


def _adding_runs(
    records: Sequence[reviews_service.RecordFacts], runs: Sequence[RunFacts]
) -> dict[str, RunFacts]:
    """For each paper snowballing took in, the run that found it first (and so added it)."""
    wanted = {r.paper_id for r in records if r.origin in ORIGINS.values()}
    found: dict[str, RunFacts] = {}
    for run in runs:  # oldest first
        for paper_id in run.paper_ids:
            if paper_id in wanted and paper_id not in found:
                found[paper_id] = run
    return found


def _rounds_of(
    records: Sequence[reviews_service.RecordFacts], runs: Sequence[RunFacts]
) -> dict[str, int]:
    """Each review paper's round: 0 unless snowballing found it."""
    adding = _adding_runs(records, runs)
    return {
        r.paper_id: (adding[r.paper_id].snowball_round or 1) if r.paper_id in adding else 0
        for r in records
    }


def start_round(
    db: Database,
    review_id: str,
    paper_ids: Sequence[str],
    directions: Sequence[Direction],
    sources: Sequence[str],
    *,
    limit: int,
    initiated_via: InitiatedVia = InitiatedVia.GUI,
) -> SnowballStarted:
    """Check the request, number the round and queue it for the worker."""
    if unknown := [s for s in sources if s not in CITATION_SOURCES]:
        raise TezError(ErrorCode.SOURCE_UNKNOWN, {"sources": unknown}, status=422)
    if not reviews_service.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
    records = reviews_service.records(db, review_id)
    seeds = list(dict.fromkeys(paper_ids))
    rounds = _rounds_of(records, _citation_runs(db, review_id))
    if outside := [p for p in seeds if p not in rounds]:
        raise TezError(ErrorCode.SNOWBALL_SEED_NOT_IN_REVIEW, {"paper_ids": outside}, status=422)
    # Wohlin's start set: the papers included so far, at either stage.
    included = screening_service.included_papers(db, review_id)
    if pending := [p for p in seeds if p not in included]:
        raise TezError(ErrorCode.SNOWBALL_SEED_NOT_INCLUDED, {"paper_ids": pending}, status=422)
    plan = RoundPlan(
        review_id=review_id,
        search_id=new_id(),
        round=1 + max(rounds[p] for p in seeds),
        seeds=tuple(seeds),
        directions=tuple(dict.fromkeys(directions)),
        sources=tuple(s for s in CITATION_SOURCES if s in sources),
        limit=limit,
        initiated_via=initiated_via,
    )
    with db.write_session() as session:
        job_id = jobs_service.enqueue(
            session, SNOWBALL_JOB, plan.payload(), dedupe_key=f"snowball:{plan.search_id}"
        )
    return SnowballStarted(search_id=plan.search_id, round=plan.round, job_id=job_id)


def _seeds(db: Database, paper_ids: Sequence[str]) -> list[Seed]:
    with db.session() as session:
        cards = PaperService(session).cards(paper_ids)
        return [Seed(p, dict(cards[p].identifiers)) for p in paper_ids if p in cards]


async def _ask(
    source: CitationSource, seed: Seed, direction: Direction, limit: int
) -> ProviderResult:
    """One source's answer for one seed. Whatever goes wrong in there stays in there."""
    try:
        return await source.citations(seed, direction, limit=limit)
    except Exception as exc:  # A bug in one source must not stop the round.
        logger.exception("citation source crashed", extra={"source": source.name})
        error = TezError(ErrorCode.INTERNAL_UNEXPECTED, {"source": source.name, "error": repr(exc)})
        return ProviderResult(source.name, "", error=error)


def take_in(db: Database, plan: RoundPlan) -> int:
    """Put the papers this action found into the review; returns how many were new.

    Safe to repeat: a retried job, or one stopped half way, catches up here.
    """
    added = 0
    for run in _citation_runs(db, plan.review_id):
        if run.search_id != plan.search_id or run.seed_paper_id is None:
            continue
        found = [(paper_id, run.seed_paper_id) for paper_id in run.paper_ids]
        added += reviews_service.add_found(db, plan.review_id, found, ORIGINS[run.method])
    return added


async def run_round(
    db: Database,
    library_path: Path,
    plan: RoundPlan,
    sources: Mapping[str, CitationSource],
    *,
    report: Callable[[float], None] = lambda _: None,
    cancelled: Callable[[], bool] = lambda: False,
) -> None:
    """Ask every source for every seed and direction, one answer at a time, and record each.

    One at a time so that papers from one answer are matched by the next. Answers already on
    record for this action (an earlier attempt of the job) are not asked for again.
    """
    done = {
        (run.seed_paper_id, run.method, run.source)
        for run in _citation_runs(db, plan.review_id)
        if run.search_id == plan.search_id
    }
    seeds = _seeds(db, plan.seeds)
    steps = [
        (direction, seed, name)
        for direction in plan.directions
        for seed in seeds
        for name in plan.sources
        if name in sources
    ]
    index = await asyncio.to_thread(search_service.paper_index, db)
    try:
        for number, (direction, seed, name) in enumerate(steps, start=1):
            if cancelled():
                return
            method = METHODS[direction]
            if (seed.paper_id, method, name) not in done:
                executed_at = utcnow()
                result = await _ask(sources[name], seed, direction, plan.limit)
                run = search_service.CitationRun(
                    review_id=plan.review_id,
                    search_id=plan.search_id,
                    method=method,
                    snowball_round=plan.round,
                    seed_paper_id=seed.paper_id,
                    initiated_via=plan.initiated_via,
                )
                await asyncio.to_thread(
                    search_service.record_citation_run,
                    db,
                    library_path,
                    run,
                    result,
                    executed_at,
                    index,
                )
            report(number / (len(steps) + 1))
    finally:
        await asyncio.to_thread(take_in, db, plan)
    report(1.0)


def snowball_job(payload: dict[str, Any], ctx: JobContext) -> None:
    """The `snowball.round` job."""
    plan = RoundPlan.of(payload)
    email = settings_service.read_settings(ctx.db).sources_email
    access = read_access(KeyringSecretStore(), email)

    async def run() -> None:
        async with open_citation_sources(plan.sources, access) as sources:
            await run_round(
                ctx.db,
                ctx.library_path,
                plan,
                sources,
                report=ctx.report,
                cancelled=lambda: ctx.cancelled,
            )

    asyncio.run(run())


# --- reading back ------------------------------------------------------------------------


def _run_view(run: RunFacts) -> SnowballRunView:
    return SnowballRunView(
        seed_paper_id=run.seed_paper_id or "",
        direction=DIRECTIONS[run.method],
        source=run.source,
        status=run.status,
        translated_query=run.translated_query,
        total_reported=run.total_reported,
        retrieved_count=len(run.paper_ids),
        error=run.error,
    )


def rounds(db: Database, review_id: str) -> list[SnowballRoundView]:
    """The review's snowballing actions, newest first, with counts derived from the runs."""
    runs = _citation_runs(db, review_id)
    adding = _adding_runs(reviews_service.records(db, review_id), runs)
    added_by: dict[str, int] = {}
    for run in adding.values():
        key = run.search_id or run.id
        added_by[key] = added_by.get(key, 0) + 1
    actions: dict[str, list[RunFacts]] = {}
    for run in runs:
        actions.setdefault(run.search_id or run.id, []).append(run)
    views: list[SnowballRoundView] = []
    for search_id, own in actions.items():
        unique = len({p for run in own for p in run.paper_ids})
        added = added_by.get(search_id, 0)
        views.append(
            SnowballRoundView(
                search_id=search_id,
                round=own[0].snowball_round or 1,
                started_at=own[0].executed_at,
                directions=[d for d in Direction if any(DIRECTIONS[r.method] is d for r in own)],
                sources=[s for s in CITATION_SOURCES if any(r.source == s for r in own)],
                seeds=len({run.seed_paper_id for run in own}),
                identified=sum(len(run.paper_ids) for run in own),
                unique=unique,
                added=added,
                already_in_review=unique - added,
                runs=[_run_view(run) for run in own],
            )
        )
    views.sort(key=lambda view: view.search_id, reverse=True)
    return views


def round_counts(db: Database, review_id: str) -> list[RoundCount]:
    """Snowballing per round number, for PRISMA's other-methods branch."""
    runs = _citation_runs(db, review_id)
    adding = _adding_runs(reviews_service.records(db, review_id), runs)
    numbers = sorted({run.snowball_round or 1 for run in runs})
    counts: list[RoundCount] = []
    for number in numbers:
        own = [run for run in runs if (run.snowball_round or 1) == number]
        counts.append(
            RoundCount(
                round=number,
                identified=sum(len(run.paper_ids) for run in own),
                unique=len({p for run in own for p in run.paper_ids}),
                added=sum((run.snowball_round or 1) == number for run in adding.values()),
            )
        )
    return counts


def seeds(db: Database, review_id: str) -> list[SnowballSeed]:
    """The review's included papers as seeds: where each came from, the stage it is included
    at and what was already followed from it."""
    if not reviews_service.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
    records = reviews_service.records(db, review_id)
    runs = _citation_runs(db, review_id)
    round_of = _rounds_of(records, runs)
    included = screening_service.included_papers(db, review_id)
    followed: dict[str, set[Direction]] = {}
    for run in runs:
        if run.seed_paper_id is not None:
            followed.setdefault(run.seed_paper_id, set()).add(DIRECTIONS[run.method])
    with db.session() as session:
        cards = PaperService(session).cards(r.paper_id for r in records)
        found: list[SnowballSeed] = []
        for record in records:
            if record.paper_id not in included:
                continue
            card = cards[record.paper_id]
            done = followed.get(record.paper_id, set())
            found.append(
                SnowballSeed(
                    paper_id=record.paper_id,
                    title=card.paper.title,
                    first_author=card.first_author.display_name if card.first_author else None,
                    year=card.paper.year,
                    origin=record.origin,
                    round=round_of[record.paper_id],
                    included_at=included[record.paper_id],
                    traceable=any(s in card.identifiers for s in _TRACEABLE),
                    followed=[d for d in Direction if d in done],
                )
            )
    return found
