"""Alembic environment.

From code (`tez.core.migrations.migrate`) a ready connection arrives in
`config.attributes["connection"]`. From the developer CLI (`uv run alembic ...` in
`backend/`) the database is the file named by `sqlalchemy.url` in alembic.ini.
"""

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import Connection, make_url

from tez.core.db import Database
from tez.models import Base

config = context.config


def run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        # SQLite cannot ALTER most things; batch mode rebuilds the table instead.
        render_as_batch=True,
        # Alembic assumes SQLite DDL is not transactional, but it is. One transaction for the
        # whole upgrade: a migration that fails half-way leaves the schema untouched.
        transactional_ddl=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def main() -> None:
    connection = config.attributes.get("connection")
    if isinstance(connection, Connection):
        run(connection)
        return

    if config.config_file_name is not None:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    if context.is_offline_mode():
        raise SystemExit("offline (--sql) migrations are not supported")
    url = make_url(config.get_main_option("sqlalchemy.url") or "")
    if url.get_backend_name() != "sqlite" or not url.database:
        raise SystemExit("alembic.ini: sqlalchemy.url must be a sqlite file URL")
    path = Path(url.database)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(path)
    try:
        with db.migration_connection() as conn:
            run(conn)
    finally:
        db.close()


main()
