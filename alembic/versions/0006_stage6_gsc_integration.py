"""Add ETAP 6 Google Search Console tables.

Revision ID: 0006_stage6_gsc_integration
Revises: 0005_stage5_rendering_and_schema
Create Date: 2026-03-14 00:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_stage6_gsc_integration"
down_revision: str | None = "0005_stage5_rendering_and_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gsc_properties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("property_uri", sa.String(length=2048), nullable=False),
        sa.Column("permission_level", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", name="uq_gsc_properties_site_id"),
    )
    op.create_index("ix_gsc_properties_property_uri", "gsc_properties", ["property_uri"], unique=False)

    op.create_table(
        "gsc_url_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gsc_property_id", sa.Integer(), nullable=False),
        sa.Column("crawl_job_id", sa.Integer(), nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("normalized_url", sa.String(length=2048), nullable=False),
        sa.Column("date_range_label", sa.String(length=32), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("ctr", sa.Float(), nullable=True),
        sa.Column("position", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["crawl_job_id"], ["crawl_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gsc_property_id"], ["gsc_properties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "crawl_job_id",
            "normalized_url",
            "date_range_label",
            name="uq_gsc_url_metrics_job_url_range",
        ),
    )
    op.create_index("ix_gsc_url_metrics_job_range", "gsc_url_metrics", ["crawl_job_id", "date_range_label"], unique=False)
    op.create_index("ix_gsc_url_metrics_page_range", "gsc_url_metrics", ["page_id", "date_range_label"], unique=False)

    op.create_table(
        "gsc_top_queries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gsc_property_id", sa.Integer(), nullable=False),
        sa.Column("crawl_job_id", sa.Integer(), nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("normalized_url", sa.String(length=2048), nullable=False),
        sa.Column("date_range_label", sa.String(length=32), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("ctr", sa.Float(), nullable=True),
        sa.Column("position", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["crawl_job_id"], ["crawl_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gsc_property_id"], ["gsc_properties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "crawl_job_id",
            "normalized_url",
            "date_range_label",
            "query",
            name="uq_gsc_top_queries_job_url_range_query",
        ),
    )
    op.create_index("ix_gsc_top_queries_job_range", "gsc_top_queries", ["crawl_job_id", "date_range_label"], unique=False)
    op.create_index("ix_gsc_top_queries_page_range", "gsc_top_queries", ["page_id", "date_range_label"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_gsc_top_queries_page_range", table_name="gsc_top_queries")
    op.drop_index("ix_gsc_top_queries_job_range", table_name="gsc_top_queries")
    op.drop_table("gsc_top_queries")

    op.drop_index("ix_gsc_url_metrics_page_range", table_name="gsc_url_metrics")
    op.drop_index("ix_gsc_url_metrics_job_range", table_name="gsc_url_metrics")
    op.drop_table("gsc_url_metrics")

    op.drop_index("ix_gsc_properties_property_uri", table_name="gsc_properties")
    op.drop_table("gsc_properties")
