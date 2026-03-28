"""semstorm briefs v1

Revision ID: 0025_semstorm_briefs_v1
Revises: 0024_semstorm_planning_v1
Create Date: 2026-03-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0025_semstorm_briefs_v1"
down_revision = "0024_semstorm_planning_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_semstorm_brief_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("plan_item_id", sa.Integer(), nullable=False),
        sa.Column("state_status", sa.String(length=32), nullable=False),
        sa.Column("brief_title", sa.Text(), nullable=True),
        sa.Column("brief_type", sa.String(length=32), nullable=False),
        sa.Column("primary_keyword", sa.String(length=512), nullable=False),
        sa.Column("secondary_keywords_json", sa.JSON(), nullable=True),
        sa.Column("search_intent", sa.String(length=32), nullable=False),
        sa.Column("target_url_existing", sa.String(length=2048), nullable=True),
        sa.Column("proposed_url_slug", sa.String(length=512), nullable=True),
        sa.Column("recommended_page_title", sa.Text(), nullable=True),
        sa.Column("recommended_h1", sa.Text(), nullable=True),
        sa.Column("content_goal", sa.Text(), nullable=True),
        sa.Column("angle_summary", sa.Text(), nullable=True),
        sa.Column("sections_json", sa.JSON(), nullable=True),
        sa.Column("internal_link_targets_json", sa.JSON(), nullable=True),
        sa.Column("source_notes_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_item_id"], ["site_semstorm_plan_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_item_id", name="uq_site_semstorm_brief_items_plan_item_id"),
    )
    op.create_index(
        "ix_site_semstorm_brief_items_site_id",
        "site_semstorm_brief_items",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_brief_items_site_id_state_status",
        "site_semstorm_brief_items",
        ["site_id", "state_status"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_brief_items_site_id_brief_type",
        "site_semstorm_brief_items",
        ["site_id", "brief_type"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_brief_items_site_id_search_intent",
        "site_semstorm_brief_items",
        ["site_id", "search_intent"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_brief_items_site_id_updated_at",
        "site_semstorm_brief_items",
        ["site_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_semstorm_brief_items_site_id_updated_at",
        table_name="site_semstorm_brief_items",
    )
    op.drop_index(
        "ix_site_semstorm_brief_items_site_id_search_intent",
        table_name="site_semstorm_brief_items",
    )
    op.drop_index(
        "ix_site_semstorm_brief_items_site_id_brief_type",
        table_name="site_semstorm_brief_items",
    )
    op.drop_index(
        "ix_site_semstorm_brief_items_site_id_state_status",
        table_name="site_semstorm_brief_items",
    )
    op.drop_index(
        "ix_site_semstorm_brief_items_site_id",
        table_name="site_semstorm_brief_items",
    )
    op.drop_table("site_semstorm_brief_items")
