"""Screening decisions can be `undecided` (undo) and `not_retrieved` (Task 31, ADR 0022).

SQLite cannot change a CHECK constraint, so the table is rebuilt (copy and rename). The
rebuild drops the append-only triggers with the old table; they are created again after.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# A copy of tez.core.db.NAMING_CONVENTION as it was, so the rebuilt table keeps its names.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "screening_decision"
OLD = ("include", "exclude", "maybe")
NEW = (*OLD, "undecided", "not_retrieved")


def _decision(values: Sequence[str]) -> sa.Enum:
    return sa.Enum(
        *values,
        name="decision",
        native_enum=False,
        create_constraint=True,
        length=max(len(v) for v in values),
    )


def _table(values: Sequence[str]) -> sa.Table:
    """The table as it stands with `values`, for batch mode to copy from."""
    return sa.Table(
        TABLE,
        sa.MetaData(naming_convention=NAMING_CONVENTION),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column(
            "stage",
            sa.Enum(
                "title_abstract",
                "full_text",
                name="stage",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("decision", _decision(values), nullable=False),
        sa.Column("criterion_id", sa.String(length=36), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewer", sa.String(length=64), nullable=False),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["criterion_id"],
            ["screening_criterion.id"],
            name="fk_screening_decision_criterion_id_screening_criterion",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["paper.id"],
            name="fk_screening_decision_paper_id_paper",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "paper_id"],
            ["review_record.review_id", "review_record.paper_id"],
            name="fk_screening_decision_review_id_paper_id_review_record",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["review.id"],
            name="fk_screening_decision_review_id_review",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["screening_decision.id"],
            name="fk_screening_decision_supersedes_id_screening_decision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_screening_decision"),
        sa.UniqueConstraint("supersedes_id", name="uq_screening_decision_supersedes_id"),
        sa.Index("ix_screening_decision_paper_id", "paper_id"),
    )


def _drop_triggers() -> None:
    for operation in ("update", "delete"):
        op.execute(f"DROP TRIGGER IF EXISTS {TABLE}_append_only_{operation}")


def _create_triggers() -> None:
    for operation in ("update", "delete"):
        op.execute(
            f"CREATE TRIGGER {TABLE}_append_only_{operation}"
            f" BEFORE {operation.upper()} ON {TABLE}"
            f" BEGIN SELECT RAISE(ABORT, 'append-only table: {TABLE}'); END"
        )


def _rebuild(old: Sequence[str], new: Sequence[str]) -> None:
    _drop_triggers()
    with op.batch_alter_table(TABLE, copy_from=_table(old), recreate="always") as batch_op:
        batch_op.alter_column("decision", existing_type=_decision(old), type_=_decision(new))
    _create_triggers()


def upgrade() -> None:
    _rebuild(OLD, NEW)


def downgrade() -> None:
    # Rows with the new values cannot be kept; downgrading a library that has them fails on
    # the CHECK constraint, which leaves it unchanged (migrations run in one transaction).
    _rebuild(NEW, OLD)
