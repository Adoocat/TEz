"""Full-text search over paper metadata: the paper_fts table (Task 19, ADR 0014).

The columns hold text already folded by tez.shared.text.fold, because FTS5's unicode61
tokenizer folds Turkish wrongly. The application fills and maintains the table; a library
opened after this migration is indexed then (tez.modules.library.search_index).

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE VIRTUAL TABLE paper_fts USING fts5("
        "paper_id UNINDEXED, title, authors, abstract, venue, extra, "
        "tokenize = 'unicode61 remove_diacritics 2')"
    )


def downgrade() -> None:
    op.execute("DROP TABLE paper_fts")
