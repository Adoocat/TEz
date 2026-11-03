"""SQLite access: engine with the required pragmas, read and write sessions.

Transactions are controlled by SQLAlchemy, not by the `sqlite3` module (whose legacy
mode skips BEGIN before SELECT and breaks SAVEPOINT). Write sessions start with
`BEGIN IMMEDIATE`, so a second writer waits up to `busy_timeout` instead of failing with
"database is locked" when it upgrades from reading to writing.
"""

import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import URL, Connection, Engine, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

logger = logging.getLogger(__name__)

BUSY_TIMEOUT_MS = 5000
_BEGIN_OPTION = "tez_begin"

# Named constraints: Alembic batch mode (how SQLite alters tables) can only drop named ones.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _on_connect(dbapi_connection: Any, _: ConnectionPoolEntry) -> None:
    assert isinstance(dbapi_connection, sqlite3.Connection)
    # Let SQLAlchemy emit BEGIN itself (see _on_begin).
    dbapi_connection.isolation_level = None
    mode = dbapi_connection.execute("PRAGMA journal_mode=WAL").fetchone()
    if mode is None or mode[0] != "wal":
        # E.g. on some network drives; still works, but readers and writers block each other.
        logger.warning("WAL mode unavailable", extra={"journal_mode": mode and mode[0]})
    dbapi_connection.execute("PRAGMA foreign_keys=ON")
    dbapi_connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    # Durable across application crashes with WAL; only an OS crash can lose the last commit.
    dbapi_connection.execute("PRAGMA synchronous=NORMAL")


def _on_begin(conn: Connection) -> None:
    conn.exec_driver_sql(conn.get_execution_options().get(_BEGIN_OPTION, "BEGIN"))


class Database:
    """One SQLite file. Create once per process and share; call `close()` at shutdown."""

    def __init__(self, path: Path) -> None:
        if not path.parent.is_dir():
            raise FileNotFoundError(f"database folder does not exist: {path.parent}")
        self.path = path
        self.engine: Engine = create_engine(URL.create("sqlite", database=str(path)))
        event.listen(self.engine, "connect", _on_connect)
        event.listen(self.engine, "begin", _on_begin)
        self._read = sessionmaker(self.engine, expire_on_commit=False)
        self._write = sessionmaker(
            self.engine.execution_options(**{_BEGIN_OPTION: "BEGIN IMMEDIATE"}),
            expire_on_commit=False,
        )

    @contextmanager
    def session(self) -> Generator[Session]:
        """Read-only by convention: never commits, so stray writes are discarded."""
        with self._read() as s:
            try:
                yield s
            finally:
                s.rollback()

    @contextmanager
    def write_session(self) -> Generator[Session]:
        """Takes the write lock at BEGIN; commits on success, rolls back on error."""
        with self._write() as s, s.begin():
            yield s

    @contextmanager
    def migration_connection(self) -> Generator[Connection]:
        """A connection with foreign keys off, as Alembic batch mode needs on SQLite.

        Batch mode rebuilds a table by copy-and-rename; with foreign keys on, dropping the
        old table could cascade or fail. Integrity is checked afterwards instead.
        """
        with self.engine.connect() as conn:
            raw = conn.connection.driver_connection
            assert isinstance(raw, sqlite3.Connection)
            # Must run outside a transaction, where SQLite ignores it.
            raw.execute("PRAGMA foreign_keys=OFF")
            try:
                yield conn
                violations = conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                conn.rollback()
                if violations:
                    raise RuntimeError(f"foreign key violations after migration: {violations}")
            finally:
                conn.rollback()
                raw.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        self.engine.dispose()
