"""semstorm planning v1

Revision ID: 0024_semstorm_planning_v1
Revises: 0023_semstorm_lifecycle_v1
Create Date: 2026-03-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0024_semstorm_planning_v1"
down_revision: str | None = "0023_semstorm_lifecycle_v1"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "site_semstorm_plan_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("promoted_item_id", sa.Integer(), nullable=False),
        sa.Column("keyword", sa.String(length=512), nullable=False),
        sa.Column("normalized_keyword", sa.String(length=512), nullable=False),
        sa.Column("source_run_id", sa.Integer(), nullable=False),
        sa.Column("state_status", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("decision_type_snapshot", sa.String(length=32), nullable=False),
        sa.Column("bucket_snapshot", sa.String(length=32), nullable=False),
        sa.Column("coverage_status_snapshot", sa.String(length=32), nullable=False),
        sa.Column("opportunity_score_v2_snapshot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_match_page_url_snapshot", sa.String(length=2048), nullable=True),
        sa.Column("gsc_signal_status_snapshot", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("plan_title", sa.Text(), nullable=True),
        sa.Column("plan_note", sa.Text(), nullable=True),
        sa.Column("target_page_type", sa.String(length=32), nullable=False, server_default="new_page"),
        sa.Column("proposed_slug", sa.String(length=512), nullable=True),
        sa.Column("proposed_primary_keyword", sa.String(length=512), nullable=True),
        sa.Column("proposed_secondary_keywords_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["promoted_item_id"], ["site_semstorm_promoted_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("promoted_item_id", name="uq_site_semstorm_plan_items_promoted_item_id"),
    )
    op.create_index(
        "ix_site_semstorm_plan_items_site_id",
        "site_semstorm_plan_items",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_plan_items_site_id_state_status",
        "site_semstorm_plan_items",
        ["site_id", "state_status"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_plan_items_site_id_target_page_type",
        "site_semstorm_plan_items",
        ["site_id", "target_page_type"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_plan_items_site_id_updated_at",
        "site_semstorm_plan_items",
        ["site_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_plan_items_site_id_normalized_keyword",
        "site_semstorm_plan_items",
        ["site_id", "normalized_keyword"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_semstorm_plan_items_site_id_normalized_keyword",
        table_name="site_semstorm_plan_items",
    )
    op.drop_index(
        "ix_site_semstorm_plan_items_site_id_updated_at",
        table_name="site_semstorm_plan_items",
    )
    op.drop_index(
        "ix_site_semstorm_plan_items_site_id_target_page_type",
        table_name="site_semstorm_plan_items",
    )
    op.drop_index(
        "ix_site_semstorm_plan_items_site_id_state_status",
        table_name="site_semstorm_plan_items",
    )
    op.drop_index(
        "ix_site_semstorm_plan_items_site_id",
        table_name="site_semstorm_plan_items",
    )
    op.drop_table("site_semstorm_plan_items")
