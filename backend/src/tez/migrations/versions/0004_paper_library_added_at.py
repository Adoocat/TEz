"""Mark what is really in the library: paper.library_added_at (Task 14, ADR 0009).

Every search result needs a `paper` row, so a row alone does not mean the user kept the paper.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("paper", sa.Column("library_added_at", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_paper_library_added_at"), "paper", ["library_added_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_paper_library_added_at"), table_name="paper")
    op.execute("ALTER TABLE paper DROP COLUMN library_added_at")
