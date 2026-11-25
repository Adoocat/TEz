"""The text inside PDFs: text_chunk, and attachment.text_version (Task 43, ADR 0030).

Revision ID: 0019
Revises: 0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "text_chunk",
        sa.Column("attachment_id", sa.String(length=36), nullable=False),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint("page_index >= 0", name=op.f("ck_text_chunk_page_index")),
        sa.CheckConstraint("char_end >= char_start", name=op.f("ck_text_chunk_char_range")),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["attachment.id"],
            name=op.f("fk_text_chunk_attachment_id_attachment"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_text_chunk")),
        sa.UniqueConstraint("attachment_id", "ord", name=op.f("uq_text_chunk_attachment_id_ord")),
    )
    op.add_column("attachment", sa.Column("text_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.execute("ALTER TABLE attachment DROP COLUMN text_version")
    op.drop_table("text_chunk")
