"""PRISMA 2020 flow counts, derived on every read from the append-only records (Task 34).

Sources: `search_run` and `search_result` (what each search, snowballing round or grey-
literature entry found), `review_record` (what entered the review, and how) and the owner's
current screening decisions, read through the screening service. Nothing is stored.

Branches. A review record belongs to the databases branch when it entered through a database
search (origin `database`), else to the other-methods branch (snowballing, websites,
organisations, registers, theses). For each branch:

- identified: the records its runs returned, repeats included, plus records that entered
  the review without a logged run (`unlogged`, from before runs were kept);
- duplicates: identified records that are the same paper as another one: a repeat within
  the branch, or a paper the other branch brought into the review;
- not_taken: papers a search found that were never taken into the review;
- screened, excluded, awaiting_screening: title-abstract screening of the branch's records;
- sought, not_retrieved, assessed, awaiting_full_text, excluded_reports (per reason) and
  included: full-text screening of those that passed.
"""

from collections import Counter
from collections.abc import Iterable, Sequence

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.prisma.schemas import (
    Branch,
    DatabasesBranch,
    OtherMethodCount,
    OtherMethodsBranch,
    PrismaCounts,
    ReasonCount,
    SourceCount,
)
from tez.modules.reviews import service as reviews_service
from tez.modules.reviews.models import Decision, RecordOrigin, ScreeningStage
from tez.modules.screening.schemas import RecordState
from tez.modules.screening.service import CurrentDecision, ScreeningService
from tez.modules.search import queries as search_queries
from tez.modules.search.models import CITATION_METHODS, OTHER_METHODS, RunMethod
from tez.modules.search.queries import RunFacts


def _screening(
    db: Database, review_id: str
) -> tuple[dict[str, RecordState], dict[str, CurrentDecision], set[str]]:
    """Title-abstract states, full-text decisions in force, and the full-text queue."""
    with db.session() as session:
        screening = ScreeningService(session)
        title_abstract = {
            e.paper_id: e.state for e in screening.entries(review_id, ScreeningStage.TITLE_ABSTRACT)
        }
        full_text = screening.current(review_id, ScreeningStage.FULL_TEXT)
        queue = set(screening.queue(review_id, ScreeningStage.FULL_TEXT))
    return title_abstract, full_text, queue


def _branch_counts(
    runs: Sequence[RunFacts],
    own: set[str],
    elsewhere: set[str],
    title_abstract: dict[str, RecordState],
    full_text: dict[str, CurrentDecision],
    full_text_queue: set[str],
    reasons: dict[str, tuple[str, str]],
) -> Branch:
    returned = [paper_id for run in runs for paper_id in run.paper_ids]
    unique = set(returned)
    unlogged = own - unique
    identified = len(returned) + len(unlogged)
    duplicates = len(returned) - len(unique) + len(unique & elsewhere)
    not_taken = len(unique - own - elsewhere)

    states = Counter(title_abstract.get(p, RecordState.UNDECIDED) for p in own)
    sought = own & full_text_queue
    decided = Counter(full_text[p].decision for p in sought if p in full_text)
    excluded_reports = Counter(
        full_text[p].criterion_id
        for p in sought
        if p in full_text and full_text[p].decision is Decision.EXCLUDE
    )
    order = list(reasons)
    by_reason = [
        ReasonCount(
            criterion_id=criterion_id,
            code=reasons[criterion_id][0] if criterion_id in reasons else None,
            text=reasons[criterion_id][1] if criterion_id in reasons else None,
            count=count,
        )
        for criterion_id, count in sorted(
            excluded_reports.items(),
            key=lambda item: order.index(item[0]) if item[0] in order else len(order),
        )
    ]
    assessed = decided[Decision.INCLUDE] + decided[Decision.EXCLUDE]
    return Branch(
        identified=identified,
        unlogged=len(unlogged),
        duplicates=duplicates,
        not_taken=not_taken,
        screened=len(own),
        excluded=states[RecordState.EXCLUDE],
        awaiting_screening=states[RecordState.UNDECIDED],
        sought=len(sought),
        not_retrieved=decided[Decision.NOT_RETRIEVED],
        assessed=assessed,
        awaiting_full_text=len(sought) - decided[Decision.NOT_RETRIEVED] - assessed,
        excluded_reports=by_reason,
        included=decided[Decision.INCLUDE],
    )


def _sources(runs: Iterable[RunFacts]) -> list[SourceCount]:
    found: dict[str, SourceCount] = {}
    for run in runs:
        now = found.get(run.source, SourceCount(source=run.source, runs=0, identified=0))
        found[run.source] = SourceCount(
            source=run.source, runs=now.runs + 1, identified=now.identified + len(run.paper_ids)
        )
    return list(found.values())


def _methods(runs: Iterable[RunFacts]) -> list[OtherMethodCount]:
    counts: Counter[tuple[RunMethod, int | None]] = Counter()
    for run in runs:
        round_ = (run.snowball_round or 1) if run.method in CITATION_METHODS else None
        counts[(run.method, round_)] += len(run.paper_ids)
    order: list[RunMethod] = list(OTHER_METHODS)
    return [
        OtherMethodCount(method=method, round=round_, identified=identified)
        for (method, round_), identified in sorted(
            counts.items(), key=lambda item: (item[0][1] or 0, order.index(item[0][0]))
        )
    ]


def counts(db: Database, review_id: str) -> PrismaCounts:
    if not reviews_service.review_exists(db, review_id):
        raise TezError(ErrorCode.REVIEW_NOT_FOUND, {"review_id": review_id}, status=404)
    records = reviews_service.records(db, review_id)
    from_databases = {r.paper_id for r in records if r.origin is RecordOrigin.DATABASE}
    from_others = {r.paper_id for r in records} - from_databases
    database_runs = search_queries.runs_by_method(db, review_id, [RunMethod.DATABASE])
    other_runs = search_queries.runs_by_method(db, review_id, OTHER_METHODS)
    title_abstract, full_text, queue = _screening(db, review_id)
    reasons = {c.id: (c.code, c.text) for c in reviews_service.list_criteria(db, review_id)}

    databases = _branch_counts(
        database_runs, from_databases, from_others, title_abstract, full_text, queue, reasons
    )
    others = _branch_counts(
        other_runs, from_others, from_databases, title_abstract, full_text, queue, reasons
    )
    return PrismaCounts(
        review_id=review_id,
        databases=DatabasesBranch(**databases.model_dump(), sources=_sources(database_runs)),
        other_methods=OtherMethodsBranch(**others.model_dump(), methods=_methods(other_runs)),
        included=databases.included + others.included,
    )
