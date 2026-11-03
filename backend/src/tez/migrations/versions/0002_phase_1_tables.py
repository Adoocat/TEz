"""Phase 1 tables: library core, reviews and search, jobs, settings (Task 6).

search_run, search_result and screening_decision are append-only, enforced by triggers
(ADR 0004).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03 22:10:52.701053
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = ("search_run", "search_result", "screening_decision")


def upgrade() -> None:
    op.create_table(
        "author",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=True),
        sa.Column("given", sa.Text(), nullable=True),
        sa.Column("orcid", sa.String(length=19), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_author")),
        sa.UniqueConstraint("orcid", name=op.f("uq_author_orcid")),
    )
    op.create_table(
        "collection",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["collection.id"],
            name=op.f("fk_collection_parent_id_collection"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection")),
    )
    with op.batch_alter_table("collection", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_collection_parent_id"), ["parent_id"], unique=False)

    op.create_table(
        "paper",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("title_norm", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("venue", sa.Text(), nullable=True),
        sa.Column(
            "venue_type",
            sa.Enum(
                "journal",
                "conference",
                "preprint",
                "book",
                "chapter",
                "thesis",
                "report",
                "other",
                name="venue_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("volume", sa.String(length=32), nullable=True),
        sa.Column("issue", sa.String(length=32), nullable=True),
        sa.Column("pages", sa.String(length=32), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("oa_url", sa.Text(), nullable=True),
        sa.Column("citation_count", sa.Integer(), nullable=True),
        sa.Column(
            "reading_status",
            sa.Enum(
                "unread",
                "reading",
                "read",
                name="reading_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("citekey", sa.String(length=128), nullable=True),
        sa.Column(
            "retraction_status",
            sa.Enum(
                "none",
                "retracted",
                "expression_of_concern",
                name="retraction_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint("citation_count >= 0", name=op.f("ck_paper_citation_count")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paper")),
        sa.UniqueConstraint("citekey", name=op.f("uq_paper_citekey")),
    )
    with op.batch_alter_table("paper", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_paper_title_norm"), ["title_norm"], unique=False)
        batch_op.create_index(batch_op.f("ix_paper_year"), ["year"], unique=False)

    op.create_table(
        "processing_job",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=256), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "done",
                "failed",
                "cancelled",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.String(length=32), nullable=True),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_processing_job_attempts")),
        sa.CheckConstraint("max_attempts >= 1", name=op.f("ck_processing_job_max_attempts")),
        sa.CheckConstraint("progress BETWEEN 0 AND 1", name=op.f("ck_processing_job_progress")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processing_job")),
    )
    with op.batch_alter_table("processing_job", schema=None) as batch_op:
        batch_op.create_index(
            "ix_processing_job_pick", ["status", "priority", "created_at"], unique=False
        )
        batch_op.create_index(
            "uq_processing_job_dedupe_key_active",
            ["dedupe_key"],
            unique=True,
            sqlite_where=sa.text("status IN ('queued', 'running')"),
        )

    op.create_table(
        "review",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("research_questions_md", sa.Text(), nullable=True),
        sa.Column("protocol_md", sa.Text(), nullable=True),
        sa.Column(
            "method",
            sa.Enum(
                "prisma2020",
                "kitchenham_slr",
                name="method",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("active", "archived", name="status", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review")),
    )
    op.create_table(
        "setting",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_setting")),
    )
    op.create_table(
        "smart_collection",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("filter_json", sa.JSON(), nullable=False),
        sa.Column("filter_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_smart_collection")),
    )
    op.create_table(
        "tag",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tag")),
        sa.UniqueConstraint("name", name=op.f("uq_tag_name")),
    )
    op.create_table(
        "attachment",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("pdf", "supplement", name="kind", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("rel_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column(
            "text_status",
            sa.Enum(
                "pending",
                "ok",
                "needs_ocr",
                "failed",
                name="text_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint("length(sha256) = 64", name=op.f("ck_attachment_sha256_length")),
        sa.CheckConstraint("page_count >= 0", name=op.f("ck_attachment_page_count")),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["paper.id"],
            name=op.f("fk_attachment_paper_id_paper"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attachment")),
        sa.UniqueConstraint("sha256", name=op.f("uq_attachment_sha256")),
    )
    with op.batch_alter_table("attachment", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_attachment_paper_id"), ["paper_id"], unique=False)

    op.create_table(
        "collection_paper",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("collection_id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["collection.id"],
            name=op.f("fk_collection_paper_collection_id_collection"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["paper.id"],
            name=op.f("fk_collection_paper_paper_id_paper"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_paper")),
        sa.UniqueConstraint(
            "collection_id", "paper_id", name=op.f("uq_collection_paper_collection_id_paper_id")
        ),
    )
    with op.batch_alter_table("collection_paper", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_collection_paper_paper_id"), ["paper_id"], unique=False
        )

    op.create_table(
        "paper_author",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("affiliation_raw", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint("position >= 0", name=op.f("ck_paper_author_position")),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["author.id"],
            name=op.f("fk_paper_author_author_id_author"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["paper.id"],
            name=op.f("fk_paper_author_paper_id_paper"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paper_author")),
        sa.UniqueConstraint("paper_id", "position", name=op.f("uq_paper_author_paper_id_position")),
    )
    with op.batch_alter_table("paper_author", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_paper_author_author_id"), ["author_id"], unique=False)

    op.create_table(
        "paper_identifier",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column(
            "scheme",
            sa.Enum(
                "doi",
                "arxiv",
                "s2",
                "openalex",
                "dblp",
                "isbn",
                "zotero",
                name="scheme",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("value", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["paper.id"],
            name=op.f("fk_paper_identifier_paper_id_paper"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paper_identifier")),
        sa.UniqueConstraint("scheme", "value", name=op.f("uq_paper_identifier_scheme_value")),
    )
    with op.batch_alter_table("paper_identifier", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_paper_identifier_paper_id"), ["paper_id"], unique=False
        )

    op.create_table(
        "paper_relation",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("from_paper_id", sa.String(length=36), nullable=False),
        sa.Column("to_paper_id", sa.String(length=36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "version_of",
                "erratum_of",
                "retraction_of",
                name="kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint("from_paper_id != to_paper_id", name=op.f("ck_paper_relation_not_self")),
        sa.ForeignKeyConstraint(
            ["from_paper_id"],
            ["paper.id"],
            name=op.f("fk_paper_relation_from_paper_id_paper"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_paper_id"],
            ["paper.id"],
            name=op.f("fk_paper_relation_to_paper_id_paper"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paper_relation")),
        sa.UniqueConstraint(
            "from_paper_id",
            "to_paper_id",
            "kind",
            name=op.f("uq_paper_relation_from_paper_id_to_paper_id_kind"),
        ),
    )
    with op.batch_alter_table("paper_relation", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_paper_relation_to_paper_id"), ["to_paper_id"], unique=False
        )

    op.create_table(
        "paper_tag",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["paper_id"], ["paper.id"], name=op.f("fk_paper_tag_paper_id_paper"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tag.id"], name=op.f("fk_paper_tag_tag_id_tag"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paper_tag")),
        sa.UniqueConstraint("paper_id", "tag_id", name=op.f("uq_paper_tag_paper_id_tag_id")),
    )
    with op.batch_alter_table("paper_tag", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_paper_tag_tag_id"), ["tag_id"], unique=False)

    op.create_table(
        "review_record",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column(
            "origin",
            sa.Enum(
                "database",
                "citation_backward",
                "citation_forward",
                "manual",
                name="origin",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("origin_ref", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["paper.id"],
            name=op.f("fk_review_record_paper_id_paper"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["review.id"],
            name=op.f("fk_review_record_review_id_review"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_record")),
        sa.UniqueConstraint(
            "review_id", "paper_id", name=op.f("uq_review_record_review_id_paper_id")
        ),
    )
    with op.batch_alter_table("review_record", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_review_record_paper_id"), ["paper_id"], unique=False)

    op.create_table(
        "screening_criterion",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "inclusion", "exclusion", name="kind", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "stage",
            sa.Enum(
                "title_abstract",
                "full_text",
                name="stage",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["review.id"],
            name=op.f("fk_screening_criterion_review_id_review"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_screening_criterion")),
        sa.UniqueConstraint(
            "review_id", "code", name=op.f("uq_screening_criterion_review_id_code")
        ),
    )
    op.create_table(
        "search_query",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=True),
        sa.Column("alert_enabled", sa.Boolean(), nullable=False),
        sa.Column("alert_last_run_at", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["review.id"],
            name=op.f("fk_search_query_review_id_review"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_query")),
    )
    with op.batch_alter_table("search_query", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_search_query_review_id"), ["review_id"], unique=False)

    op.create_table(
        "screening_decision",
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
        sa.Column(
            "decision",
            sa.Enum(
                "include",
                "exclude",
                "maybe",
                name="decision",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("criterion_id", sa.String(length=36), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewer", sa.String(length=64), nullable=False),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["criterion_id"],
            ["screening_criterion.id"],
            name=op.f("fk_screening_decision_criterion_id_screening_criterion"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["paper.id"],
            name=op.f("fk_screening_decision_paper_id_paper"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "paper_id"],
            ["review_record.review_id", "review_record.paper_id"],
            name=op.f("fk_screening_decision_review_id_paper_id_review_record"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["review.id"],
            name=op.f("fk_screening_decision_review_id_review"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["screening_decision.id"],
            name=op.f("fk_screening_decision_supersedes_id_screening_decision"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_screening_decision")),
        sa.UniqueConstraint("supersedes_id", name=op.f("uq_screening_decision_supersedes_id")),
    )
    with op.batch_alter_table("screening_decision", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_screening_decision_paper_id"), ["paper_id"], unique=False
        )

    op.create_table(
        "search_run",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("query_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("translated_query", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.String(length=32), nullable=False),
        sa.Column(
            "initiated_via",
            sa.Enum("gui", "cli", name="initiated_via", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("total_reported", sa.Integer(), nullable=True),
        sa.Column("retrieved_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ok", "partial", "error", name="status", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("snapshot_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint("retrieved_count >= 0", name=op.f("ck_search_run_retrieved_count")),
        sa.CheckConstraint("total_reported >= 0", name=op.f("ck_search_run_total_reported")),
        sa.ForeignKeyConstraint(
            ["query_id"],
            ["search_query.id"],
            name=op.f("fk_search_run_query_id_search_query"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["review.id"],
            name=op.f("fk_search_run_review_id_review"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_run")),
    )
    with op.batch_alter_table("search_run", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_search_run_review_id"), ["review_id"], unique=False)

    op.create_table(
        "search_result",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column(
            "match_method",
            sa.Enum(
                "doi",
                "id",
                "title_fuzzy",
                "new",
                name="match_method",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "match_score BETWEEN 0 AND 1", name=op.f("ck_search_result_match_score")
        ),
        sa.CheckConstraint("rank >= 1", name=op.f("ck_search_result_rank")),
        sa.ForeignKeyConstraint(
            ["paper_id"],
            ["paper.id"],
            name=op.f("fk_search_result_paper_id_paper"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["search_run.id"],
            name=op.f("fk_search_result_run_id_search_run"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_result")),
        sa.UniqueConstraint("run_id", "rank", name=op.f("uq_search_result_run_id_rank")),
    )
    with op.batch_alter_table("search_result", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_search_result_paper_id"), ["paper_id"], unique=False)

    for table in APPEND_ONLY_TABLES:
        for operation in ("update", "delete"):
            op.execute(
                f"CREATE TRIGGER {table}_append_only_{operation}"
                f" BEFORE {operation.upper()} ON {table}"
                f" BEGIN SELECT RAISE(ABORT, 'append-only table: {table}'); END"
            )


def downgrade() -> None:
    for table in APPEND_ONLY_TABLES:
        for operation in ("update", "delete"):
            op.execute(f"DROP TRIGGER {table}_append_only_{operation}")
    with op.batch_alter_table("search_result", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_search_result_paper_id"))

    op.drop_table("search_result")
    with op.batch_alter_table("search_run", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_search_run_review_id"))

    op.drop_table("search_run")
    with op.batch_alter_table("screening_decision", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_screening_decision_paper_id"))

    op.drop_table("screening_decision")
    with op.batch_alter_table("search_query", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_search_query_review_id"))

    op.drop_table("search_query")
    op.drop_table("screening_criterion")
    with op.batch_alter_table("review_record", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_review_record_paper_id"))

    op.drop_table("review_record")
    with op.batch_alter_table("paper_tag", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_paper_tag_tag_id"))

    op.drop_table("paper_tag")
    with op.batch_alter_table("paper_relation", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_paper_relation_to_paper_id"))

    op.drop_table("paper_relation")
    with op.batch_alter_table("paper_identifier", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_paper_identifier_paper_id"))

    op.drop_table("paper_identifier")
    with op.batch_alter_table("paper_author", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_paper_author_author_id"))

    op.drop_table("paper_author")
    with op.batch_alter_table("collection_paper", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_collection_paper_paper_id"))

    op.drop_table("collection_paper")
    with op.batch_alter_table("attachment", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_attachment_paper_id"))

    op.drop_table("attachment")
    op.drop_table("tag")
    op.drop_table("smart_collection")
    op.drop_table("setting")
    op.drop_table("review")
    with op.batch_alter_table("processing_job", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_processing_job_dedupe_key_active",
            sqlite_where=sa.text("status IN ('queued', 'running')"),
        )
        batch_op.drop_index("ix_processing_job_pick")

    op.drop_table("processing_job")
    with op.batch_alter_table("paper", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_paper_year"))
        batch_op.drop_index(batch_op.f("ix_paper_title_norm"))

    op.drop_table("paper")
    with op.batch_alter_table("collection", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_collection_parent_id"))

    op.drop_table("collection")
    op.drop_table("author")
