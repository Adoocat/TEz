"""Files, reviews/screening, search, jobs and settings repositories, with their constraints."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.unit.repositories.conftest import violates
from tez.core.errors import ErrorCode, TezError
from tez.modules.files.models import TextStatus
from tez.modules.files.repository import FilesRepository
from tez.modules.jobs.models import JobStatus
from tez.modules.jobs.repository import JobsRepository
from tez.modules.library.repository import LibraryRepository
from tez.modules.reviews.models import (
    CriterionKind,
    Decision,
    RecordOrigin,
    ReviewMethod,
    ScreeningStage,
)
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.search.models import InitiatedVia, MatchMethod, RunStatus
from tez.modules.search.repository import ResultInput, SearchRepository
from tez.modules.settings.repository import SettingsRepository

SHA_A = "a" * 64
SHA_B = "b" * 64
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def new_paper(session: Session, title: str = "Paper") -> str:
    return LibraryRepository(session).add_paper(title).id


# --- files ----------------------------------------------------------------------------


def test_attachment_lookup_by_sha256(session: Session) -> None:
    files = FilesRepository(session)
    paper = new_paper(session)

    pdf = files.add_attachment(paper, rel_path="files/aa/a.pdf", sha256=SHA_A, page_count=12)

    assert pdf.text_status is TextStatus.PENDING
    assert files.find_by_sha256(SHA_A) is pdf
    assert files.find_by_sha256(SHA_B) is None
    assert files.for_paper(paper) == [pdf]


def test_same_pdf_is_stored_once(session: Session) -> None:
    files = FilesRepository(session)
    files.add_attachment(new_paper(session), rel_path="files/aa/a.pdf", sha256=SHA_A)
    session.flush()

    assert "UNIQUE" in violates(
        session,
        "INSERT INTO attachment (id, paper_id, kind, rel_path, sha256, text_status, created_at,"
        " updated_at) VALUES ('x', :p, 'pdf', 'files/aa/b.pdf', :sha, 'pending', 'now', 'now')",
        p=new_paper(session, "Other"),
        sha=SHA_A,
    )


@pytest.mark.parametrize(
    ("column", "value"),
    [("sha256", "abc"), ("text_status", "unknown"), ("kind", "video"), ("page_count", -1)],
)
def test_attachment_checks(session: Session, column: str, value: object) -> None:
    paper = new_paper(session)
    session.flush()
    values = {"kind": "pdf", "sha256": SHA_A, "text_status": "pending", "page_count": 1}
    values[column] = value

    assert "CHECK" in violates(
        session,
        "INSERT INTO attachment (id, paper_id, kind, rel_path, sha256, text_status, page_count,"
        " created_at, updated_at) VALUES ('x', :p, :kind, 'f.pdf', :sha256, :text_status,"
        " :page_count, 'now', 'now')",
        p=paper,
        **values,
    )


# --- reviews and screening --------------------------------------------------------------


@pytest.fixture
def reviews(session: Session) -> ReviewsRepository:
    return ReviewsRepository(session)


@pytest.fixture
def review_id(reviews: ReviewsRepository) -> str:
    return reviews.add_review("LLM Code Review SLR", method=ReviewMethod.KITCHENHAM_SLR).id


def test_records_are_unique_per_review(
    reviews: ReviewsRepository, review_id: str, session: Session
) -> None:
    paper = new_paper(session)
    reviews.add_record(review_id, paper, RecordOrigin.DATABASE)
    session.flush()

    assert [r.paper_id for r in reviews.records(review_id)] == [paper]
    with pytest.raises(IntegrityError, match="UNIQUE"), session.begin_nested():
        reviews.add_record(review_id, paper, RecordOrigin.MANUAL)
        session.flush()


def test_criterion_codes_are_unique_per_review(
    reviews: ReviewsRepository, review_id: str, session: Session
) -> None:
    reviews.add_criterion(review_id, CriterionKind.EXCLUSION, "E1", "Not about code review")
    reviews.add_criterion(review_id, CriterionKind.INCLUSION, "I1", "Empirical study")
    session.flush()

    assert [c.code for c in reviews.criteria(review_id)] == ["E1", "I1"]
    with pytest.raises(IntegrityError, match="UNIQUE"), session.begin_nested():
        reviews.add_criterion(review_id, CriterionKind.EXCLUSION, "E1", "Duplicate code")
        session.flush()


def test_correction_is_a_new_row_and_the_latest_counts(
    reviews: ReviewsRepository, review_id: str, session: Session
) -> None:
    paper = new_paper(session)
    other = new_paper(session, "Other")
    for p in (paper, other):
        reviews.add_record(review_id, p, RecordOrigin.DATABASE)
    e1 = reviews.add_criterion(review_id, CriterionKind.EXCLUSION, "E1", "Off topic")
    stage = ScreeningStage.TITLE_ABSTRACT

    first = reviews.decide(review_id, paper, stage, Decision.EXCLUDE, criterion_id=e1.id)
    kept = reviews.decide(review_id, other, stage, Decision.MAYBE)
    fixed = reviews.decide(review_id, paper, stage, Decision.INCLUDE, supersedes_id=first.id)
    session.flush()

    current = reviews.current_decisions(review_id, stage)
    assert {d.id for d in current} == {fixed.id, kept.id}
    assert [d.id for d in reviews.history(review_id, paper)] == [first.id, fixed.id]
    assert first.decision is Decision.EXCLUDE  # the original row is untouched


def test_a_decision_is_corrected_at_most_once(
    reviews: ReviewsRepository, review_id: str, session: Session
) -> None:
    paper = new_paper(session)
    reviews.add_record(review_id, paper, RecordOrigin.DATABASE)
    stage = ScreeningStage.TITLE_ABSTRACT
    first = reviews.decide(review_id, paper, stage, Decision.EXCLUDE)
    reviews.decide(review_id, paper, stage, Decision.INCLUDE, supersedes_id=first.id)
    session.flush()

    with pytest.raises(IntegrityError, match="UNIQUE"), session.begin_nested():
        reviews.decide(review_id, paper, stage, Decision.MAYBE, supersedes_id=first.id)
        session.flush()


@pytest.mark.parametrize("mismatch", ["paper", "stage", "missing"])
def test_correction_must_target_the_same_paper_and_stage(
    reviews: ReviewsRepository, review_id: str, session: Session, mismatch: str
) -> None:
    paper = new_paper(session)
    other = new_paper(session, "Other")
    for p in (paper, other):
        reviews.add_record(review_id, p, RecordOrigin.DATABASE)
    first = reviews.decide(review_id, paper, ScreeningStage.TITLE_ABSTRACT, Decision.EXCLUDE)
    target = {
        "paper": (other, ScreeningStage.TITLE_ABSTRACT, first.id),
        "stage": (paper, ScreeningStage.FULL_TEXT, first.id),
        "missing": (paper, ScreeningStage.TITLE_ABSTRACT, "no-such-decision"),
    }[mismatch]

    with pytest.raises(TezError) as exc:
        reviews.decide(review_id, target[0], target[1], Decision.INCLUDE, supersedes_id=target[2])

    assert exc.value.code is ErrorCode.SCREENING_INVALID_CORRECTION


def test_decision_needs_the_paper_in_the_review(
    reviews: ReviewsRepository, review_id: str, session: Session
) -> None:
    outsider = new_paper(session)
    session.flush()

    with pytest.raises(IntegrityError, match="FOREIGN KEY"), session.begin_nested():
        reviews.decide(review_id, outsider, ScreeningStage.TITLE_ABSTRACT, Decision.INCLUDE)
        session.flush()


@pytest.mark.parametrize("statement", ["UPDATE", "DELETE"])
def test_screening_decisions_are_append_only(
    reviews: ReviewsRepository, review_id: str, session: Session, statement: str
) -> None:
    paper = new_paper(session)
    reviews.add_record(review_id, paper, RecordOrigin.DATABASE)
    reviews.decide(review_id, paper, ScreeningStage.TITLE_ABSTRACT, Decision.EXCLUDE)
    session.flush()

    sql = {
        "UPDATE": "UPDATE screening_decision SET decision = 'include'",
        "DELETE": "DELETE FROM screening_decision",
    }[statement]
    assert "append-only" in violates(session, sql)


def test_review_with_decisions_cannot_be_deleted(
    reviews: ReviewsRepository, review_id: str, session: Session
) -> None:
    paper = new_paper(session)
    reviews.add_record(review_id, paper, RecordOrigin.DATABASE)
    reviews.decide(review_id, paper, ScreeningStage.TITLE_ABSTRACT, Decision.INCLUDE)
    session.flush()

    violates(session, "DELETE FROM review WHERE id = :id", id=review_id)


@pytest.mark.parametrize(("column", "value"), [("decision", "perhaps"), ("stage", "abstract_only")])
def test_decision_checks(
    reviews: ReviewsRepository, review_id: str, session: Session, column: str, value: str
) -> None:
    paper = new_paper(session)
    reviews.add_record(review_id, paper, RecordOrigin.DATABASE)
    session.flush()
    values = {"decision": "include", "stage": "title_abstract"}
    values[column] = value

    assert "CHECK" in violates(
        session,
        "INSERT INTO screening_decision (id, review_id, paper_id, stage, decision, reviewer,"
        " created_at) VALUES ('x', :r, :p, :stage, :decision, 'owner', 'now')",
        r=review_id,
        p=paper,
        **values,
    )


# --- search -----------------------------------------------------------------------------


def test_run_with_results_is_written_once_with_ranks(
    reviews: ReviewsRepository, review_id: str, session: Session
) -> None:
    search = SearchRepository(session)
    query = search.add_query(review_id, "main", '"code review" AND (LLM OR GPT)')
    a, b = new_paper(session, "A"), new_paper(session, "B")

    run = search.add_run(
        review_id,
        source="openalex",
        query_id=query.id,
        translated_query="code review LLM",
        executed_at=NOW,
        initiated_via=InitiatedVia.CLI,
        total_reported=2,
        status=RunStatus.OK,
        results=[
            ResultInput(paper_id=a, match_method=MatchMethod.NEW),
            ResultInput(paper_id=b, match_method=MatchMethod.TITLE_FUZZY, match_score=0.93),
        ],
    )
    session.flush()

    assert run.retrieved_count == 2
    assert [(r.rank, r.paper_id) for r in search.results(run.id)] == [(1, a), (2, b)]
    assert [r.id for r in search.runs(review_id)] == [run.id]
    assert run.executed_at == NOW


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE search_run SET status = 'error'",
        "DELETE FROM search_run",
        "UPDATE search_result SET rank = 9",
        "DELETE FROM search_result",
    ],
)
def test_search_history_is_append_only(review_id: str, session: Session, sql: str) -> None:
    SearchRepository(session).add_run(
        review_id,
        source="arxiv",
        executed_at=NOW,
        initiated_via=InitiatedVia.GUI,
        status=RunStatus.OK,
        results=[ResultInput(paper_id=new_paper(session), match_method=MatchMethod.NEW)],
    )
    session.flush()

    assert "append-only" in violates(session, sql)


def test_import_run_without_a_query(review_id: str, session: Session) -> None:
    run = SearchRepository(session).add_run(
        review_id,
        source="IEEE Xplore",
        executed_at=NOW,
        initiated_via=InitiatedVia.GUI,
        status=RunStatus.PARTIAL,
        error="3 records could not be parsed",
        results=[],
    )

    assert run.query_id is None
    assert run.retrieved_count == 0


@pytest.mark.parametrize(
    ("column", "value"), [("status", "running"), ("initiated_via", "api"), ("retrieved_count", -1)]
)
def test_run_checks(review_id: str, session: Session, column: str, value: object) -> None:
    session.flush()
    values: dict[str, object] = {"status": "ok", "initiated_via": "gui", "retrieved_count": 0}
    values[column] = value

    assert "CHECK" in violates(
        session,
        "INSERT INTO search_run (id, review_id, source, executed_at, initiated_via,"
        " retrieved_count, status, created_at) VALUES ('x', :r, 's', 'now', :initiated_via,"
        " :retrieved_count, :status, 'now')",
        r=review_id,
        **values,
    )


# --- jobs ---------------------------------------------------------------------------------


def test_enqueue_returns_the_active_job_for_the_same_key(session: Session) -> None:
    jobs = JobsRepository(session)

    first, created = jobs.enqueue("extract_text", {"attachment_id": "a1"}, dedupe_key="text:a1")
    again, created_again = jobs.enqueue(
        "extract_text", {"attachment_id": "a1"}, dedupe_key="text:a1"
    )

    assert created is True
    assert created_again is False
    assert again.id == first.id
    assert first.status is JobStatus.QUEUED
    assert (first.attempts, first.max_attempts, first.priority) == (0, 3, 0)


def test_finished_job_can_be_queued_again(session: Session) -> None:
    jobs = JobsRepository(session)
    first, _ = jobs.enqueue("extract_text", {}, dedupe_key="text:a1")
    first.status = JobStatus.DONE
    session.flush()

    second, created = jobs.enqueue("extract_text", {}, dedupe_key="text:a1")

    assert created is True
    assert second.id != first.id
    assert jobs.get(first.id) is first


def test_two_active_jobs_with_one_key_violate_the_index(session: Session) -> None:
    JobsRepository(session).enqueue("extract_text", {}, dedupe_key="text:a1")
    session.flush()

    assert "UNIQUE" in violates(
        session,
        "INSERT INTO processing_job (id, type, payload_json, dedupe_key, status, priority,"
        " attempts, max_attempts, created_at, updated_at) VALUES ('x', 'extract_text', '{}',"
        " 'text:a1', 'running', 0, 0, 3, 'now', 'now')",
    )


@pytest.mark.parametrize(
    ("column", "value"),
    [("status", "paused"), ("progress", 1.5), ("attempts", -1), ("max_attempts", 0)],
)
def test_job_checks(session: Session, column: str, value: object) -> None:
    values: dict[str, object] = {
        "status": "queued",
        "progress": 0.5,
        "attempts": 0,
        "max_attempts": 3,
    }
    values[column] = value

    assert "CHECK" in violates(
        session,
        "INSERT INTO processing_job (id, type, payload_json, status, priority, attempts,"
        " max_attempts, progress, created_at, updated_at) VALUES ('x', 't', '{}', :status, 0,"
        " :attempts, :max_attempts, :progress, 'now', 'now')",
        **values,
    )


# --- settings -------------------------------------------------------------------------------


def test_settings_store_json_values(session: Session) -> None:
    settings = SettingsRepository(session)

    assert settings.get("ui.language") is None
    settings.set("ui.language", "tr")
    settings.set("sources.email", "demirkan@example.com")
    settings.set("search.sources", ["openalex", "arxiv"])
    settings.set("ui.density", {"compact": True, "rows": 40})
    settings.set("ui.language", "en")
    session.flush()

    assert settings.get("ui.language") == "en"
    assert settings.get("search.sources") == ["openalex", "arxiv"]
    assert settings.get("ui.density") == {"compact": True, "rows": 40}
    assert set(settings.all()) == {"ui.language", "sources.email", "search.sources", "ui.density"}

    settings.delete("sources.email")
    settings.delete("sources.email")
    assert settings.get("sources.email") is None


def test_append_only_triggers_exist(session: Session) -> None:
    names = set(
        session.execute(text("SELECT name FROM sqlite_master WHERE type = 'trigger'")).scalars()
    )

    # The only other trigger keeps the full-text index in step (migration 0020).
    assert names - {"tr_text_chunk_unindex"} == {
        f"{table}_append_only_{op}"
        for table in ("search_run", "search_result", "screening_decision")
        for op in ("update", "delete")
    }
