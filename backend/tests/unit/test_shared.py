import json
import threading
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import Column, Engine, MetaData, Table, create_engine, insert, select, text
from sqlalchemy.exc import StatementError

from tez.core.db import UtcDateTime
from tez.shared.ids import new_id
from tez.shared.text import fold, normalize_title, strip_markup

# --- UUIDv7 ----------------------------------------------------------------------------


def test_ids_are_uuid_version_7_with_rfc_variant() -> None:
    value = uuid.UUID(new_id())

    assert value.version == 7
    assert value.variant == uuid.RFC_4122


def test_ids_embed_the_current_time() -> None:
    before = int(datetime.now(UTC).timestamp() * 1000)
    ms = uuid.UUID(new_id()).int >> 80
    after = int(datetime.now(UTC).timestamp() * 1000)

    assert before <= ms <= after


def test_ids_sort_in_creation_order_even_within_one_millisecond() -> None:
    ids = [new_id() for _ in range(10_000)]

    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


def test_ids_are_unique_across_threads() -> None:
    results: list[list[str]] = [[] for _ in range(4)]

    def make(bucket: list[str]) -> None:
        bucket.extend(new_id() for _ in range(2_000))

    threads = [threading.Thread(target=make, args=(bucket,)) for bucket in results]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    every = [i for bucket in results for i in bucket]
    assert len(set(every)) == len(every)


# --- Turkish-aware text folding ------------------------------------------------------


@pytest.mark.parametrize("variant", ["IŞIK", "Işık", "ışık", "işık", "ISIK", "İŞİK"])
def test_turkish_i_variants_fold_to_the_same_text(variant: str) -> None:
    assert fold(variant) == "isik"


def test_fold_strips_diacritics() -> None:
    assert fold("Çağrı Öğüt Şükrü") == "cagri ogut sukru"
    assert fold("Müller façade naïve") == "muller facade naive"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Deep-Learning: A Survey!", "deep learning a survey"),
        ("  LLMs   for\tCode  Review ", "llms for code review"),
        ("Büyük Dil Modelleriyle KOD İNCELEME", "buyuk dil modelleriyle kod inceleme"),
        ("snake_case and “quotes”", "snake case and quotes"),
        ("", ""),
    ],
)
def test_normalize_title(title: str, expected: str) -> None:
    assert normalize_title(title) == expected


# --- UTC timestamps stored as ISO 8601 text ------------------------------------------


@pytest.fixture
def table() -> Generator[tuple[Table, Engine]]:
    engine = create_engine("sqlite://")
    meta = MetaData()
    t = Table("t", meta, Column("at", UtcDateTime))
    meta.create_all(engine)
    yield t, engine
    engine.dispose()


def test_utc_datetime_round_trips_as_fixed_width_text(table: tuple[Table, Engine]) -> None:
    t, engine = table
    value = datetime(2026, 11, 3, 19, 49, 3, 120, tzinfo=UTC)
    with engine.begin() as conn:
        conn.execute(insert(t).values(at=value))
        raw = conn.execute(text("SELECT at FROM t")).scalar_one()
        back = conn.execute(select(t.c.at)).scalar_one()

    assert raw == "2026-11-03T19:49:03.000120+00:00"
    assert back == value
    assert back.tzinfo is not None


def test_utc_datetime_converts_other_offsets_to_utc(table: tuple[Table, Engine]) -> None:
    t, engine = table
    istanbul = timezone(timedelta(hours=3))
    with engine.begin() as conn:
        conn.execute(insert(t).values(at=datetime(2026, 11, 3, 22, 0, tzinfo=istanbul)))
        raw = conn.execute(text("SELECT at FROM t")).scalar_one()

    assert raw == "2026-11-03T19:00:00.000000+00:00"


def test_utc_datetime_rejects_naive_values(table: tuple[Table, Engine]) -> None:
    t, engine = table
    with pytest.raises(StatementError, match="timezone"), engine.begin() as conn:
        conn.execute(insert(t).values(at=datetime(2026, 11, 3, 19, 0)))  # noqa: DTZ001


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("<jats:p>We study\n  reviews.</jats:p>", "We study reviews."),
        ("Kod &amp; <i>Inceleme</i>", "Kod & Inceleme"),
        ("a < b and c > d", "a < b and c > d"),
        ("x<sub>2</sub>y", "x 2 y"),
        ("plain", "plain"),
        ("", ""),
    ],
)
def test_strip_markup(given: str, expected: str) -> None:
    assert strip_markup(given) == expected


FOLD_CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "text" / "fold_cases.json").read_text("utf-8")
)


@pytest.mark.parametrize(("text", "expected"), FOLD_CASES)
def test_fold_matches_the_shared_table(text: str, expected: str) -> None:
    # The frontend's lib/text.ts folds the same table (Task 32, ADR 0023).
    assert fold(text) == expected
