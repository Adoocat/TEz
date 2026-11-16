"""Grey literature methods for search runs: website, organisation, register, thesis (Task 37).

ADR 0025. SQLite cannot change a CHECK constraint, so batch mode rebuilds `search_run`; the
rebuild drops its append-only triggers, which are taken down first and put back afterwards.

Revision ID: 0015
Revises: 0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ("database", "citation_backward", "citation_forward")
NEW = (*OLD, "website", "organisation", "register", "thesis")


def _method(values: Sequence[str]) -> sa.Enum:
    return sa.Enum(
        *values,
        name="method",
        native_enum=False,
        create_constraint=True,
        length=max(len(v) for v in values),
    )


def _triggers(action: str) -> None:
    for operation in ("update", "delete"):
        if action == "drop":
            op.execute(f"DROP TRIGGER search_run_append_only_{operation}")
        else:
            op.execute(
                f"CREATE TRIGGER search_run_append_only_{operation}"
                f" BEFORE {operation.upper()} ON search_run"
                " BEGIN SELECT RAISE(ABORT, 'append-only table: search_run'); END"
            )


def _change(old: Sequence[str], new: Sequence[str]) -> None:
    _triggers("drop")
    with op.batch_alter_table("search_run", schema=None) as batch_op:
        batch_op.alter_column(
            "method",
            existing_type=_method(old),
            type_=_method(new),
            existing_nullable=False,
            existing_server_default="database",
        )
    _triggers("create")


def upgrade() -> None:
    _change(OLD, NEW)


def downgrade() -> None:
    # A library with grey-literature runs cannot go back: the CHECK fails and nothing changes.
    _change(NEW, OLD)
