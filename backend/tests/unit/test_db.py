import contextlib
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from tez.core.db import Base, Database


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "library.sqlite")
    yield database
    database.close()


@pytest.fixture
def db_with_tables(db: Database) -> Database:
    # Throwaway tables: the real schema comes from migrations (Task 6).
    with db.write_session() as s:
        s.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
        s.execute(
            text("CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent)")
        )
        s.execute(text("CREATE TABLE counter (n INTEGER)"))
    return db


def pragma(db: Database, name: str) -> object:
    with db.session() as s:
        return s.execute(text(f"PRAGMA {name}")).scalar_one()


def test_pragmas_on_every_connection(db: Database) -> None:
    assert pragma(db, "journal_mode") == "wal"
    assert pragma(db, "foreign_keys") == 1
    assert pragma(db, "busy_timeout") == 5000
    assert pragma(db, "synchronous") == 1  # NORMAL


def test_pragmas_on_a_fresh_connection_after_dispose(db: Database) -> None:
    db.engine.dispose()

    assert pragma(db, "foreign_keys") == 1
    assert pragma(db, "busy_timeout") == 5000


def test_foreign_keys_are_enforced(db_with_tables: Database) -> None:
    with (
        pytest.raises(IntegrityError, match="FOREIGN KEY"),
        db_with_tables.write_session() as s,
    ):
        s.execute(text("INSERT INTO child (id, parent_id) VALUES (1, 42)"))


def test_write_session_commits(db_with_tables: Database) -> None:
    with db_with_tables.write_session() as s:
        s.execute(text("INSERT INTO counter VALUES (1)"))

    with db_with_tables.session() as s:
        assert s.execute(text("SELECT count(*) FROM counter")).scalar_one() == 1


def test_write_session_rolls_back_on_error(db_with_tables: Database) -> None:
    with pytest.raises(RuntimeError), db_with_tables.write_session() as s:
        s.execute(text("INSERT INTO counter VALUES (1)"))
        raise RuntimeError("boom")

    with db_with_tables.session() as s:
        assert s.execute(text("SELECT count(*) FROM counter")).scalar_one() == 0


def test_read_session_never_commits(db_with_tables: Database) -> None:
    with db_with_tables.session() as s:
        s.execute(text("INSERT INTO counter VALUES (1)"))

    with db_with_tables.session() as s:
        assert s.execute(text("SELECT count(*) FROM counter")).scalar_one() == 0


def test_savepoints_work(db_with_tables: Database) -> None:
    # Needs SQLAlchemy, not the sqlite3 module, to control BEGIN.
    with db_with_tables.write_session() as s:
        s.execute(text("INSERT INTO counter VALUES (1)"))
        nested = s.begin_nested()
        s.execute(text("INSERT INTO counter VALUES (2)"))
        nested.rollback()

    with db_with_tables.session() as s:
        assert s.execute(text("SELECT n FROM counter")).scalars().all() == [1]


def test_concurrent_read_then_write_transactions_do_not_fail(db_with_tables: Database) -> None:
    """API and worker both read-then-write. With a deferred BEGIN the second writer gets
    "database is locked" at once (busy_timeout cannot help); BEGIN IMMEDIATE makes it wait."""
    both_inside = threading.Barrier(2, timeout=5)
    errors: list[OperationalError] = []

    def increment() -> None:
        try:
            with db_with_tables.write_session() as s:
                count = s.execute(text("SELECT count(*) FROM counter")).scalar_one()
                # Times out (breaks) when the other writer is correctly waiting for our lock.
                with contextlib.suppress(threading.BrokenBarrierError):
                    both_inside.wait(timeout=0.5)
                s.execute(text("INSERT INTO counter VALUES (:n)"), {"n": count + 1})
        except OperationalError as exc:
            errors.append(exc)

    threads = [threading.Thread(target=increment) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert errors == []
    with db_with_tables.session() as s:
        assert sorted(s.execute(text("SELECT n FROM counter")).scalars()) == [1, 2]


def test_readers_are_not_blocked_by_a_writer(db_with_tables: Database) -> None:
    with db_with_tables.write_session() as writer:
        writer.execute(text("INSERT INTO counter VALUES (1)"))
        # WAL: a reader sees the last committed state while the write is open.
        with db_with_tables.session() as reader:
            assert reader.execute(text("SELECT count(*) FROM counter")).scalar_one() == 0


def test_missing_folder_is_an_error_not_a_new_folder(tmp_path: Path) -> None:
    # Creating library folders is the library module's job (Task 5), not the database's.
    with pytest.raises(FileNotFoundError):
        Database(tmp_path / "missing" / "library.sqlite")
    assert not (tmp_path / "missing").exists()


def test_metadata_names_constraints() -> None:
    # Batch migrations on SQLite can only drop constraints that have names.
    convention = Base.metadata.naming_convention
    assert {"ix", "uq", "ck", "fk", "pk"} <= set(convention)


def test_migration_connection_turns_foreign_keys_off_and_back_on(db: Database) -> None:
    with db.migration_connection() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 0

    # The pooled connection goes back with foreign keys on again.
    assert pragma(db, "foreign_keys") == 1


def test_migration_connection_rejects_broken_foreign_keys(db_with_tables: Database) -> None:
    with (
        pytest.raises(RuntimeError, match="foreign key violations"),
        db_with_tables.migration_connection() as conn,
    ):
        conn.exec_driver_sql("INSERT INTO child (id, parent_id) VALUES (1, 42)")
        conn.commit()
