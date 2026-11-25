"""Highlights and marked areas: annotation (Task 47).

Revision ID: 0022
Revises: 0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "annotation",
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("anchor_id", sa.String(length=36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "highlight",
                "underline",
                "area",
                name="kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("color", sa.String(length=16), nullable=False),
        sa.Column("comment_md", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["paper.id"],
            name=op.f("fk_annotation_paper_id_paper"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["anchor_id"],
            ["anchor.id"],
            name=op.f("fk_annotation_anchor_id_anchor"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_annotation")),
        sa.UniqueConstraint("anchor_id", name=op.f("uq_annotation_anchor_id")),
    )
    with op.batch_alter_table("annotation", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_annotation_paper_id"), ["paper_id"], unique=False)


def downgrade() -> None:
    op.drop_table("annotation")
