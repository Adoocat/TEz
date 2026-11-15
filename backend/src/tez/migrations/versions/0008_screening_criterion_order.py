"""Order and archive screening criteria: position and archived_at (Task 25).

The first nine criteria of a stage, in `position` order, get the 1-9 screening keys. A
criterion a decision already uses is archived instead of deleted. Existing criteria are
ordered by code.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("screening_criterion") as batch:
        batch.add_column(sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("archived_at", sa.String(length=32), nullable=True))
    op.execute(
        "UPDATE screening_criterion SET position = ("
        "SELECT COUNT(*) FROM screening_criterion AS earlier "
        "WHERE earlier.review_id = screening_criterion.review_id "
        "AND earlier.code < screening_criterion.code)"
    )


def downgrade() -> None:
    with op.batch_alter_table("screening_criterion") as batch:
        batch.drop_column("archived_at")
        batch.drop_column("position")
