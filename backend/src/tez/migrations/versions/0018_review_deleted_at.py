"""A review can be moved to the trash and restored: review.deleted_at.

Revision ID: 0018
Revises: 0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("review", sa.Column("deleted_at", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.execute("ALTER TABLE review DROP COLUMN deleted_at")
