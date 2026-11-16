"""Quality assessment: quality_setting, quality_question, quality_assessment (Task 38).

Left out of Phase 1 (Task 6). quality_setting turns the optional stage on per review
(ADR 0026).

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quality_question",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("scale_json", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("template", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["review.id"],
            name=op.f("fk_quality_question_review_id_review"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quality_question")),
    )
    with op.batch_alter_table("quality_question", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_quality_question_review_id"), ["review_id"], unique=False
        )

    op.create_table(
        "quality_setting",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["review.id"],
            name=op.f("fk_quality_setting_review_id_review"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quality_setting")),
        sa.UniqueConstraint("review_id", name=op.f("uq_quality_setting_review_id")),
    )
    op.create_table(
        "quality_assessment",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("answer", sa.String(length=32), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewer", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["paper.id"],
            name=op.f("fk_quality_assessment_paper_id_paper"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["quality_question.id"],
            name=op.f("fk_quality_assessment_question_id_quality_question"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "paper_id"],
            ["review_record.review_id", "review_record.paper_id"],
            name=op.f("fk_quality_assessment_review_id_paper_id_review_record"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["review.id"],
            name=op.f("fk_quality_assessment_review_id_review"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quality_assessment")),
        sa.UniqueConstraint(
            "review_id",
            "paper_id",
            "question_id",
            "reviewer",
            name=op.f("uq_quality_assessment_review_id_paper_id_question_id_reviewer"),
        ),
    )
    with op.batch_alter_table("quality_assessment", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_quality_assessment_paper_id"), ["paper_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_quality_assessment_question_id"), ["question_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("quality_assessment", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_quality_assessment_question_id"))
        batch_op.drop_index(batch_op.f("ix_quality_assessment_paper_id"))

    op.drop_table("quality_assessment")
    op.drop_table("quality_setting")
    with op.batch_alter_table("quality_question", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_quality_question_review_id"))

    op.drop_table("quality_question")
