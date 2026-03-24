"""Add semantic arbiter cache and run store for competitive gap.

Revision ID: 0015_semantic_arbiter
Revises: 0014_semantic_foundation
Create Date: 2026-03-17 17:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0015_semantic_arbiter"
down_revision: str | None = "0014_semantic_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "site_competitor_semantic_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("competitor_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("trigger_source", sa.String(length=32), nullable=False, server_default="manual_incremental"),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="incremental"),
        sa.Column("active_crawl_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message_safe", sa.Text(), nullable=True),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("source_candidate_ids_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("summary_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["active_crawl_id"], ["crawl_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["competitor_id"], ["site_competitors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "competitor_id",
            "run_id",
            name="uq_site_competitor_semantic_runs_competitor_id_run_id",
        ),
    )
    op.create_index(
        "ix_site_competitor_semantic_runs_site_id",
        "site_competitor_semantic_runs",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_runs_competitor_id",
        "site_competitor_semantic_runs",
        ["competitor_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_runs_status",
        "site_competitor_semantic_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_runs_lease_expires_at",
        "site_competitor_semantic_runs",
        ["lease_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_runs_competitor_id_created_at",
        "site_competitor_semantic_runs",
        ["competitor_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "site_competitor_semantic_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("source_competitor_id", sa.Integer(), nullable=False),
        sa.Column("source_candidate_id", sa.Integer(), nullable=False),
        sa.Column("decision_type", sa.String(length=32), nullable=False),
        sa.Column("decision_key", sa.String(length=64), nullable=False),
        sa.Column("source_semantic_input_hash", sa.String(length=64), nullable=False),
        sa.Column("target_competitor_id", sa.Integer(), nullable=True),
        sa.Column("target_candidate_id", sa.Integer(), nullable=True),
        sa.Column("target_semantic_input_hash", sa.String(length=64), nullable=True),
        sa.Column("own_page_id", sa.Integer(), nullable=True),
        sa.Column("active_crawl_id", sa.Integer(), nullable=True),
        sa.Column("own_page_semantic_hash", sa.String(length=64), nullable=True),
        sa.Column("candidate_rank", sa.Integer(), nullable=True),
        sa.Column("candidate_score", sa.Integer(), nullable=True),
        sa.Column("decision_label", sa.String(length=64), nullable=False),
        sa.Column("canonical_topic_label", sa.String(length=255), nullable=True),
        sa.Column("decision_rationale", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("llm_provider", sa.String(length=64), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fallback_reason", sa.String(length=64), nullable=True),
        sa.Column("debug_code", sa.String(length=64), nullable=True),
        sa.Column("debug_message", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["active_crawl_id"], ["crawl_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["own_page_id"], ["pages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_candidate_id"], ["site_competitor_semantic_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_competitor_id"], ["site_competitors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_candidate_id"], ["site_competitor_semantic_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_competitor_id"], ["site_competitors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "decision_key",
            name="uq_site_competitor_semantic_decisions_decision_key",
        ),
    )
    op.create_index(
        "ix_site_competitor_semantic_decisions_site_id",
        "site_competitor_semantic_decisions",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_decisions_source_competitor_id",
        "site_competitor_semantic_decisions",
        ["source_competitor_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_decisions_source_candidate_id",
        "site_competitor_semantic_decisions",
        ["source_candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_decisions_target_candidate_id",
        "site_competitor_semantic_decisions",
        ["target_candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_decisions_decision_type",
        "site_competitor_semantic_decisions",
        ["decision_type"],
        unique=False,
    )
    op.create_index(
        "ix_site_competitor_semantic_decisions_active_crawl_id",
        "site_competitor_semantic_decisions",
        ["active_crawl_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_site_competitor_semantic_decisions_active_crawl_id",
        table_name="site_competitor_semantic_decisions",
    )
    op.drop_index(
        "ix_site_competitor_semantic_decisions_decision_type",
        table_name="site_competitor_semantic_decisions",
    )
    op.drop_index(
        "ix_site_competitor_semantic_decisions_target_candidate_id",
        table_name="site_competitor_semantic_decisions",
    )
    op.drop_index(
        "ix_site_competitor_semantic_decisions_source_candidate_id",
        table_name="site_competitor_semantic_decisions",
    )
    op.drop_index(
        "ix_site_competitor_semantic_decisions_source_competitor_id",
        table_name="site_competitor_semantic_decisions",
    )
    op.drop_index(
        "ix_site_competitor_semantic_decisions_site_id",
        table_name="site_competitor_semantic_decisions",
    )
    op.drop_table("site_competitor_semantic_decisions")

    op.drop_index(
        "ix_site_competitor_semantic_runs_competitor_id_created_at",
        table_name="site_competitor_semantic_runs",
    )
    op.drop_index(
        "ix_site_competitor_semantic_runs_lease_expires_at",
        table_name="site_competitor_semantic_runs",
    )
    op.drop_index(
        "ix_site_competitor_semantic_runs_status",
        table_name="site_competitor_semantic_runs",
    )
    op.drop_index(
        "ix_site_competitor_semantic_runs_competitor_id",
        table_name="site_competitor_semantic_runs",
    )
    op.drop_index(
        "ix_site_competitor_semantic_runs_site_id",
        table_name="site_competitor_semantic_runs",
    )
    op.drop_table("site_competitor_semantic_runs")
