"""Highlight terms per screening criterion: screening_criterion.keywords (Task 32, ADR 0023).

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "screening_criterion",
        sa.Column("keywords", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )


def downgrade() -> None:
    op.execute("ALTER TABLE screening_criterion DROP COLUMN keywords")
