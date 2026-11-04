"""Group the runs of one search: search_run.search_id (Task 13, ADR 0009).

Plain ALTER statements, not batch mode: a batch rebuild would drop the append-only triggers.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("search_run", sa.Column("search_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_search_run_search_id"), "search_run", ["search_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_search_run_search_id"), table_name="search_run")
    op.execute("ALTER TABLE search_run DROP COLUMN search_id")
