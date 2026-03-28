"""semstorm lifecycle v1

Revision ID: 0023_semstorm_lifecycle_v1
Revises: 0022_semstorm_discovery_v1
Create Date: 2026-03-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0023_semstorm_lifecycle_v1"
down_revision: str | None = "0022_semstorm_discovery_v1"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "site_semstorm_opportunity_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_key", sa.String(length=96), nullable=False),
        sa.Column("source_run_id", sa.Integer(), nullable=True),
        sa.Column("normalized_keyword", sa.String(length=512), nullable=False),
        sa.Column("state_status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "site_id",
            "normalized_keyword",
            name="uq_site_semstorm_opportunity_states_site_keyword",
        ),
    )
    op.create_index(
        "ix_site_semstorm_opportunity_states_site_id",
        "site_semstorm_opportunity_states",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_opportunity_states_site_id_status",
        "site_semstorm_opportunity_states",
        ["site_id", "state_status"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_opportunity_states_opportunity_key",
        "site_semstorm_opportunity_states",
        ["opportunity_key"],
        unique=False,
    )

    op.create_table(
        "site_semstorm_promoted_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("opportunity_key", sa.String(length=96), nullable=False),
        sa.Column("source_run_id", sa.Integer(), nullable=False),
        sa.Column("keyword", sa.String(length=512), nullable=False),
        sa.Column("normalized_keyword", sa.String(length=512), nullable=False),
        sa.Column("bucket", sa.String(length=32), nullable=False),
        sa.Column("decision_type", sa.String(length=32), nullable=False),
        sa.Column("opportunity_score_v2", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage_status", sa.String(length=32), nullable=False),
        sa.Column("best_match_page_url", sa.String(length=2048), nullable=True),
        sa.Column("gsc_signal_status", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("source_payload_json", sa.JSON(), nullable=True),
        sa.Column("promotion_status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "site_id",
            "normalized_keyword",
            name="uq_site_semstorm_promoted_items_site_keyword",
        ),
    )
    op.create_index(
        "ix_site_semstorm_promoted_items_site_id",
        "site_semstorm_promoted_items",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_promoted_items_site_id_status",
        "site_semstorm_promoted_items",
        ["site_id", "promotion_status"],
        unique=False,
    )
    op.create_index(
        "ix_site_semstorm_promoted_items_opportunity_key",
        "site_semstorm_promoted_items",
        ["opportunity_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_semstorm_promoted_items_opportunity_key",
        table_name="site_semstorm_promoted_items",
    )
    op.drop_index(
        "ix_site_semstorm_promoted_items_site_id_status",
        table_name="site_semstorm_promoted_items",
    )
    op.drop_index(
        "ix_site_semstorm_promoted_items_site_id",
        table_name="site_semstorm_promoted_items",
    )
    op.drop_table("site_semstorm_promoted_items")

    op.drop_index(
        "ix_site_semstorm_opportunity_states_opportunity_key",
        table_name="site_semstorm_opportunity_states",
    )
    op.drop_index(
        "ix_site_semstorm_opportunity_states_site_id_status",
        table_name="site_semstorm_opportunity_states",
    )
    op.drop_index(
        "ix_site_semstorm_opportunity_states_site_id",
        table_name="site_semstorm_opportunity_states",
    )
    op.drop_table("site_semstorm_opportunity_states")
