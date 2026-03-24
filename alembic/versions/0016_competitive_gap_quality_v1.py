"""Add quality-first semantic card and own profile persistence for competitive gap.

Revision ID: 0016_competitive_gap_quality_v1
Revises: 0015_semantic_arbiter
Create Date: 2026-03-18 22:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0016_competitive_gap_quality_v1"
down_revision: str | None = "0015_semantic_arbiter"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "site_competitor_page_extractions",
        sa.Column("semantic_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "site_competitor_page_extractions",
        sa.Column("semantic_input_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "site_competitor_page_extractions",
        sa.Column("semantic_card_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "site_competitor_page_extractions",
        sa.Column("chunk_summary_json", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_site_competitor_page_extractions_semantic_input_hash",
        "site_competitor_page_extractions",
        ["semantic_input_hash"],
        unique=False,
    )

    op.create_table(
        "crawl_page_semantic_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("crawl_job_id", sa.Integer(), nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=False),
        sa.Column("semantic_input_hash", sa.String(length=64), nullable=False),
        sa.Column("semantic_version", sa.String(length=64), nullable=False),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("semantic_card_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["crawl_job_id"], ["crawl_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "page_id",
            "semantic_input_hash",
            name="uq_crawl_page_semantic_profiles_page_id_hash",
        ),
    )
    op.create_index(
        "ix_crawl_page_semantic_profiles_site_id",
        "crawl_page_semantic_profiles",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_crawl_page_semantic_profiles_crawl_job_id",
        "crawl_page_semantic_profiles",
        ["crawl_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_crawl_page_semantic_profiles_page_id",
        "crawl_page_semantic_profiles",
        ["page_id"],
        unique=False,
    )
    op.create_index(
        "ix_crawl_page_semantic_profiles_crawl_job_id_current",
        "crawl_page_semantic_profiles",
        ["crawl_job_id", "current"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_crawl_page_semantic_profiles_crawl_job_id_current",
        table_name="crawl_page_semantic_profiles",
    )
    op.drop_index(
        "ix_crawl_page_semantic_profiles_page_id",
        table_name="crawl_page_semantic_profiles",
    )
    op.drop_index(
        "ix_crawl_page_semantic_profiles_crawl_job_id",
        table_name="crawl_page_semantic_profiles",
    )
    op.drop_index(
        "ix_crawl_page_semantic_profiles_site_id",
        table_name="crawl_page_semantic_profiles",
    )
    op.drop_table("crawl_page_semantic_profiles")

    op.drop_index(
        "ix_site_competitor_page_extractions_semantic_input_hash",
        table_name="site_competitor_page_extractions",
    )
    op.drop_column("site_competitor_page_extractions", "chunk_summary_json")
    op.drop_column("site_competitor_page_extractions", "semantic_card_json")
    op.drop_column("site_competitor_page_extractions", "semantic_input_hash")
    op.drop_column("site_competitor_page_extractions", "semantic_version")
