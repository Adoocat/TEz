"""Task 4 acceptance: an empty database goes `upgrade head` -> `downgrade base` cleanly.

These tests cover every migration added later, so each one must be reversible and the
models must always match what the migrations build.
"""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from tez.core.db import Base, Database
from tez.core.migrations import MIGRATIONS_DIR, alembic_config, migrate


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "library.sqlite")
    yield database
    database.close()


def tables(db: Database) -> set[str]:
    return set(inspect(db.engine).get_table_names())


def current_revision(db: Database) -> str | None:
    with db.engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def run(db: Database, action: str, target: str) -> None:
    with db.migration_connection() as conn:
        config = alembic_config(conn)
        getattr(command, action)(config, target)


def head(config: Config) -> str:
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1
    return heads[0]


def test_upgrade_head_then_downgrade_base(db: Database) -> None:
    migrate(db)
    assert current_revision(db) == head(alembic_config())

    run(db, "downgrade", "base")
    assert current_revision(db) is None
    assert tables(db) <= {"alembic_version"}

    migrate(db)
    assert current_revision(db) == head(alembic_config())


def test_every_migration_steps_up_and_down(db: Database) -> None:
    """Stairway test: upgrade one step, downgrade it, upgrade again, for every revision."""
    script = ScriptDirectory.from_config(alembic_config())
    revisions = list(reversed(list(script.walk_revisions())))
    assert revisions, "no migrations found"

    for revision in revisions:
        run(db, "upgrade", revision.revision)
        down = revision.down_revision
        assert down is None or isinstance(down, str), "merge revisions are not expected"
        run(db, "downgrade", down or "base")
        run(db, "upgrade", revision.revision)
        assert current_revision(db) == revision.revision


def test_history_has_a_single_head() -> None:
    script = ScriptDirectory.from_config(alembic_config())
    assert len(script.get_heads()) == 1, "merge the migration branches"


def test_models_match_migrations(db: Database) -> None:
    # A model change without a migration fails here (and so in CI).
    migrate(db)

    with db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)

    assert diff == []


def test_migrate_is_idempotent(db: Database) -> None:
    migrate(db)
    migrate(db)

    assert current_revision(db) == head(alembic_config())


def test_migrate_works_from_any_working_directory(
    db: Database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The installed app starts with an arbitrary cwd; migrations ship inside the package.
    monkeypatch.chdir(tmp_path)

    migrate(db)

    assert current_revision(db) is not None


def test_path_with_spaces_and_turkish_letters(tmp_path: Path) -> None:
    folder = tmp_path / "Tez Kütüphanesi İçerik"
    folder.mkdir()
    db = Database(folder / "library.sqlite")
    try:
        migrate(db)
        assert current_revision(db) is not None
    finally:
        db.close()


def test_a_failing_migration_leaves_the_database_unchanged(db: Database, tmp_path: Path) -> None:
    # SQLite DDL is transactional; a crash half-way must not leave a half-built schema.
    scripts = tmp_path / "scripts"
    shutil.copytree(MIGRATIONS_DIR, scripts, ignore=shutil.ignore_patterns("__pycache__"))
    (scripts / "versions" / "9999_broken.py").write_text(
        'revision = "9999"\n'
        f"down_revision = {head(alembic_config())!r}\n"
        "branch_labels = None\n"
        "depends_on = None\n"
        "from alembic import op\n"
        "def upgrade():\n"
        '    op.execute("CREATE TABLE half_built (id INTEGER)")\n'
        '    raise RuntimeError("migration crashed")\n'
        "def downgrade():\n"
        "    pass\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="migration crashed"), db.migration_connection() as conn:
        config = alembic_config(conn)
        config.set_main_option("script_location", str(scripts))
        command.upgrade(config, "head")

    assert current_revision(db) is None
    assert tables(db) == set()
