"""PubMed identifiers: paper_identifier.scheme takes pmid and pmcid (Task 29, ADR 0020).

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BEFORE = ("doi", "arxiv", "s2", "openalex", "dblp", "isbn", "zotero")
_AFTER = (*_BEFORE, "pmid", "pmcid")


def _scheme(values: tuple[str, ...]) -> sa.Enum:
    return sa.Enum(*values, name="scheme", native_enum=False, create_constraint=True)


def upgrade() -> None:
    # SQLite cannot change a CHECK in place: batch mode rebuilds the (small) table.
    with op.batch_alter_table("paper_identifier") as batch:
        batch.alter_column(
            "scheme", existing_type=_scheme(_BEFORE), type_=_scheme(_AFTER), nullable=False
        )


def downgrade() -> None:
    op.execute("DELETE FROM paper_identifier WHERE scheme IN ('pmid', 'pmcid')")
    with op.batch_alter_table("paper_identifier") as batch:
        batch.alter_column(
            "scheme", existing_type=_scheme(_AFTER), type_=_scheme(_BEFORE), nullable=False
        )
