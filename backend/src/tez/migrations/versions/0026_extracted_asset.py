"""Figures and tables kept from PDFs: extracted_asset (Task 55, ADR 0036).

Revision ID: 0026
Revises: 0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extracted_asset",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("attachment_id", sa.String(length=36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "figure", "table", name="asset_kind", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("bbox_json", sa.JSON(), nullable=False),
        sa.Column("anchor_id", sa.String(length=36), nullable=False),
        sa.Column("file_rel_path", sa.Text(), nullable=False),
        sa.Column("data_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("extractor", sa.String(length=32), nullable=False),
        sa.Column("extractor_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["anchor_id"],
            ["anchor.id"],
            name=op.f("fk_extracted_asset_anchor_id_anchor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["attachment.id"],
            name=op.f("fk_extracted_asset_attachment_id_attachment"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extracted_asset")),
    )
    with op.batch_alter_table("extracted_asset", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_extracted_asset_anchor_id"), ["anchor_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_extracted_asset_attachment_id"), ["attachment_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("extracted_asset", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_extracted_asset_attachment_id"))
        batch_op.drop_index(batch_op.f("ix_extracted_asset_anchor_id"))

    op.drop_table("extracted_asset")
