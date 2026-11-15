"""The degree of a thesis: paper.thesis_type (Task 28).

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A plain ADD COLUMN: SQLite takes a column CHECK there, and rebuilding `paper` would
    # mean rebuilding everything that points at it.
    op.execute(
        "ALTER TABLE paper ADD COLUMN thesis_type VARCHAR(8) "
        "CONSTRAINT ck_paper_thesis_type CHECK (thesis_type IN ('masters', 'doctoral'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE paper DROP COLUMN thesis_type")
