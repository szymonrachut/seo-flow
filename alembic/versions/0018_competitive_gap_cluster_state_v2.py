"""Persistent competitive gap cluster state cache.

Revision ID: 0018_comp_gap_cluster_state
Revises: 0017_competitive_gap_lean_v1
Create Date: 2026-03-19 16:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0018_comp_gap_cluster_state"
down_revision: str | None = "0017_competitive_gap_lean_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_competitive_gap_cluster_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("active_crawl_id", sa.Integer(), nullable=True),
        sa.Column("semantic_cluster_key", sa.String(length=64), nullable=False),
        sa.Column("topic_key", sa.String(length=255), nullable=True),
        sa.Column("canonical_topic_label", sa.String(length=255), nullable=True),
        sa.Column("source_candidate_ids_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("competitor_ids_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("cluster_state_hash", sa.String(length=64), nullable=False),
        sa.Column("coverage_state_hash", sa.String(length=64), nullable=True),
        sa.Column("cluster_summary_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("coverage_state_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["active_crawl_id"], ["crawl_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "site_id",
            "active_crawl_id",
            "semantic_cluster_key",
            name="uq_site_competitive_gap_cluster_states_site_crawl_cluster",
        ),
    )
    op.create_index(
        "ix_site_competitive_gap_cluster_states_site_id",
        "site_competitive_gap_cluster_states",
        ["site_id"],
    )
    op.create_index(
        "ix_site_competitive_gap_cluster_states_active_crawl_id",
        "site_competitive_gap_cluster_states",
        ["active_crawl_id"],
    )
    op.create_index(
        "ix_site_competitive_gap_cluster_states_cluster_key",
        "site_competitive_gap_cluster_states",
        ["semantic_cluster_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_competitive_gap_cluster_states_cluster_key",
        table_name="site_competitive_gap_cluster_states",
    )
    op.drop_index(
        "ix_site_competitive_gap_cluster_states_active_crawl_id",
        table_name="site_competitive_gap_cluster_states",
    )
    op.drop_index(
        "ix_site_competitive_gap_cluster_states_site_id",
        table_name="site_competitive_gap_cluster_states",
    )
    op.drop_table("site_competitive_gap_cluster_states")
