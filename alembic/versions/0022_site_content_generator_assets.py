"""site content generator assets

Revision ID: 0022_content_gen_assets
Revises: 0021_content_gap_items
Create Date: 2026-03-26 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0022_content_gen_assets"
down_revision: str | None = "0021_content_gap_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_content_generator_assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("basis_crawl_job_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("surfer_custom_instructions", sa.Text(), nullable=True),
        sa.Column("seowriting_details_to_include", sa.Text(), nullable=True),
        sa.Column("introductory_hook_brief", sa.Text(), nullable=True),
        sa.Column("source_urls_json", sa.JSON(), nullable=True),
        sa.Column("source_pages_hash", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["basis_crawl_job_id"], ["crawl_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", name="uq_site_content_generator_assets_site_id"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'ready', 'failed')",
            name="ck_site_content_generator_assets_status",
        ),
    )
    op.create_index(
        "ix_site_content_generator_assets_site_id",
        "site_content_generator_assets",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_content_generator_assets_basis_crawl_job_id",
        "site_content_generator_assets",
        ["basis_crawl_job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_site_content_generator_assets_basis_crawl_job_id", table_name="site_content_generator_assets")
    op.drop_index("ix_site_content_generator_assets_site_id", table_name="site_content_generator_assets")
    op.drop_table("site_content_generator_assets")
