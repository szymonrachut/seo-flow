"""content gap items v1

Revision ID: 0021_content_gap_items
Revises: 0020_content_gap_review_runs
Create Date: 2026-03-19 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0021_content_gap_items"
down_revision = "0020_content_gap_review_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_content_gap_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("basis_crawl_job_id", sa.Integer(), nullable=False),
        sa.Column("review_run_id", sa.Integer(), nullable=False),
        sa.Column("source_candidate_id", sa.Integer(), nullable=False),
        sa.Column("source_candidate_key", sa.String(length=96), nullable=False),
        sa.Column("source_candidate_input_hash", sa.String(length=64), nullable=False),
        sa.Column("item_status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("decision_action", sa.String(length=32), nullable=False),
        sa.Column("display_state", sa.String(length=32), nullable=False, server_default="visible"),
        sa.Column("review_group_key", sa.String(length=96), nullable=False),
        sa.Column("group_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("original_phrase", sa.String(length=255), nullable=False),
        sa.Column("original_topic_label", sa.String(length=255), nullable=False),
        sa.Column("reviewed_phrase", sa.String(length=255), nullable=True),
        sa.Column("reviewed_topic_label", sa.String(length=255), nullable=True),
        sa.Column("reviewed_normalized_topic_key", sa.String(length=255), nullable=True),
        sa.Column("reviewed_gap_type", sa.String(length=64), nullable=True),
        sa.Column("fit_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("decision_reason_code", sa.String(length=64), nullable=True),
        sa.Column("decision_reason_text", sa.Text(), nullable=False),
        sa.Column("merge_target_candidate_key", sa.String(length=96), nullable=True),
        sa.Column("merge_target_phrase", sa.String(length=255), nullable=True),
        sa.Column("remove_reason_code", sa.String(length=64), nullable=True),
        sa.Column("remove_reason_text", sa.Text(), nullable=True),
        sa.Column("rewrite_reason_text", sa.Text(), nullable=True),
        sa.Column("own_site_alignment_json", sa.JSON(), nullable=True),
        sa.Column("gsc_support_json", sa.JSON(), nullable=True),
        sa.Column("competitor_evidence_json", sa.JSON(), nullable=True),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=True),
        sa.Column("output_language", sa.String(length=16), nullable=False, server_default="en"),
        sa.Column("response_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_decision_json", sa.JSON(), nullable=True),
        sa.Column("visible_in_results", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["basis_crawl_job_id"], ["crawl_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_run_id"], ["site_content_gap_review_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_candidate_id"], ["site_content_gap_candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_run_id", "source_candidate_id", name="uq_site_content_gap_items_run_candidate"),
    )
    op.create_index("ix_site_content_gap_items_site_id", "site_content_gap_items", ["site_id"], unique=False)
    op.create_index(
        "ix_site_content_gap_items_basis_crawl_job_id",
        "site_content_gap_items",
        ["basis_crawl_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_items_review_run_id",
        "site_content_gap_items",
        ["review_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_items_source_candidate_id",
        "site_content_gap_items",
        ["source_candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_items_item_status",
        "site_content_gap_items",
        ["item_status"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_items_site_crawl_visible",
        "site_content_gap_items",
        ["site_id", "basis_crawl_job_id", "visible_in_results"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_items_site_crawl_group",
        "site_content_gap_items",
        ["site_id", "basis_crawl_job_id", "review_group_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_site_content_gap_items_site_crawl_group", table_name="site_content_gap_items")
    op.drop_index("ix_site_content_gap_items_site_crawl_visible", table_name="site_content_gap_items")
    op.drop_index("ix_site_content_gap_items_item_status", table_name="site_content_gap_items")
    op.drop_index("ix_site_content_gap_items_source_candidate_id", table_name="site_content_gap_items")
    op.drop_index("ix_site_content_gap_items_review_run_id", table_name="site_content_gap_items")
    op.drop_index("ix_site_content_gap_items_basis_crawl_job_id", table_name="site_content_gap_items")
    op.drop_index("ix_site_content_gap_items_site_id", table_name="site_content_gap_items")
    op.drop_table("site_content_gap_items")
