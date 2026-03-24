"""content gap review runs v1

Revision ID: 0020_content_gap_review_runs
Revises: 0019_content_gap_candidates
Create Date: 2026-03-19 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0020_content_gap_review_runs"
down_revision = "0019_content_gap_candidates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_content_gap_review_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("basis_crawl_job_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("trigger_source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("scope_type", sa.String(length=32), nullable=False, server_default="all_current"),
        sa.Column("selected_candidate_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_set_hash", sa.String(length=64), nullable=False),
        sa.Column("candidate_generation_version", sa.String(length=32), nullable=False),
        sa.Column("own_context_hash", sa.String(length=64), nullable=False),
        sa.Column("gsc_context_hash", sa.String(length=64), nullable=True),
        sa.Column("context_summary_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("output_language", sa.String(length=16), nullable=False, server_default="en"),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=True),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("batch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_batch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message_safe", sa.Text(), nullable=True),
        sa.Column("retry_of_run_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["basis_crawl_job_id"], ["crawl_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "run_id", name="uq_site_content_gap_review_runs_site_id_run_id"),
    )
    op.create_index(
        "ix_site_content_gap_review_runs_site_id",
        "site_content_gap_review_runs",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_review_runs_basis_crawl_job_id",
        "site_content_gap_review_runs",
        ["basis_crawl_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_review_runs_status",
        "site_content_gap_review_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_review_runs_lease_expires_at",
        "site_content_gap_review_runs",
        ["lease_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_review_runs_site_crawl_created_at",
        "site_content_gap_review_runs",
        ["site_id", "basis_crawl_job_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_site_content_gap_review_runs_site_crawl_created_at", table_name="site_content_gap_review_runs")
    op.drop_index("ix_site_content_gap_review_runs_lease_expires_at", table_name="site_content_gap_review_runs")
    op.drop_index("ix_site_content_gap_review_runs_status", table_name="site_content_gap_review_runs")
    op.drop_index("ix_site_content_gap_review_runs_basis_crawl_job_id", table_name="site_content_gap_review_runs")
    op.drop_index("ix_site_content_gap_review_runs_site_id", table_name="site_content_gap_review_runs")
    op.drop_table("site_content_gap_review_runs")
