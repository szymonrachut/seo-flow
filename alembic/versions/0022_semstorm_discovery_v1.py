"""semstorm discovery v1

Revision ID: 0022_semstorm_discovery_v1
Revises: 0021_content_gap_items
Create Date: 2026-03-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0022_semstorm_discovery_v1"
down_revision: str | None = "0021_content_gap_items"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "site_semstorm_discovery_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="discovering"),
        sa.Column("source_domain", sa.String(length=255), nullable=False),
        sa.Column("result_type", sa.String(length=16), nullable=False, server_default="organic"),
        sa.Column("competitors_type", sa.String(length=32), nullable=False, server_default="all"),
        sa.Column("include_basic_stats", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("max_competitors", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("max_keywords_per_competitor", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("total_competitors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_queries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_keywords", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message_safe", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "run_id", name="uq_site_semstorm_discovery_runs_site_id_run_id"),
    )
    op.create_index(
        "ix_site_semstorm_discovery_runs_site_id",
        "site_semstorm_discovery_runs",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_discovery_runs_status",
        "site_semstorm_discovery_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_discovery_runs_site_id_created_at",
        "site_semstorm_discovery_runs",
        ["site_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "site_semstorm_competitors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("discovery_run_id", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("common_keywords", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("traffic", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queries_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("basic_stats_keywords", sa.Integer(), nullable=True),
        sa.Column("basic_stats_keywords_top", sa.Integer(), nullable=True),
        sa.Column("basic_stats_traffic", sa.Integer(), nullable=True),
        sa.Column("basic_stats_traffic_potential", sa.Integer(), nullable=True),
        sa.Column("basic_stats_search_volume", sa.Integer(), nullable=True),
        sa.Column("basic_stats_search_volume_top", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(
            ["discovery_run_id"],
            ["site_semstorm_discovery_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discovery_run_id", "domain", name="uq_site_semstorm_competitors_run_domain"),
    )
    op.create_index(
        "ix_site_semstorm_competitors_site_id",
        "site_semstorm_competitors",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_competitors_discovery_run_id",
        "site_semstorm_competitors",
        ["discovery_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_competitors_domain",
        "site_semstorm_competitors",
        ["domain"],
        unique=False,
    )

    op.create_table(
        "site_semstorm_competitor_queries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("discovery_run_id", sa.Integer(), nullable=False),
        sa.Column("semstorm_competitor_id", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("keyword", sa.String(length=512), nullable=False),
        sa.Column("normalized_keyword", sa.String(length=512), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("position_change", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("traffic", sa.Integer(), nullable=True),
        sa.Column("traffic_change", sa.Integer(), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("competitors", sa.Integer(), nullable=True),
        sa.Column("cpc", sa.Float(), nullable=True),
        sa.Column("trends_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(
            ["discovery_run_id"],
            ["site_semstorm_discovery_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["semstorm_competitor_id"],
            ["site_semstorm_competitors.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_site_semstorm_competitor_queries_site_id",
        "site_semstorm_competitor_queries",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_competitor_queries_discovery_run_id",
        "site_semstorm_competitor_queries",
        ["discovery_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_competitor_queries_competitor_id",
        "site_semstorm_competitor_queries",
        ["semstorm_competitor_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_competitor_queries_run_keyword",
        "site_semstorm_competitor_queries",
        ["discovery_run_id", "normalized_keyword"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_semstorm_competitor_queries_run_keyword",
        table_name="site_semstorm_competitor_queries",
    )
    op.drop_index(
        "ix_site_semstorm_competitor_queries_competitor_id",
        table_name="site_semstorm_competitor_queries",
    )
    op.drop_index(
        "ix_site_semstorm_competitor_queries_discovery_run_id",
        table_name="site_semstorm_competitor_queries",
    )
    op.drop_index(
        "ix_site_semstorm_competitor_queries_site_id",
        table_name="site_semstorm_competitor_queries",
    )
    op.drop_table("site_semstorm_competitor_queries")

    op.drop_index(
        "ix_site_semstorm_competitors_domain",
        table_name="site_semstorm_competitors",
    )
    op.drop_index(
        "ix_site_semstorm_competitors_discovery_run_id",
        table_name="site_semstorm_competitors",
    )
    op.drop_index(
        "ix_site_semstorm_competitors_site_id",
        table_name="site_semstorm_competitors",
    )
    op.drop_table("site_semstorm_competitors")

    op.drop_index(
        "ix_site_semstorm_discovery_runs_site_id_created_at",
        table_name="site_semstorm_discovery_runs",
    )
    op.drop_index(
        "ix_site_semstorm_discovery_runs_status",
        table_name="site_semstorm_discovery_runs",
    )
    op.drop_index(
        "ix_site_semstorm_discovery_runs_site_id",
        table_name="site_semstorm_discovery_runs",
    )
    op.drop_table("site_semstorm_discovery_runs")
