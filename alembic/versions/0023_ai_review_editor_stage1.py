"""ai review editor stage 1 foundation

Revision ID: 0023_ai_review_editor_stage1
Revises: 0022_content_gen_assets
Create Date: 2026-03-26 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0023_ai_review_editor_stage1"
down_revision: str | None = "0022_content_gen_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "editor_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("source_format", sa.String(length=32), nullable=False),
        sa.Column("source_content", sa.Text(), nullable=False),
        sa.Column("normalized_content", sa.Text(), nullable=True),
        sa.Column("topic_brief_json", sa.JSON(), nullable=True),
        sa.Column("facts_context_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('draft', 'parsed', 'archived')",
            name="ck_editor_documents_status",
        ),
    )
    op.create_index("ix_editor_documents_site_id", "editor_documents", ["site_id"], unique=False)
    op.create_index("ix_editor_documents_site_id_created_at", "editor_documents", ["site_id", "created_at"], unique=False)
    op.create_index("ix_editor_documents_site_id_status", "editor_documents", ["site_id", "status"], unique=False)

    op.create_table(
        "editor_document_blocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("block_key", sa.String(length=32), nullable=False),
        sa.Column("block_type", sa.String(length=32), nullable=False),
        sa.Column("block_level", sa.Integer(), nullable=True),
        sa.Column("parent_block_key", sa.String(length=32), nullable=True),
        sa.Column("position_index", sa.Integer(), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("html_content", sa.Text(), nullable=True),
        sa.Column("context_path", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["editor_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "block_key", name="uq_editor_document_blocks_document_id_block_key"),
        sa.UniqueConstraint("document_id", "position_index", name="uq_editor_document_blocks_document_id_position"),
    )
    op.create_index("ix_editor_document_blocks_document_id", "editor_document_blocks", ["document_id"], unique=False)
    op.create_index(
        "ix_editor_document_blocks_document_id_active",
        "editor_document_blocks",
        ["document_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_editor_document_blocks_document_id_type",
        "editor_document_blocks",
        ["document_id", "block_type"],
        unique=False,
    )

    op.create_table(
        "editor_review_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("document_version_hash", sa.String(length=64), nullable=False),
        sa.Column("review_mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["editor_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_editor_review_runs_status",
        ),
    )
    op.create_index("ix_editor_review_runs_document_id", "editor_review_runs", ["document_id"], unique=False)
    op.create_index(
        "ix_editor_review_runs_document_id_created_at",
        "editor_review_runs",
        ["document_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_editor_review_runs_document_id_status",
        "editor_review_runs",
        ["document_id", "status"],
        unique=False,
    )

    op.create_table(
        "editor_review_issues",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_run_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("block_key", sa.String(length=32), nullable=False),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("replacement_instruction", sa.Text(), nullable=True),
        sa.Column("replacement_candidate_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("dismiss_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["editor_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_run_id"], ["editor_review_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('open', 'dismissed', 'resolved')",
            name="ck_editor_review_issues_status",
        ),
    )
    op.create_index("ix_editor_review_issues_review_run_id", "editor_review_issues", ["review_run_id"], unique=False)
    op.create_index("ix_editor_review_issues_document_id", "editor_review_issues", ["document_id"], unique=False)
    op.create_index(
        "ix_editor_review_issues_document_id_status",
        "editor_review_issues",
        ["document_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_editor_review_issues_document_id_block_key",
        "editor_review_issues",
        ["document_id", "block_key"],
        unique=False,
    )

    op.create_table(
        "editor_rewrite_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("review_issue_id", sa.Integer(), nullable=True),
        sa.Column("block_key", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["editor_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_issue_id"], ["editor_review_issues.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_editor_rewrite_runs_status",
        ),
    )
    op.create_index("ix_editor_rewrite_runs_document_id", "editor_rewrite_runs", ["document_id"], unique=False)
    op.create_index(
        "ix_editor_rewrite_runs_review_issue_id",
        "editor_rewrite_runs",
        ["review_issue_id"],
        unique=False,
    )
    op.create_index(
        "ix_editor_rewrite_runs_document_id_status",
        "editor_rewrite_runs",
        ["document_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_editor_rewrite_runs_document_id_block_key",
        "editor_rewrite_runs",
        ["document_id", "block_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_editor_rewrite_runs_document_id_block_key", table_name="editor_rewrite_runs")
    op.drop_index("ix_editor_rewrite_runs_document_id_status", table_name="editor_rewrite_runs")
    op.drop_index("ix_editor_rewrite_runs_review_issue_id", table_name="editor_rewrite_runs")
    op.drop_index("ix_editor_rewrite_runs_document_id", table_name="editor_rewrite_runs")
    op.drop_table("editor_rewrite_runs")

    op.drop_index("ix_editor_review_issues_document_id_block_key", table_name="editor_review_issues")
    op.drop_index("ix_editor_review_issues_document_id_status", table_name="editor_review_issues")
    op.drop_index("ix_editor_review_issues_document_id", table_name="editor_review_issues")
    op.drop_index("ix_editor_review_issues_review_run_id", table_name="editor_review_issues")
    op.drop_table("editor_review_issues")

    op.drop_index("ix_editor_review_runs_document_id_status", table_name="editor_review_runs")
    op.drop_index("ix_editor_review_runs_document_id_created_at", table_name="editor_review_runs")
    op.drop_index("ix_editor_review_runs_document_id", table_name="editor_review_runs")
    op.drop_table("editor_review_runs")

    op.drop_index("ix_editor_document_blocks_document_id_type", table_name="editor_document_blocks")
    op.drop_index("ix_editor_document_blocks_document_id_active", table_name="editor_document_blocks")
    op.drop_index("ix_editor_document_blocks_document_id", table_name="editor_document_blocks")
    op.drop_table("editor_document_blocks")

    op.drop_index("ix_editor_documents_site_id_status", table_name="editor_documents")
    op.drop_index("ix_editor_documents_site_id_created_at", table_name="editor_documents")
    op.drop_index("ix_editor_documents_site_id", table_name="editor_documents")
    op.drop_table("editor_documents")
