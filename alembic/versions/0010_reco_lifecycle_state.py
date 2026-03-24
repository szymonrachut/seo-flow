"""Add content recommendation lifecycle state table.

Revision ID: 0010_reco_lifecycle_state
Revises: 0009_comp_gap_sync_debug
Create Date: 2026-03-16 23:35:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0010_reco_lifecycle_state"
down_revision: str | None = "0009_comp_gap_sync_debug"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_content_recommendation_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("recommendation_key", sa.String(length=255), nullable=False),
        sa.Column("recommendation_type", sa.String(length=64), nullable=False),
        sa.Column("segment", sa.String(length=64), nullable=True),
        sa.Column("target_url", sa.String(length=2048), nullable=True),
        sa.Column("normalized_target_url", sa.String(length=2048), nullable=True),
        sa.Column("target_title_snapshot", sa.Text(), nullable=True),
        sa.Column("suggested_page_type", sa.String(length=64), nullable=True),
        sa.Column("cluster_label", sa.String(length=255), nullable=True),
        sa.Column("cluster_key", sa.String(length=255), nullable=True),
        sa.Column("recommendation_text", sa.Text(), nullable=False),
        sa.Column("signals_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("helper_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("primary_outcome_kind", sa.String(length=32), nullable=False),
        sa.Column("implemented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("implemented_crawl_job_id", sa.Integer(), nullable=True),
        sa.Column("implemented_baseline_crawl_job_id", sa.Integer(), nullable=True),
        sa.Column("times_marked_done", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["implemented_baseline_crawl_job_id"], ["crawl_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["implemented_crawl_job_id"], ["crawl_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "recommendation_key", name="uq_site_content_recommendation_states_site_id_key"),
    )
    op.create_index(
        "ix_site_content_recommendation_states_site_id",
        "site_content_recommendation_states",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_recommendation_states_site_id_impl_at",
        "site_content_recommendation_states",
        ["site_id", "implemented_at"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_recommendation_states_site_id_impl_crawl",
        "site_content_recommendation_states",
        ["site_id", "implemented_crawl_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_recommendation_states_normalized_target_url",
        "site_content_recommendation_states",
        ["normalized_target_url"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_content_recommendation_states_normalized_target_url",
        table_name="site_content_recommendation_states",
    )
    op.drop_index("ix_site_content_recommendation_states_site_id_impl_crawl", table_name="site_content_recommendation_states")
    op.drop_index("ix_site_content_recommendation_states_site_id_impl_at", table_name="site_content_recommendation_states")
    op.drop_index("ix_site_content_recommendation_states_site_id", table_name="site_content_recommendation_states")
    op.drop_table("site_content_recommendation_states")
