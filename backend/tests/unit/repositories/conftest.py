"""A fresh, fully migrated database per test (migrations, not create_all: triggers count)."""

import shutil
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tez.core.db import Database
from tez.core.migrations import migrate


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("template") / "library.sqlite"
    db = Database(path)
    try:
        migrate(db)
        with db.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        db.close()
    return path


@pytest.fixture
def db(migrated_template: Path, tmp_path: Path) -> Generator[Database]:
    path = tmp_path / "library.sqlite"
    shutil.copyfile(migrated_template, path)
    database = Database(path)
    yield database
    database.close()


@pytest.fixture
def session(db: Database) -> Generator[Session]:
    """A write session; every test has its own database file, so it may commit freely."""
    with db.write_session() as s:
        yield s


def violates(session: Session, sql: str, **params: object) -> str:
    """Run raw SQL that must break a constraint; returns the database's message."""
    nested = session.begin_nested()
    try:
        session.execute(text(sql), params)
    except IntegrityError as error:
        nested.rollback()
        return str(error.orig)
    nested.rollback()
    pytest.fail(f"no constraint violation: {sql}")
