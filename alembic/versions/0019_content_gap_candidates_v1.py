"""Add raw content gap candidate store.

Revision ID: 0019_content_gap_candidates
Revises: 0018_comp_gap_cluster_state
Create Date: 2026-03-19 18:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0019_content_gap_candidates"
down_revision: str | None = "0018_comp_gap_cluster_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_content_gap_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("basis_crawl_job_id", sa.Integer(), nullable=False),
        sa.Column("candidate_key", sa.String(length=96), nullable=False),
        sa.Column("candidate_input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("generation_version", sa.String(length=32), nullable=False),
        sa.Column("rules_version", sa.String(length=32), nullable=False),
        sa.Column("normalized_topic_key", sa.String(length=255), nullable=False),
        sa.Column("original_topic_label", sa.String(length=255), nullable=False),
        sa.Column("original_phrase", sa.String(length=255), nullable=False),
        sa.Column("gap_type", sa.String(length=64), nullable=False),
        sa.Column("source_cluster_key", sa.String(length=96), nullable=False),
        sa.Column("source_cluster_hash", sa.String(length=64), nullable=False),
        sa.Column("source_competitor_ids_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source_competitor_page_ids_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("competitor_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("own_coverage_hint", sa.String(length=64), nullable=False),
        sa.Column("deterministic_priority_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rationale_summary", sa.Text(), nullable=False),
        sa.Column("signals_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("review_needed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("review_visibility", sa.String(length=32), nullable=False, server_default="visible"),
        sa.Column("first_generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["basis_crawl_job_id"], ["crawl_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "site_id",
            "basis_crawl_job_id",
            "candidate_key",
            "candidate_input_hash",
            name="uq_site_content_gap_candidates_site_crawl_key_hash",
        ),
    )
    op.create_index(
        "ix_site_content_gap_candidates_site_id",
        "site_content_gap_candidates",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_candidates_basis_crawl_job_id",
        "site_content_gap_candidates",
        ["basis_crawl_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_candidates_site_crawl_current",
        "site_content_gap_candidates",
        ["site_id", "basis_crawl_job_id", "current"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_candidates_site_crawl_status",
        "site_content_gap_candidates",
        ["site_id", "basis_crawl_job_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_candidates_site_crawl_topic_key",
        "site_content_gap_candidates",
        ["site_id", "basis_crawl_job_id", "normalized_topic_key"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_gap_candidates_site_crawl_candidate_key",
        "site_content_gap_candidates",
        ["site_id", "basis_crawl_job_id", "candidate_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_content_gap_candidates_site_crawl_candidate_key",
        table_name="site_content_gap_candidates",
    )
    op.drop_index(
        "ix_site_content_gap_candidates_site_crawl_topic_key",
        table_name="site_content_gap_candidates",
    )
    op.drop_index(
        "ix_site_content_gap_candidates_site_crawl_status",
        table_name="site_content_gap_candidates",
    )
    op.drop_index(
        "ix_site_content_gap_candidates_site_crawl_current",
        table_name="site_content_gap_candidates",
    )
    op.drop_index(
        "ix_site_content_gap_candidates_basis_crawl_job_id",
        table_name="site_content_gap_candidates",
    )
    op.drop_index(
        "ix_site_content_gap_candidates_site_id",
        table_name="site_content_gap_candidates",
    )
    op.drop_table("site_content_gap_candidates")
