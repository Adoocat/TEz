"""Keep the name a PDF had and its size: attachment.file_name, attachment.size (Task 16).

The stored name is the content hash, so the user's own file name would be lost otherwise.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("attachment", sa.Column("file_name", sa.Text(), nullable=True))
    op.add_column("attachment", sa.Column("size", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.execute("ALTER TABLE attachment DROP COLUMN size")
    op.execute("ALTER TABLE attachment DROP COLUMN file_name")
