"""Add ETAP 12A competitive gap backend core tables.

Revision ID: 0008_stage12a_gap_core
Revises: 0007_stage11_page_taxonomy
Create Date: 2026-03-16 16:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0008_stage12a_gap_core"
down_revision: str | None = "0007_stage11_page_taxonomy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_content_strategies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("raw_user_input", sa.Text(), nullable=False),
        sa.Column("normalized_strategy_json", sa.JSON(), nullable=True),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("normalization_status", sa.String(length=32), nullable=False, server_default="not_processed"),
        sa.Column("normalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", name="uq_site_content_strategies_site_id"),
    )
    op.create_index("ix_site_content_strategies_site_id", "site_content_strategies", ["site_id"], unique=False)

    op.create_table(
        "site_competitors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("root_url", sa.String(length=2048), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_sync_status", sa.String(length=32), nullable=False, server_default="not_started"),
        sa.Column("last_sync_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "domain", name="uq_site_competitors_site_id_domain"),
    )
    op.create_index("ix_site_competitors_site_id", "site_competitors", ["site_id"], unique=False)
    op.create_index("ix_site_competitors_domain", "site_competitors", ["domain"], unique=False)
    op.create_index("ix_site_competitors_site_id_is_active", "site_competitors", ["site_id", "is_active"], unique=False)

    op.create_table(
        "site_competitor_pages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("competitor_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("normalized_url", sa.String(length=2048), nullable=False),
        sa.Column("final_url", sa.String(length=2048), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("h1", sa.Text(), nullable=True),
        sa.Column("canonical_url", sa.String(length=2048), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("content_text_hash", sa.String(length=64), nullable=True),
        sa.Column("visible_text", sa.Text(), nullable=True),
        sa.Column("visible_text_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("visible_text_truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("schema_present", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("schema_count", sa.Integer(), nullable=True),
        sa.Column("schema_types_json", sa.JSON(), nullable=True),
        sa.Column("page_type", sa.String(length=64), nullable=False, server_default="other"),
        sa.Column("page_bucket", sa.String(length=64), nullable=False, server_default="other"),
        sa.Column("page_type_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("page_type_version", sa.String(length=64), nullable=False, server_default="unclassified"),
        sa.Column("page_type_rationale", sa.Text(), nullable=True),
        sa.Column("was_rendered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("render_attempted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fetch_mode_used", sa.String(length=32), nullable=True),
        sa.Column("js_heavy_like", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("render_reason", sa.Text(), nullable=True),
        sa.Column("render_error_message", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["competitor_id"], ["site_competitors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("competitor_id", "normalized_url", name="uq_site_competitor_pages_competitor_id_normalized_url"),
    )
    op.create_index("ix_site_competitor_pages_site_id", "site_competitor_pages", ["site_id"], unique=False)
    op.create_index("ix_site_competitor_pages_competitor_id", "site_competitor_pages", ["competitor_id"], unique=False)
    op.create_index("ix_site_competitor_pages_normalized_url", "site_competitor_pages", ["normalized_url"], unique=False)
    op.create_index(
        "ix_site_competitor_pages_content_text_hash",
        "site_competitor_pages",
        ["content_text_hash"],
        unique=False,
    )

    op.create_table(
        "site_competitor_page_extractions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("competitor_id", sa.Integer(), nullable=False),
        sa.Column("competitor_page_id", sa.Integer(), nullable=False),
        sa.Column("content_hash_at_extraction", sa.String(length=64), nullable=True),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("schema_version", sa.String(length=64), nullable=True),
        sa.Column("topic_label", sa.String(length=255), nullable=True),
        sa.Column("topic_key", sa.String(length=255), nullable=False),
        sa.Column("search_intent", sa.String(length=64), nullable=True),
        sa.Column("content_format", sa.String(length=64), nullable=True),
        sa.Column("page_role", sa.String(length=64), nullable=True),
        sa.Column("secondary_topics_json", sa.JSON(), nullable=True),
        sa.Column("entities_json", sa.JSON(), nullable=True),
        sa.Column("evidence_snippets_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["competitor_id"], ["site_competitors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["competitor_page_id"], ["site_competitor_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_site_competitor_page_extractions_site_id", "site_competitor_page_extractions", ["site_id"], unique=False)
    op.create_index(
        "ix_site_competitor_page_extractions_competitor_id",
        "site_competitor_page_extractions",
        ["competitor_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_page_extractions_competitor_page_id",
        "site_competitor_page_extractions",
        ["competitor_page_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_page_extractions_topic_key",
        "site_competitor_page_extractions",
        ["topic_key"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_page_extractions_site_id_topic_key",
        "site_competitor_page_extractions",
        ["site_id", "topic_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_site_competitor_page_extractions_site_id_topic_key", table_name="site_competitor_page_extractions")
    op.drop_index("ix_site_competitor_page_extractions_topic_key", table_name="site_competitor_page_extractions")
    op.drop_index("ix_site_competitor_page_extractions_competitor_page_id", table_name="site_competitor_page_extractions")
    op.drop_index("ix_site_competitor_page_extractions_competitor_id", table_name="site_competitor_page_extractions")
    op.drop_index("ix_site_competitor_page_extractions_site_id", table_name="site_competitor_page_extractions")
    op.drop_table("site_competitor_page_extractions")

    op.drop_index("ix_site_competitor_pages_content_text_hash", table_name="site_competitor_pages")
    op.drop_index("ix_site_competitor_pages_normalized_url", table_name="site_competitor_pages")
    op.drop_index("ix_site_competitor_pages_competitor_id", table_name="site_competitor_pages")
    op.drop_index("ix_site_competitor_pages_site_id", table_name="site_competitor_pages")
    op.drop_table("site_competitor_pages")

    op.drop_index("ix_site_competitors_site_id_is_active", table_name="site_competitors")
    op.drop_index("ix_site_competitors_domain", table_name="site_competitors")
    op.drop_index("ix_site_competitors_site_id", table_name="site_competitors")
    op.drop_table("site_competitors")

    op.drop_index("ix_site_content_strategies_site_id", table_name="site_content_strategies")
    op.drop_table("site_content_strategies")
