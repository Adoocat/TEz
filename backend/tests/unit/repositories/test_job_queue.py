"""Lease-based job queue on processing_job (Task 6b)."""

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from tez.modules.jobs.models import JobStatus
from tez.modules.jobs.repository import JobsRepository

T0 = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)
LEASE = timedelta(seconds=30)


def test_claim_takes_the_highest_priority_then_the_oldest(session: Session) -> None:
    jobs = JobsRepository(session)
    old, _ = jobs.enqueue("a", {})
    urgent, _ = jobs.enqueue("b", {}, priority=10)
    jobs.enqueue("c", {})

    first = jobs.claim(now=T0, lease=LEASE)
    second = jobs.claim(now=T0, lease=LEASE)

    assert first is not None
    assert second is not None
    assert [first.id, second.id] == [urgent.id, old.id]


def test_claim_marks_running_counts_the_attempt_and_sets_the_lease(session: Session) -> None:
    jobs = JobsRepository(session)
    jobs.enqueue("a", {})

    job = jobs.claim(now=T0, lease=LEASE)

    assert job is not None
    assert job.status is JobStatus.RUNNING
    assert job.attempts == 1
    assert job.lease_until == T0 + LEASE


def test_nothing_to_claim(session: Session) -> None:
    assert JobsRepository(session).claim(now=T0, lease=LEASE) is None


def test_a_leased_job_is_not_claimed_twice(session: Session) -> None:
    jobs = JobsRepository(session)
    jobs.enqueue("a", {})
    jobs.claim(now=T0, lease=LEASE)

    assert jobs.claim(now=T0 + LEASE - timedelta(seconds=1), lease=LEASE) is None


def test_an_expired_lease_is_claimed_again(session: Session) -> None:
    """The acceptance in miniature: the worker died, the lease ran out, the job is retried."""
    jobs = JobsRepository(session)
    jobs.enqueue("a", {})
    jobs.claim(now=T0, lease=LEASE)

    again = jobs.claim(now=T0 + LEASE, lease=LEASE)

    assert again is not None
    assert again.attempts == 2
    assert again.lease_until == T0 + 2 * LEASE


def test_expired_lease_on_the_last_attempt_fails_the_job(session: Session) -> None:
    jobs = JobsRepository(session)
    job, _ = jobs.enqueue("a", {}, max_attempts=2)
    jobs.claim(now=T0, lease=LEASE)
    jobs.claim(now=T0 + LEASE, lease=LEASE)

    assert jobs.claim(now=T0 + 2 * LEASE, lease=LEASE) is None
    assert job.status is JobStatus.FAILED
    assert job.lease_until is None
    assert json.loads(job.error or "") == {"code": "job.lease_expired", "params": {"attempts": 2}}


def test_heartbeat_extends_the_lease_and_stores_progress(session: Session) -> None:
    jobs = JobsRepository(session)
    jobs.enqueue("a", {})
    job = jobs.claim(now=T0, lease=LEASE)
    assert job is not None

    assert jobs.heartbeat(
        job.id, attempt=1, progress=0.4, now=T0 + timedelta(seconds=20), lease=LEASE
    )

    assert job.progress == 0.4
    assert job.lease_until == T0 + timedelta(seconds=50)


def test_a_worker_that_lost_its_lease_cannot_touch_the_job(session: Session) -> None:
    # Worker A stalls past its lease, worker B takes over: A's late writes are refused.
    jobs = JobsRepository(session)
    jobs.enqueue("a", {})
    job = jobs.claim(now=T0, lease=LEASE)
    assert job is not None
    jobs.claim(now=T0 + LEASE, lease=LEASE)  # attempt 2 belongs to someone else

    assert not jobs.heartbeat(job.id, attempt=1, progress=0.9, now=T0 + LEASE, lease=LEASE)
    assert not jobs.complete(job.id, attempt=1)
    assert not jobs.fail(job.id, attempt=1, code="x", now=T0 + LEASE)
    assert job.status is JobStatus.RUNNING
    assert job.attempts == 2


def test_complete(session: Session) -> None:
    jobs = JobsRepository(session)
    jobs.enqueue("a", {})
    job = jobs.claim(now=T0, lease=LEASE)
    assert job is not None

    assert jobs.complete(job.id, attempt=1)

    assert job.status is JobStatus.DONE
    assert job.progress == 1.0
    assert job.lease_until is None
    assert job.error is None


def test_failure_is_retried_later_until_attempts_run_out(session: Session) -> None:
    jobs = JobsRepository(session)
    job, _ = jobs.enqueue("a", {}, max_attempts=2)
    jobs.claim(now=T0, lease=LEASE)

    assert jobs.fail(job.id, attempt=1, code="job.handler_failed", now=T0)
    assert job.status is JobStatus.QUEUED
    assert json.loads(job.error or "")["code"] == "job.handler_failed"
    # Back-off: not claimable straight away, so a failing job cannot spin.
    assert jobs.claim(now=T0, lease=LEASE) is None
    assert job.lease_until is not None
    retry = jobs.claim(now=job.lease_until, lease=LEASE)
    assert retry is not None

    assert jobs.fail(job.id, attempt=2, code="job.handler_failed", now=T0)
    assert job.status is JobStatus.FAILED


def test_permanent_failure_skips_the_retries(session: Session) -> None:
    jobs = JobsRepository(session)
    job, _ = jobs.enqueue("a", {})
    jobs.claim(now=T0, lease=LEASE)

    jobs.fail(job.id, attempt=1, code="job.unknown_type", params={"type": "a"}, now=T0, retry=False)

    assert job.status is JobStatus.FAILED
    assert json.loads(job.error or "") == {"code": "job.unknown_type", "params": {"type": "a"}}


def test_changes_since_lists_updates_in_order(session: Session) -> None:
    jobs = JobsRepository(session)
    a, _ = jobs.enqueue("a", {})
    b, _ = jobs.enqueue("b", {})
    session.flush()

    changed = jobs.changed_since(None)
    assert [j.id for j in changed] == [a.id, b.id]

    jobs.claim(now=T0, lease=LEASE)  # touches a
    after = jobs.changed_since((b.updated_at, b.id))
    assert [j.id for j in after] == [a.id]


def test_recent_and_active(session: Session) -> None:
    jobs = JobsRepository(session)
    done, _ = jobs.enqueue("a", {})
    queued, _ = jobs.enqueue("b", {})
    jobs.claim(now=T0, lease=LEASE)
    jobs.complete(done.id, attempt=1)

    assert [j.id for j in jobs.active()] == [queued.id]
    assert [j.id for j in jobs.recent(limit=10)] == [queued.id, done.id]
