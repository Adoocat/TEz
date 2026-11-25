"""Places in PDFs: anchor (Task 46).

Revision ID: 0021
Revises: 0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "anchor",
        sa.Column("attachment_id", sa.String(length=36), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("text", "area", name="kind", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column(
            "state",
            sa.Enum(
                "verified",
                "unverified",
                "lost",
                name="state",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("rects_json", sa.JSON(), nullable=False),
        sa.Column("quote_exact", sa.Text(), nullable=False),
        sa.Column("quote_prefix", sa.Text(), nullable=False),
        sa.Column("quote_suffix", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint("page_index >= 0", name=op.f("ck_anchor_page_index")),
        sa.CheckConstraint("char_end > char_start", name=op.f("ck_anchor_char_range")),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["attachment.id"],
            name=op.f("fk_anchor_attachment_id_attachment"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anchor")),
    )
    with op.batch_alter_table("anchor", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_anchor_attachment_id"), ["attachment_id"], unique=False
        )


def downgrade() -> None:
    op.drop_table("anchor")
