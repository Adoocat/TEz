"""Record snowballing as search runs: search_run.method, snowball_round, seed_paper_id (Task 36).

Batch mode, because SQLite cannot add a named foreign key with ALTER TABLE. The rebuild drops
the table's append-only triggers, so they are taken down first and put back afterwards.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OPERATIONS = ("update", "delete")


def _drop_triggers() -> None:
    for operation in _OPERATIONS:
        op.execute(f"DROP TRIGGER search_run_append_only_{operation}")


def _create_triggers() -> None:
    for operation in _OPERATIONS:
        op.execute(
            f"CREATE TRIGGER search_run_append_only_{operation}"
            f" BEFORE {operation.upper()} ON search_run"
            " BEGIN SELECT RAISE(ABORT, 'append-only table: search_run'); END"
        )


def upgrade() -> None:
    _drop_triggers()
    with op.batch_alter_table("search_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "method",
                sa.Enum(
                    "database",
                    "citation_backward",
                    "citation_forward",
                    name="method",
                    native_enum=False,
                    create_constraint=True,
                    length=17,
                ),
                server_default="database",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("snowball_round", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("seed_paper_id", sa.String(length=36), nullable=True))
        batch_op.create_check_constraint("snowball_round", "snowball_round >= 1")
        batch_op.create_foreign_key(
            batch_op.f("fk_search_run_seed_paper_id_paper"),
            "paper",
            ["seed_paper_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            batch_op.f("ix_search_run_seed_paper_id"), ["seed_paper_id"], unique=False
        )
    _create_triggers()


def downgrade() -> None:
    _drop_triggers()
    with op.batch_alter_table("search_run", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_search_run_seed_paper_id"))
        batch_op.drop_constraint(
            batch_op.f("fk_search_run_seed_paper_id_paper"), type_="foreignkey"
        )
        batch_op.drop_constraint(batch_op.f("ck_search_run_snowball_round"), type_="check")
        batch_op.drop_constraint(batch_op.f("ck_search_run_method"), type_="check")
        batch_op.drop_column("seed_paper_id")
        batch_op.drop_column("snowball_round")
        batch_op.drop_column("method")
    _create_triggers()
