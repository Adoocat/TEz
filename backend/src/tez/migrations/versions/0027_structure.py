"""A paper's structure read by GROBID: structure_read, document_section, reference_entry
(Task 56, ADR 0037).

Revision ID: 0027
Revises: 0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_section",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("attachment_id", sa.String(length=36), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("heading", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["attachment.id"],
            name=op.f("fk_document_section_attachment_id_attachment"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_section")),
        sa.UniqueConstraint(
            "attachment_id", "ord", name=op.f("uq_document_section_attachment_id_ord")
        ),
    )
    op.create_table(
        "reference_entry",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("attachment_id", sa.String(length=36), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("parsed_json", sa.JSON(), nullable=False),
        sa.Column("matched_paper_id", sa.String(length=36), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["attachment.id"],
            name=op.f("fk_reference_entry_attachment_id_attachment"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["matched_paper_id"],
            ["paper.id"],
            name=op.f("fk_reference_entry_matched_paper_id_paper"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reference_entry")),
        sa.UniqueConstraint(
            "attachment_id", "ord", name=op.f("uq_reference_entry_attachment_id_ord")
        ),
    )
    with op.batch_alter_table("reference_entry", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_reference_entry_matched_paper_id"), ["matched_paper_id"], unique=False
        )

    op.create_table(
        "structure_read",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("attachment_id", sa.String(length=36), nullable=False),
        sa.Column("read_at", sa.String(length=32), nullable=True),
        sa.Column("error", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["attachment.id"],
            name=op.f("fk_structure_read_attachment_id_attachment"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_structure_read")),
        sa.UniqueConstraint("attachment_id", name=op.f("uq_structure_read_attachment_id")),
    )


def downgrade() -> None:
    op.drop_table("structure_read")
    with op.batch_alter_table("reference_entry", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_reference_entry_matched_paper_id"))

    op.drop_table("reference_entry")
    op.drop_table("document_section")
