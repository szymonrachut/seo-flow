"""semstorm brief enrichment v1

Revision ID: 0026_semstorm_brief_ai_v1
Revises: 0025_semstorm_briefs_v1
Create Date: 2026-03-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0026_semstorm_brief_ai_v1"
down_revision = "0025_semstorm_briefs_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_semstorm_brief_enrichment_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("brief_item_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("engine_mode", sa.String(length=16), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output_summary_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message_safe", sa.Text(), nullable=True),
        sa.Column("is_applied", sa.Boolean(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["brief_item_id"], ["site_semstorm_brief_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_site_semstorm_brief_enrichment_runs_site_id",
        "site_semstorm_brief_enrichment_runs",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_brief_enrichment_runs_brief_item_id",
        "site_semstorm_brief_enrichment_runs",
        ["brief_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_brief_enrichment_runs_site_id_status",
        "site_semstorm_brief_enrichment_runs",
        ["site_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_brief_enrichment_runs_site_id_created_at",
        "site_semstorm_brief_enrichment_runs",
        ["site_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_semstorm_brief_enrichment_runs_site_id_created_at",
        table_name="site_semstorm_brief_enrichment_runs",
    )
    op.drop_index(
        "ix_site_semstorm_brief_enrichment_runs_site_id_status",
        table_name="site_semstorm_brief_enrichment_runs",
    )
    op.drop_index(
        "ix_site_semstorm_brief_enrichment_runs_brief_item_id",
        table_name="site_semstorm_brief_enrichment_runs",
    )
    op.drop_index(
        "ix_site_semstorm_brief_enrichment_runs_site_id",
        table_name="site_semstorm_brief_enrichment_runs",
    )
    op.drop_table("site_semstorm_brief_enrichment_runs")
