"""Notes and their links: note, note_link, note_fts (Task 48, ADR 0034).

Revision ID: 0023
Revises: 0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "note",
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("paper_id", sa.String(length=36), nullable=True),
        sa.Column("review_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.String(length=32), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        *[
            sa.ForeignKeyConstraint(
                [f"{name}_id"],
                [f"{table}.id"],
                name=op.f(f"fk_note_{name}_id_{table}"),
                ondelete="SET NULL",
            )
            for name, table in (("parent", "note"), ("paper", "paper"), ("review", "review"))
        ],
        sa.PrimaryKeyConstraint("id", name=op.f("pk_note")),
    )
    with op.batch_alter_table("note", schema=None) as batch_op:
        for name in ("parent_id", "paper_id", "review_id"):
            batch_op.create_index(batch_op.f(f"ix_note_{name}"), [name], unique=False)
    op.create_table(
        "note_link",
        sa.Column("source_note_id", sa.String(length=36), nullable=False),
        sa.Column("ord", sa.Integer(), nullable=False),
        sa.Column(
            "target_type",
            sa.Enum(
                "note",
                "paper",
                "anchor",
                name="target_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "(target_type IS NULL) = (target_id IS NULL)",
            name=op.f("ck_note_link_target_is_whole"),
        ),
        sa.ForeignKeyConstraint(
            ["source_note_id"],
            ["note.id"],
            name=op.f("fk_note_link_source_note_id_note"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_note_link")),
    )
    with op.batch_alter_table("note_link", schema=None) as batch_op:
        for name in ("source_note_id", "target_id"):
            batch_op.create_index(batch_op.f(f"ix_note_link_{name}"), [name], unique=False)
    op.execute(
        "CREATE VIRTUAL TABLE note_fts USING fts5("
        "note_id UNINDEXED, title, body, tokenize = 'unicode61 remove_diacritics 2')"
    )


def downgrade() -> None:
    op.execute("DROP TABLE note_fts")
    op.drop_table("note_link")
    op.drop_table("note")
