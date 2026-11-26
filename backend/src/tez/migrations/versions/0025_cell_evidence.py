"""Evidence for matrix cells: cell_evidence (Task 53, ADR 0035).

Revision ID: 0025
Revises: 0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cell_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("cell_id", sa.String(length=36), nullable=False),
        sa.Column("anchor_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["anchor_id"],
            ["anchor.id"],
            name=op.f("fk_cell_evidence_anchor_id_anchor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cell_id"],
            ["matrix_cell.id"],
            name=op.f("fk_cell_evidence_cell_id_matrix_cell"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cell_evidence")),
        sa.UniqueConstraint(
            "cell_id", "anchor_id", name=op.f("uq_cell_evidence_cell_id_anchor_id")
        ),
    )
    with op.batch_alter_table("cell_evidence", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_cell_evidence_anchor_id"), ["anchor_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("cell_evidence", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_cell_evidence_anchor_id"))

    op.drop_table("cell_evidence")
