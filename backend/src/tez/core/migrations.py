"""Running Alembic migrations from code (app start-up, CLI, tests).

The migration scripts live inside the package (`tez/migrations/`) so they ship with the
PyInstaller build and resolve regardless of the working directory (ADR 0003).
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection

from tez.core.db import Database

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def alembic_config(connection: Connection | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def migrate(db: Database) -> None:
    """Bring the database schema to the latest revision. Safe to call on every start."""
    with db.migration_connection() as conn:
        command.upgrade(alembic_config(conn), "head")


def _scripts() -> ScriptDirectory:
    return ScriptDirectory.from_config(alembic_config())


def head_revision() -> str:
    head = _scripts().get_current_head()
    assert head is not None, "no migrations found"
    return head


def is_known_revision(revision: str) -> bool:
    return any(script.revision == revision for script in _scripts().walk_revisions())


def current_revision(db: Database) -> str | None:
    """The revision the database is at; None for a database never migrated."""
    with db.engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()
