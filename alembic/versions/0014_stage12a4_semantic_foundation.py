"""Add semantic foundation tables and metadata for competitive gap.

Revision ID: 0014_semantic_foundation
Revises: 0013_comp_gap_sync_runs
Create Date: 2026-03-17 11:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0014_semantic_foundation"
down_revision: str | None = "0013_comp_gap_sync_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "site_competitor_pages",
        sa.Column("robots_meta", sa.Text(), nullable=True),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("x_robots_tag", sa.Text(), nullable=True),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("semantic_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("semantic_exclusion_reason", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("semantic_input_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("semantic_last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_site_competitor_pages_competitor_id_semantic_eligible",
        "site_competitor_pages",
        ["competitor_id", "semantic_eligible"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_pages_semantic_input_hash",
        "site_competitor_pages",
        ["semantic_input_hash"],
        unique=False,
    )

    op.create_table(
        "site_competitor_semantic_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("competitor_id", sa.Integer(), nullable=False),
        sa.Column("competitor_page_id", sa.Integer(), nullable=False),
        sa.Column("semantic_input_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_topic_key", sa.String(length=255), nullable=False),
        sa.Column("raw_topic_label", sa.String(length=255), nullable=False),
        sa.Column("primary_tokens_json", sa.JSON(), nullable=False),
        sa.Column("secondary_tokens_json", sa.JSON(), nullable=False),
        sa.Column("match_terms_json", sa.JSON(), nullable=False),
        sa.Column("page_type", sa.String(length=64), nullable=False),
        sa.Column("page_bucket", sa.String(length=64), nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["competitor_id"], ["site_competitors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["competitor_page_id"], ["site_competitor_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "competitor_page_id",
            "semantic_input_hash",
            name="uq_site_competitor_semantic_candidates_page_id_hash",
        ),
    )
    op.create_index(
        "ix_site_competitor_semantic_candidates_site_id",
        "site_competitor_semantic_candidates",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_candidates_competitor_id",
        "site_competitor_semantic_candidates",
        ["competitor_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_candidates_competitor_page_id",
        "site_competitor_semantic_candidates",
        ["competitor_page_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_candidates_site_id_current",
        "site_competitor_semantic_candidates",
        ["site_id", "current"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_candidates_raw_topic_key",
        "site_competitor_semantic_candidates",
        ["raw_topic_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_competitor_semantic_candidates_raw_topic_key",
        table_name="site_competitor_semantic_candidates",
    )
    op.drop_index(
        "ix_site_competitor_semantic_candidates_site_id_current",
        table_name="site_competitor_semantic_candidates",
    )
    op.drop_index(
        "ix_site_competitor_semantic_candidates_competitor_page_id",
        table_name="site_competitor_semantic_candidates",
    )
    op.drop_index(
        "ix_site_competitor_semantic_candidates_competitor_id",
        table_name="site_competitor_semantic_candidates",
    )
    op.drop_index(
        "ix_site_competitor_semantic_candidates_site_id",
        table_name="site_competitor_semantic_candidates",
    )
    op.drop_table("site_competitor_semantic_candidates")

    op.drop_index("ix_site_competitor_pages_semantic_input_hash", table_name="site_competitor_pages")
    op.drop_index(
        "ix_site_competitor_pages_competitor_id_semantic_eligible",
        table_name="site_competitor_pages",
    )
    op.drop_column("site_competitor_pages", "semantic_last_evaluated_at")
    op.drop_column("site_competitor_pages", "semantic_input_hash")
    op.drop_column("site_competitor_pages", "semantic_exclusion_reason")
    op.drop_column("site_competitor_pages", "semantic_eligible")
    op.drop_column("site_competitor_pages", "x_robots_tag")
    op.drop_column("site_competitor_pages", "robots_meta")
