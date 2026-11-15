"""Save searches of databases without an open API: search_query.external_source (Task 27).

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("search_query", sa.Column("external_source", sa.String(64), nullable=True))


def downgrade() -> None:
    op.execute("ALTER TABLE search_query DROP COLUMN external_source")
