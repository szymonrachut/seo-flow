"""Initial schema for SEO crawler ETAP 1.

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-12 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def build_crawl_job_status_enum(*, is_postgresql: bool) -> sa.Enum:
    if is_postgresql:
        return postgresql.ENUM(
            "pending",
            "running",
            "finished",
            "failed",
            name="crawl_job_status",
            create_type=False,
        )
    return sa.Enum(
        "pending",
        "running",
        "finished",
        "failed",
        name="crawl_job_status",
        native_enum=False,
    )


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    status_enum = build_crawl_job_status_enum(is_postgresql=is_postgresql)
    if is_postgresql:
        status_enum.create(bind, checkfirst=True)
    empty_json_default = sa.text("'{}'::json") if is_postgresql else sa.text("'{}'")

    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("root_url", sa.String(length=2048), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_sites_domain", "sites", ["domain"], unique=True)

    op.create_table(
        "crawl_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("settings_json", sa.JSON(), nullable=False, server_default=empty_json_default),
        sa.Column("stats_json", sa.JSON(), nullable=False, server_default=empty_json_default),
    )
    op.create_index("ix_crawl_jobs_site_id", "crawl_jobs", ["site_id"], unique=False)

    op.create_table(
        "pages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("crawl_job_id", sa.Integer(), sa.ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("normalized_url", sa.String(length=2048), nullable=False),
        sa.Column("final_url", sa.String(length=2048), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("h1", sa.Text(), nullable=True),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("depth", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("crawl_job_id", "normalized_url", name="uq_pages_crawl_job_id_normalized_url"),
    )
    op.create_index("ix_pages_crawl_job_id", "pages", ["crawl_job_id"], unique=False)
    op.create_index("ix_pages_status_code", "pages", ["status_code"], unique=False)
    op.create_index("ix_pages_is_internal", "pages", ["is_internal"], unique=False)
    op.create_index("ix_pages_depth", "pages", ["depth"], unique=False)

    op.create_table(
        "links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("crawl_job_id", sa.Integer(), sa.ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_page_id", sa.Integer(), sa.ForeignKey("pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("target_normalized_url", sa.String(length=2048), nullable=True),
        sa.Column("target_domain", sa.String(length=255), nullable=True),
        sa.Column("anchor_text", sa.Text(), nullable=True),
        sa.Column("rel_attr", sa.String(length=512), nullable=True),
        sa.Column("is_nofollow", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_links_crawl_job_id", "links", ["crawl_job_id"], unique=False)
    op.create_index("ix_links_source_page_id", "links", ["source_page_id"], unique=False)
    op.create_index("ix_links_target_domain", "links", ["target_domain"], unique=False)
    op.create_index("ix_links_is_internal", "links", ["is_internal"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    status_enum = build_crawl_job_status_enum(is_postgresql=is_postgresql)

    op.drop_index("ix_links_is_internal", table_name="links")
    op.drop_index("ix_links_target_domain", table_name="links")
    op.drop_index("ix_links_source_page_id", table_name="links")
    op.drop_index("ix_links_crawl_job_id", table_name="links")
    op.drop_table("links")

    op.drop_index("ix_pages_depth", table_name="pages")
    op.drop_index("ix_pages_is_internal", table_name="pages")
    op.drop_index("ix_pages_status_code", table_name="pages")
    op.drop_index("ix_pages_crawl_job_id", table_name="pages")
    op.drop_table("pages")

    op.drop_index("ix_crawl_jobs_site_id", table_name="crawl_jobs")
    op.drop_table("crawl_jobs")

    op.drop_index("ix_sites_domain", table_name="sites")
    op.drop_table("sites")

    if is_postgresql:
        status_enum.drop(bind, checkfirst=True)
