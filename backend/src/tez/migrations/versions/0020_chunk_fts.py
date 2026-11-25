"""Full-text search inside PDFs: chunk_fts over text_chunk (Task 44).

The table is contentless (no second copy of the text) and holds text already folded by
tez.shared.text.fold, like paper_fts. The application fills it; a library opened after this
migration is indexed then (tez.modules.fulltext.search_index). The trigger also covers rows
removed by a foreign-key cascade.

Revision ID: 0020
Revises: 0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("text_chunk", sa.Column("search_row", sa.Integer(), nullable=True))
    op.execute("UPDATE text_chunk SET search_row = rowid")
    with op.batch_alter_table("text_chunk", schema=None) as batch_op:
        batch_op.alter_column("search_row", existing_type=sa.Integer(), nullable=False)
        batch_op.create_unique_constraint(batch_op.f("uq_text_chunk_search_row"), ["search_row"])
        batch_op.create_index(
            "ix_text_chunk_search", ["search_row", "attachment_id", "page_index"], unique=False
        )
    op.execute(
        "CREATE VIRTUAL TABLE chunk_fts USING fts5("
        "text, content = '', contentless_delete = 1, "
        "tokenize = 'unicode61 remove_diacritics 2')"
    )
    op.execute(
        "CREATE TRIGGER tr_text_chunk_unindex AFTER DELETE ON text_chunk BEGIN "
        "DELETE FROM chunk_fts WHERE rowid = old.search_row; END"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER tr_text_chunk_unindex")
    op.execute("DROP TABLE chunk_fts")
    with op.batch_alter_table("text_chunk", schema=None) as batch_op:
        batch_op.drop_index("ix_text_chunk_search")
        batch_op.drop_constraint(batch_op.f("uq_text_chunk_search_row"), type_="unique")
        batch_op.drop_column("search_row")
