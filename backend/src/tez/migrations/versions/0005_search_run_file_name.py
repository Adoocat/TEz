"""Name the file an imported run came from: search_run.file_name (Task 15).

Plain ALTER statements, not batch mode: a batch rebuild would drop the append-only triggers.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("search_run", sa.Column("file_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.execute("ALTER TABLE search_run DROP COLUMN file_name")
