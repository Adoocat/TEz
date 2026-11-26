"""The literature matrix: matrix, matrix_column, matrix_row, matrix_cell (Task 51, ADR 0035).

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "matrix",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["review.id"],
            name=op.f("fk_matrix_review_id_review"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matrix")),
    )
    with op.batch_alter_table("matrix", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_matrix_review_id"), ["review_id"], unique=False)

    op.create_table(
        "matrix_column",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("matrix_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column(
            "data_type",
            sa.Enum(
                "text",
                "number",
                "enum",
                "multi_enum",
                "bool",
                name="matrix_data_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("options_json", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["matrix_id"],
            ["matrix.id"],
            name=op.f("fk_matrix_column_matrix_id_matrix"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matrix_column")),
    )
    with op.batch_alter_table("matrix_column", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_matrix_column_matrix_id"), ["matrix_id"], unique=False)

    op.create_table(
        "matrix_row",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("matrix_id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["matrix_id"],
            ["matrix.id"],
            name=op.f("fk_matrix_row_matrix_id_matrix"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["paper.id"],
            name=op.f("fk_matrix_row_paper_id_paper"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matrix_row")),
        sa.UniqueConstraint("matrix_id", "paper_id", name=op.f("uq_matrix_row_matrix_id_paper_id")),
    )
    with op.batch_alter_table("matrix_row", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_matrix_row_paper_id"), ["paper_id"], unique=False)

    op.create_table(
        "matrix_cell",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("row_id", sa.String(length=36), nullable=False),
        sa.Column("column_id", sa.String(length=36), nullable=False),
        sa.Column("value_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column(
            "origin",
            sa.Enum(
                "manual",
                "ai_accepted",
                name="matrix_cell_origin",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["column_id"],
            ["matrix_column.id"],
            name=op.f("fk_matrix_cell_column_id_matrix_column"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["row_id"],
            ["matrix_row.id"],
            name=op.f("fk_matrix_cell_row_id_matrix_row"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matrix_cell")),
        sa.UniqueConstraint("row_id", "column_id", name=op.f("uq_matrix_cell_row_id_column_id")),
    )
    with op.batch_alter_table("matrix_cell", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_matrix_cell_column_id"), ["column_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("matrix_cell", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_matrix_cell_column_id"))

    op.drop_table("matrix_cell")
    with op.batch_alter_table("matrix_row", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_matrix_row_paper_id"))

    op.drop_table("matrix_row")
    with op.batch_alter_table("matrix_column", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_matrix_column_matrix_id"))

    op.drop_table("matrix_column")
    with op.batch_alter_table("matrix", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_matrix_review_id"))

    op.drop_table("matrix")
