from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import event
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.text_processing import prepare_visible_text
from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CrawlJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    STOPPED = "stopped"


def crawl_job_status_sqlalchemy_enum() -> Enum:
    return Enum(
        CrawlJobStatus,
        name="crawl_job_status",
        values_callable=lambda enum_cls: [status.value for status in enum_cls],
        validate_strings=True,
    )


CONTENT_GENERATOR_ASSET_ALLOWED_STATUSES = frozenset({"pending", "running", "ready", "failed"})
CONTENT_GENERATOR_ASSET_STATUS_PENDING = "pending"


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    root_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    crawl_jobs: Mapped[list["CrawlJob"]] = relationship(back_populates="site", cascade="all, delete-orphan")
    gsc_property: Mapped["GscProperty | None"] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
        uselist=False,
    )
    content_strategy: Mapped["SiteContentStrategy | None"] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
        uselist=False,
    )
    content_generator_asset: Mapped["SiteContentGeneratorAsset | None"] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
        uselist=False,
    )
    content_recommendation_states: Mapped[list["SiteContentRecommendationState"]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
    content_gap_candidates: Mapped[list["SiteContentGapCandidate"]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
    content_gap_review_runs: Mapped[list["SiteContentGapReviewRun"]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
    content_gap_items: Mapped[list["SiteContentGapItem"]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
    semstorm_discovery_runs: Mapped[list["SiteSemstormDiscoveryRun"]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
    semstorm_opportunity_states: Mapped[list["SiteSemstormOpportunityState"]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
    semstorm_promoted_items: Mapped[list["SiteSemstormPromotedItem"]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
    semstorm_plan_items: Mapped[list["SiteSemstormPlanItem"]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
    semstorm_brief_items: Mapped[list["SiteSemstormBriefItem"]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
    semstorm_brief_enrichment_runs: Mapped[list["SiteSemstormBriefEnrichmentRun"]] = relationship(
        back_populates="site",
        cascade="all, delete-orphan",
    )
    competitors: Mapped[list["SiteCompetitor"]] = relationship(back_populates="site", cascade="all, delete-orphan")


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[CrawlJobStatus] = mapped_column(
        crawl_job_status_sqlalchemy_enum(),
        nullable=False,
        default=CrawlJobStatus.PENDING,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    settings_json: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSON), nullable=False, default=dict)
    stats_json: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSON), nullable=False, default=dict)

    site: Mapped[Site] = relationship(back_populates="crawl_jobs")
    pages: Mapped[list["Page"]] = relationship(back_populates="crawl_job", cascade="all, delete-orphan")
    links: Mapped[list["Link"]] = relationship(back_populates="crawl_job", cascade="all, delete-orphan")
    gsc_url_metrics: Mapped[list["GscUrlMetric"]] = relationship(
        back_populates="crawl_job",
        cascade="all, delete-orphan",
    )
    gsc_top_queries: Mapped[list["GscTopQuery"]] = relationship(
        back_populates="crawl_job",
        cascade="all, delete-orphan",
    )
    semantic_profiles: Mapped[list["CrawlPageSemanticProfile"]] = relationship(
        back_populates="crawl_job",
        cascade="all, delete-orphan",
    )
    content_generator_assets: Mapped[list["SiteContentGeneratorAsset"]] = relationship(
        back_populates="basis_crawl_job",
        cascade="all, delete-orphan",
    )
    content_gap_candidates: Mapped[list["SiteContentGapCandidate"]] = relationship(
        back_populates="basis_crawl_job",
        cascade="all, delete-orphan",
    )
    content_gap_review_runs: Mapped[list["SiteContentGapReviewRun"]] = relationship(
        back_populates="basis_crawl_job",
        cascade="all, delete-orphan",
    )
    content_gap_items: Mapped[list["SiteContentGapItem"]] = relationship(
        back_populates="basis_crawl_job",
        cascade="all, delete-orphan",
    )


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("crawl_job_id", "normalized_url", name="uq_pages_crawl_job_id_normalized_url"),
        Index("ix_pages_crawl_job_id", "crawl_job_id"),
        Index("ix_pages_status_code", "status_code"),
        Index("ix_pages_is_internal", "is_internal"),
        Index("ix_pages_depth", "depth"),
        Index("ix_pages_page_type", "page_type"),
        Index("ix_pages_page_bucket", "page_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crawl_job_id: Mapped[int] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    final_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    title_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    h1: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    h2_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    robots_meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    x_robots_tag: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    images_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    images_missing_alt_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    html_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    was_rendered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    render_attempted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fetch_mode_used: Mapped[str | None] = mapped_column(String(32), nullable=True)
    js_heavy_like: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    render_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    render_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    schema_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schema_types_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    page_type: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    page_bucket: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    page_type_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    page_type_version: Mapped[str] = mapped_column(String(64), nullable=False, default="unclassified")
    page_type_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    crawl_job: Mapped[CrawlJob] = relationship(back_populates="pages")
    outgoing_links: Mapped[list["Link"]] = relationship(back_populates="source_page", cascade="all, delete-orphan")
    gsc_url_metrics: Mapped[list["GscUrlMetric"]] = relationship(back_populates="page")
    gsc_top_queries: Mapped[list["GscTopQuery"]] = relationship(back_populates="page")
    semantic_profiles: Mapped[list["CrawlPageSemanticProfile"]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
    )


class Link(Base):
    __tablename__ = "links"
    __table_args__ = (
        Index("ix_links_crawl_job_id", "crawl_job_id"),
        Index("ix_links_source_page_id", "source_page_id"),
        Index("ix_links_target_domain", "target_domain"),
        Index("ix_links_is_internal", "is_internal"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crawl_job_id: Mapped[int] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False)
    source_page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    target_normalized_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    target_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    anchor_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    rel_attr: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_nofollow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    crawl_job: Mapped[CrawlJob] = relationship(back_populates="links")
    source_page: Mapped[Page] = relationship(back_populates="outgoing_links")


class SiteContentRecommendationState(Base):
    __tablename__ = "site_content_recommendation_states"
    __table_args__ = (
        UniqueConstraint("site_id", "recommendation_key", name="uq_site_content_recommendation_states_site_id_key"),
        Index("ix_site_content_recommendation_states_site_id", "site_id"),
        Index("ix_site_content_recommendation_states_site_id_impl_at", "site_id", "implemented_at"),
        Index("ix_site_content_recommendation_states_site_id_impl_crawl", "site_id", "implemented_crawl_job_id"),
        Index("ix_site_content_recommendation_states_normalized_target_url", "normalized_target_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    recommendation_key: Mapped[str] = mapped_column(String(255), nullable=False)
    recommendation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    segment: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    normalized_target_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    target_title_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_page_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cluster_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cluster_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recommendation_text: Mapped[str] = mapped_column(Text, nullable=False)
    signals_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
    )
    helper_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
    )
    primary_outcome_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    implemented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    implemented_crawl_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    implemented_baseline_crawl_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    times_marked_done: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="content_recommendation_states")


class SiteContentStrategy(Base):
    __tablename__ = "site_content_strategies"
    __table_args__ = (
        UniqueConstraint("site_id", name="uq_site_content_strategies_site_id"),
        Index("ix_site_content_strategies_site_id", "site_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    raw_user_input: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_strategy_json: Mapped[dict[str, Any] | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalization_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_processed")
    last_normalization_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    normalization_fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    normalization_debug_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalization_debug_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="content_strategy")


class SiteContentGeneratorAsset(Base):
    __tablename__ = "site_content_generator_assets"
    __table_args__ = (
        UniqueConstraint("site_id", name="uq_site_content_generator_assets_site_id"),
        Index("ix_site_content_generator_assets_site_id", "site_id"),
        Index("ix_site_content_generator_assets_basis_crawl_job_id", "basis_crawl_job_id"),
        CheckConstraint(
            "status IN ('pending', 'running', 'ready', 'failed')",
            name="ck_site_content_generator_assets_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    basis_crawl_job_id: Mapped[int] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=CONTENT_GENERATOR_ASSET_STATUS_PENDING)
    surfer_custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    seowriting_details_to_include: Mapped[str | None] = mapped_column(Text, nullable=True)
    introductory_hook_brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_urls_json: Mapped[list[str] | None] = mapped_column(MutableList.as_mutable(JSON), nullable=True)
    source_pages_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    @validates("status")
    def _validate_status(self, _key: str, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("SiteContentGeneratorAsset.status must be a string.")
        normalized_value = value.strip().lower()
        if normalized_value not in CONTENT_GENERATOR_ASSET_ALLOWED_STATUSES:
            allowed_values = ", ".join(sorted(CONTENT_GENERATOR_ASSET_ALLOWED_STATUSES))
            raise ValueError(f"Unsupported SiteContentGeneratorAsset.status: {value!r}. Allowed values: {allowed_values}.")
        return normalized_value

    site: Mapped[Site] = relationship(back_populates="content_generator_asset")
    basis_crawl_job: Mapped[CrawlJob] = relationship(back_populates="content_generator_assets")


class SiteSemstormDiscoveryRun(Base):
    __tablename__ = "site_semstorm_discovery_runs"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "run_id",
            name="uq_site_semstorm_discovery_runs_site_id_run_id",
        ),
        Index("ix_site_semstorm_discovery_runs_site_id", "site_id"),
        Index("ix_site_semstorm_discovery_runs_status", "status"),
        Index(
            "ix_site_semstorm_discovery_runs_site_id_created_at",
            "site_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="discovering")
    source_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    result_type: Mapped[str] = mapped_column(String(16), nullable=False, default="organic")
    competitors_type: Mapped[str] = mapped_column(String(32), nullable=False, default="all")
    include_basic_stats: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_competitors: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_keywords_per_competitor: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    total_competitors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_queries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_keywords: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message_safe: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="semstorm_discovery_runs")
    competitors: Mapped[list["SiteSemstormCompetitor"]] = relationship(
        back_populates="discovery_run",
        cascade="all, delete-orphan",
    )
    queries: Mapped[list["SiteSemstormCompetitorQuery"]] = relationship(
        back_populates="discovery_run",
        cascade="all, delete-orphan",
    )


class SiteSemstormCompetitor(Base):
    __tablename__ = "site_semstorm_competitors"
    __table_args__ = (
        UniqueConstraint(
            "discovery_run_id",
            "domain",
            name="uq_site_semstorm_competitors_run_domain",
        ),
        Index("ix_site_semstorm_competitors_site_id", "site_id"),
        Index("ix_site_semstorm_competitors_discovery_run_id", "discovery_run_id"),
        Index("ix_site_semstorm_competitors_domain", "domain"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    discovery_run_id: Mapped[int] = mapped_column(
        ForeignKey("site_semstorm_discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    common_keywords: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    traffic: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queries_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    basic_stats_keywords: Mapped[int | None] = mapped_column(Integer, nullable=True)
    basic_stats_keywords_top: Mapped[int | None] = mapped_column(Integer, nullable=True)
    basic_stats_traffic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    basic_stats_traffic_potential: Mapped[int | None] = mapped_column(Integer, nullable=True)
    basic_stats_search_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    basic_stats_search_volume_top: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    discovery_run: Mapped[SiteSemstormDiscoveryRun] = relationship(back_populates="competitors")
    queries: Mapped[list["SiteSemstormCompetitorQuery"]] = relationship(
        back_populates="competitor",
        cascade="all, delete-orphan",
    )


class SiteSemstormCompetitorQuery(Base):
    __tablename__ = "site_semstorm_competitor_queries"
    __table_args__ = (
        Index("ix_site_semstorm_competitor_queries_site_id", "site_id"),
        Index(
            "ix_site_semstorm_competitor_queries_discovery_run_id",
            "discovery_run_id",
        ),
        Index(
            "ix_site_semstorm_competitor_queries_competitor_id",
            "semstorm_competitor_id",
        ),
        Index(
            "ix_site_semstorm_competitor_queries_run_keyword",
            "discovery_run_id",
            "normalized_keyword",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    discovery_run_id: Mapped[int] = mapped_column(
        ForeignKey("site_semstorm_discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    semstorm_competitor_id: Mapped[int] = mapped_column(
        ForeignKey("site_semstorm_competitors.id", ondelete="CASCADE"),
        nullable=False,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_change: Mapped[int | None] = mapped_column(Integer, nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    traffic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    traffic_change: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    competitors: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cpc: Mapped[float | None] = mapped_column(Float, nullable=True)
    trends_json: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    discovery_run: Mapped[SiteSemstormDiscoveryRun] = relationship(back_populates="queries")
    competitor: Mapped[SiteSemstormCompetitor] = relationship(back_populates="queries")


class SiteSemstormOpportunityState(Base):
    __tablename__ = "site_semstorm_opportunity_states"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "normalized_keyword",
            name="uq_site_semstorm_opportunity_states_site_keyword",
        ),
        Index("ix_site_semstorm_opportunity_states_site_id", "site_id"),
        Index(
            "ix_site_semstorm_opportunity_states_site_id_status",
            "site_id",
            "state_status",
        ),
        Index(
            "ix_site_semstorm_opportunity_states_opportunity_key",
            "opportunity_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    opportunity_key: Mapped[str] = mapped_column(String(96), nullable=False)
    source_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    normalized_keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    state_status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="semstorm_opportunity_states")


class SiteSemstormPromotedItem(Base):
    __tablename__ = "site_semstorm_promoted_items"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "normalized_keyword",
            name="uq_site_semstorm_promoted_items_site_keyword",
        ),
        Index("ix_site_semstorm_promoted_items_site_id", "site_id"),
        Index(
            "ix_site_semstorm_promoted_items_site_id_status",
            "site_id",
            "promotion_status",
        ),
        Index(
            "ix_site_semstorm_promoted_items_opportunity_key",
            "opportunity_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    opportunity_key: Mapped[str] = mapped_column(String(96), nullable=False)
    source_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    bucket: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False)
    opportunity_score_v2: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage_status: Mapped[str] = mapped_column(String(32), nullable=False)
    best_match_page_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    gsc_signal_status: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    source_payload_json: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
    )
    promotion_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="semstorm_promoted_items")
    plan_item: Mapped["SiteSemstormPlanItem | None"] = relationship(
        back_populates="promoted_item",
        cascade="all, delete-orphan",
        uselist=False,
    )


class SiteSemstormPlanItem(Base):
    __tablename__ = "site_semstorm_plan_items"
    __table_args__ = (
        UniqueConstraint(
            "promoted_item_id",
            name="uq_site_semstorm_plan_items_promoted_item_id",
        ),
        Index("ix_site_semstorm_plan_items_site_id", "site_id"),
        Index(
            "ix_site_semstorm_plan_items_site_id_state_status",
            "site_id",
            "state_status",
        ),
        Index(
            "ix_site_semstorm_plan_items_site_id_target_page_type",
            "site_id",
            "target_page_type",
        ),
        Index(
            "ix_site_semstorm_plan_items_site_id_updated_at",
            "site_id",
            "updated_at",
        ),
        Index(
            "ix_site_semstorm_plan_items_site_id_normalized_keyword",
            "site_id",
            "normalized_keyword",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    promoted_item_id: Mapped[int] = mapped_column(
        ForeignKey("site_semstorm_promoted_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    source_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    state_status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    decision_type_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    bucket_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    coverage_status_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    opportunity_score_v2_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_match_page_url_snapshot: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    gsc_signal_status_snapshot: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    plan_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_page_type: Mapped[str] = mapped_column(String(32), nullable=False, default="new_page")
    proposed_slug: Mapped[str | None] = mapped_column(String(512), nullable=True)
    proposed_primary_keyword: Mapped[str | None] = mapped_column(String(512), nullable=True)
    proposed_secondary_keywords_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="semstorm_plan_items")
    promoted_item: Mapped[SiteSemstormPromotedItem] = relationship(back_populates="plan_item")
    brief_item: Mapped["SiteSemstormBriefItem | None"] = relationship(
        back_populates="plan_item",
        cascade="all, delete-orphan",
        uselist=False,
    )


class SiteSemstormBriefItem(Base):
    __tablename__ = "site_semstorm_brief_items"
    __table_args__ = (
        UniqueConstraint(
            "plan_item_id",
            name="uq_site_semstorm_brief_items_plan_item_id",
        ),
        Index("ix_site_semstorm_brief_items_site_id", "site_id"),
        Index(
            "ix_site_semstorm_brief_items_site_id_state_status",
            "site_id",
            "state_status",
        ),
        Index(
            "ix_site_semstorm_brief_items_site_id_brief_type",
            "site_id",
            "brief_type",
        ),
        Index(
            "ix_site_semstorm_brief_items_site_id_search_intent",
            "site_id",
            "search_intent",
        ),
        Index(
            "ix_site_semstorm_brief_items_site_id_updated_at",
            "site_id",
            "updated_at",
        ),
        Index(
            "ix_site_semstorm_brief_items_site_id_assignee",
            "site_id",
            "assignee",
        ),
        Index(
            "ix_site_semstorm_brief_items_site_id_impl_status",
            "site_id",
            "implementation_status",
        ),
        Index(
            "ix_site_semstorm_brief_items_site_id_implemented_at",
            "site_id",
            "implemented_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    plan_item_id: Mapped[int] = mapped_column(
        ForeignKey("site_semstorm_plan_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    state_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    brief_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    brief_type: Mapped[str] = mapped_column(String(32), nullable=False, default="new_page")
    primary_keyword: Mapped[str] = mapped_column(String(512), nullable=False)
    secondary_keywords_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    search_intent: Mapped[str] = mapped_column(String(32), nullable=False, default="mixed")
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    execution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    implementation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    implemented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evaluation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_outcome_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    implementation_url_override: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    target_url_existing: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    proposed_url_slug: Mapped[str | None] = mapped_column(String(512), nullable=True)
    recommended_page_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_h1: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    angle_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    internal_link_targets_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    source_notes_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="semstorm_brief_items")
    plan_item: Mapped[SiteSemstormPlanItem] = relationship(back_populates="brief_item")
    enrichment_runs: Mapped[list["SiteSemstormBriefEnrichmentRun"]] = relationship(
        back_populates="brief_item",
        cascade="all, delete-orphan",
    )


class SiteSemstormBriefEnrichmentRun(Base):
    __tablename__ = "site_semstorm_brief_enrichment_runs"
    __table_args__ = (
        Index("ix_site_semstorm_brief_enrichment_runs_site_id", "site_id"),
        Index(
            "ix_site_semstorm_brief_enrichment_runs_brief_item_id",
            "brief_item_id",
        ),
        Index(
            "ix_site_semstorm_brief_enrichment_runs_site_id_status",
            "site_id",
            "status",
        ),
        Index(
            "ix_site_semstorm_brief_enrichment_runs_site_id_created_at",
            "site_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    brief_item_id: Mapped[int] = mapped_column(
        ForeignKey("site_semstorm_brief_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    engine_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="mock")
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message_safe: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="semstorm_brief_enrichment_runs")
    brief_item: Mapped[SiteSemstormBriefItem] = relationship(back_populates="enrichment_runs")


class SiteCompetitor(Base):
    __tablename__ = "site_competitors"
    __table_args__ = (
        UniqueConstraint("site_id", "domain", name="uq_site_competitors_site_id_domain"),
        Index("ix_site_competitors_site_id", "site_id"),
        Index("ix_site_competitors_domain", "domain"),
        Index("ix_site_competitors_site_id_is_active", "site_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    root_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_run_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    last_sync_stage: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    last_sync_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_processed_urls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_sync_url_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=400)
    last_sync_processed_extraction_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_sync_total_extractable_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_sync_summary_json: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="competitors")
    sync_runs: Mapped[list["SiteCompetitorSyncRun"]] = relationship(
        back_populates="competitor",
        cascade="all, delete-orphan",
    )
    pages: Mapped[list["SiteCompetitorPage"]] = relationship(back_populates="competitor", cascade="all, delete-orphan")
    extractions: Mapped[list["SiteCompetitorPageExtraction"]] = relationship(
        back_populates="competitor",
        cascade="all, delete-orphan",
    )
    semantic_candidates: Mapped[list["SiteCompetitorSemanticCandidate"]] = relationship(
        back_populates="competitor",
        cascade="all, delete-orphan",
    )
    semantic_runs: Mapped[list["SiteCompetitorSemanticRun"]] = relationship(
        back_populates="competitor",
        cascade="all, delete-orphan",
    )
    semantic_decisions: Mapped[list["SiteCompetitorSemanticDecision"]] = relationship(
        back_populates="source_competitor",
        cascade="all, delete-orphan",
        foreign_keys="SiteCompetitorSemanticDecision.source_competitor_id",
    )


class SiteCompetitorSyncRun(Base):
    __tablename__ = "site_competitor_sync_runs"
    __table_args__ = (
        UniqueConstraint("competitor_id", "run_id", name="uq_site_competitor_sync_runs_competitor_id_run_id"),
        Index("ix_site_competitor_sync_runs_site_id", "site_id"),
        Index("ix_site_competitor_sync_runs_competitor_id", "competitor_id"),
        Index("ix_site_competitor_sync_runs_status", "status"),
        Index("ix_site_competitor_sync_runs_lease_expires_at", "lease_expires_at"),
        Index("ix_site_competitor_sync_runs_competitor_id_created_at", "competitor_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("site_competitors.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual_single")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message_safe: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    retry_of_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_urls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    url_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_extraction_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_extractable_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    competitor: Mapped[SiteCompetitor] = relationship(back_populates="sync_runs")


class SiteCompetitorPage(Base):
    __tablename__ = "site_competitor_pages"
    __table_args__ = (
        UniqueConstraint("competitor_id", "normalized_url", name="uq_site_competitor_pages_competitor_id_normalized_url"),
        Index("ix_site_competitor_pages_site_id", "site_id"),
        Index("ix_site_competitor_pages_competitor_id", "competitor_id"),
        Index("ix_site_competitor_pages_normalized_url", "normalized_url"),
        Index("ix_site_competitor_pages_content_text_hash", "content_text_hash"),
        Index("ix_site_competitor_pages_competitor_id_semantic_eligible", "competitor_id", "semantic_eligible"),
        Index("ix_site_competitor_pages_semantic_input_hash", "semantic_input_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("site_competitors.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    final_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    visible_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_type: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    page_bucket: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    page_type_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fetch_diagnostics_json: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    semantic_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    semantic_exclusion_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    semantic_input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    semantic_last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    competitor: Mapped[SiteCompetitor] = relationship(back_populates="pages")
    extractions: Mapped[list["SiteCompetitorPageExtraction"]] = relationship(
        back_populates="competitor_page",
        cascade="all, delete-orphan",
    )
    semantic_candidates: Mapped[list["SiteCompetitorSemanticCandidate"]] = relationship(
        back_populates="competitor_page",
        cascade="all, delete-orphan",
    )


class SiteCompetitorSemanticCandidate(Base):
    __tablename__ = "site_competitor_semantic_candidates"
    __table_args__ = (
        UniqueConstraint(
            "competitor_page_id",
            "semantic_input_hash",
            name="uq_site_competitor_semantic_candidates_page_id_hash",
        ),
        Index("ix_site_competitor_semantic_candidates_site_id", "site_id"),
        Index("ix_site_competitor_semantic_candidates_competitor_id", "competitor_id"),
        Index("ix_site_competitor_semantic_candidates_competitor_page_id", "competitor_page_id"),
        Index("ix_site_competitor_semantic_candidates_site_id_current", "site_id", "current"),
        Index("ix_site_competitor_semantic_candidates_raw_topic_key", "raw_topic_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("site_competitors.id", ondelete="CASCADE"), nullable=False)
    competitor_page_id: Mapped[int] = mapped_column(
        ForeignKey("site_competitor_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    semantic_input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_topic_key: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_topic_label: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_terms_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    page_type: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    page_bucket: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    competitor: Mapped[SiteCompetitor] = relationship(back_populates="semantic_candidates")
    competitor_page: Mapped[SiteCompetitorPage] = relationship(back_populates="semantic_candidates")
    source_semantic_decisions: Mapped[list["SiteCompetitorSemanticDecision"]] = relationship(
        back_populates="source_candidate",
        cascade="all, delete-orphan",
        foreign_keys="SiteCompetitorSemanticDecision.source_candidate_id",
    )
    target_semantic_decisions: Mapped[list["SiteCompetitorSemanticDecision"]] = relationship(
        back_populates="target_candidate",
        foreign_keys="SiteCompetitorSemanticDecision.target_candidate_id",
    )


class SiteCompetitorSemanticRun(Base):
    __tablename__ = "site_competitor_semantic_runs"
    __table_args__ = (
        UniqueConstraint(
            "competitor_id",
            "run_id",
            name="uq_site_competitor_semantic_runs_competitor_id_run_id",
        ),
        Index("ix_site_competitor_semantic_runs_site_id", "site_id"),
        Index("ix_site_competitor_semantic_runs_competitor_id", "competitor_id"),
        Index("ix_site_competitor_semantic_runs_status", "status"),
        Index("ix_site_competitor_semantic_runs_lease_expires_at", "lease_expires_at"),
        Index(
            "ix_site_competitor_semantic_runs_competitor_id_created_at",
            "competitor_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("site_competitors.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual_incremental")
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="incremental")
    active_crawl_id: Mapped[int | None] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message_safe: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_candidate_ids_json: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    summary_json: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    competitor: Mapped[SiteCompetitor] = relationship(back_populates="semantic_runs")


class SiteCompetitorSemanticDecision(Base):
    __tablename__ = "site_competitor_semantic_decisions"
    __table_args__ = (
        UniqueConstraint(
            "decision_key",
            name="uq_site_competitor_semantic_decisions_decision_key",
        ),
        Index("ix_site_competitor_semantic_decisions_site_id", "site_id"),
        Index(
            "ix_site_competitor_semantic_decisions_source_competitor_id",
            "source_competitor_id",
        ),
        Index(
            "ix_site_competitor_semantic_decisions_source_candidate_id",
            "source_candidate_id",
        ),
        Index(
            "ix_site_competitor_semantic_decisions_target_candidate_id",
            "target_candidate_id",
        ),
        Index(
            "ix_site_competitor_semantic_decisions_decision_type",
            "decision_type",
        ),
        Index(
            "ix_site_competitor_semantic_decisions_active_crawl_id",
            "active_crawl_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    source_competitor_id: Mapped[int] = mapped_column(
        ForeignKey("site_competitors.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_candidate_id: Mapped[int] = mapped_column(
        ForeignKey("site_competitor_semantic_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    decision_type: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_semantic_input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    target_competitor_id: Mapped[int | None] = mapped_column(
        ForeignKey("site_competitors.id", ondelete="CASCADE"),
        nullable=True,
    )
    target_candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("site_competitor_semantic_candidates.id", ondelete="CASCADE"),
        nullable=True,
    )
    target_semantic_input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    own_page_id: Mapped[int | None] = mapped_column(
        ForeignKey("pages.id", ondelete="SET NULL"),
        nullable=True,
    )
    active_crawl_id: Mapped[int | None] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    own_page_semantic_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    candidate_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidate_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision_label: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_topic_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    debug_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    debug_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    source_competitor: Mapped[SiteCompetitor] = relationship(
        back_populates="semantic_decisions",
        foreign_keys=[source_competitor_id],
    )
    source_candidate: Mapped[SiteCompetitorSemanticCandidate] = relationship(
        back_populates="source_semantic_decisions",
        foreign_keys=[source_candidate_id],
    )
    target_candidate: Mapped[SiteCompetitorSemanticCandidate | None] = relationship(
        back_populates="target_semantic_decisions",
        foreign_keys=[target_candidate_id],
    )


class SiteCompetitiveGapClusterState(Base):
    __tablename__ = "site_competitive_gap_cluster_states"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "active_crawl_id",
            "semantic_cluster_key",
            name="uq_site_competitive_gap_cluster_states_site_crawl_cluster",
        ),
        Index("ix_site_competitive_gap_cluster_states_site_id", "site_id"),
        Index("ix_site_competitive_gap_cluster_states_active_crawl_id", "active_crawl_id"),
        Index("ix_site_competitive_gap_cluster_states_cluster_key", "semantic_cluster_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    active_crawl_id: Mapped[int | None] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    semantic_cluster_key: Mapped[str] = mapped_column(String(64), nullable=False)
    topic_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_topic_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_candidate_ids_json: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    competitor_ids_json: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    cluster_state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    coverage_state_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cluster_summary_json: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    coverage_state_json: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )


class SiteContentGapCandidate(Base):
    __tablename__ = "site_content_gap_candidates"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "basis_crawl_job_id",
            "candidate_key",
            "candidate_input_hash",
            name="uq_site_content_gap_candidates_site_crawl_key_hash",
        ),
        Index("ix_site_content_gap_candidates_site_id", "site_id"),
        Index("ix_site_content_gap_candidates_basis_crawl_job_id", "basis_crawl_job_id"),
        Index(
            "ix_site_content_gap_candidates_site_crawl_current",
            "site_id",
            "basis_crawl_job_id",
            "current",
        ),
        Index(
            "ix_site_content_gap_candidates_site_crawl_status",
            "site_id",
            "basis_crawl_job_id",
            "status",
        ),
        Index(
            "ix_site_content_gap_candidates_site_crawl_topic_key",
            "site_id",
            "basis_crawl_job_id",
            "normalized_topic_key",
        ),
        Index(
            "ix_site_content_gap_candidates_site_crawl_candidate_key",
            "site_id",
            "basis_crawl_job_id",
            "candidate_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    basis_crawl_job_id: Mapped[int] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_key: Mapped[str] = mapped_column(String(96), nullable=False)
    candidate_input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    generation_version: Mapped[str] = mapped_column(String(32), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_topic_key: Mapped[str] = mapped_column(String(255), nullable=False)
    original_topic_label: Mapped[str] = mapped_column(String(255), nullable=False)
    original_phrase: Mapped[str] = mapped_column(String(255), nullable=False)
    gap_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_cluster_key: Mapped[str] = mapped_column(String(96), nullable=False)
    source_cluster_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_competitor_ids_json: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    source_competitor_page_ids_json: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    competitor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    own_coverage_hint: Mapped[str] = mapped_column(String(64), nullable=False)
    deterministic_priority_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rationale_summary: Mapped[str] = mapped_column(Text, nullable=False)
    signals_json: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    review_needed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    review_visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="visible")
    first_generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="content_gap_candidates")
    basis_crawl_job: Mapped[CrawlJob] = relationship(back_populates="content_gap_candidates")
    content_gap_items: Mapped[list["SiteContentGapItem"]] = relationship(
        back_populates="source_candidate",
        cascade="all, delete-orphan",
    )


class SiteContentGapReviewRun(Base):
    __tablename__ = "site_content_gap_review_runs"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "run_id",
            name="uq_site_content_gap_review_runs_site_id_run_id",
        ),
        Index("ix_site_content_gap_review_runs_site_id", "site_id"),
        Index("ix_site_content_gap_review_runs_basis_crawl_job_id", "basis_crawl_job_id"),
        Index("ix_site_content_gap_review_runs_status", "status"),
        Index("ix_site_content_gap_review_runs_lease_expires_at", "lease_expires_at"),
        Index(
            "ix_site_content_gap_review_runs_site_crawl_created_at",
            "site_id",
            "basis_crawl_job_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    basis_crawl_job_id: Mapped[int] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="all_current")
    selected_candidate_ids_json: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidate_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_generation_version: Mapped[str] = mapped_column(String(32), nullable=False)
    own_context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    gsc_context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context_summary_json: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    output_language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    batch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_batch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message_safe: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_of_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="content_gap_review_runs")
    basis_crawl_job: Mapped[CrawlJob] = relationship(back_populates="content_gap_review_runs")
    items: Mapped[list["SiteContentGapItem"]] = relationship(
        back_populates="review_run",
        cascade="all, delete-orphan",
    )


class SiteContentGapItem(Base):
    __tablename__ = "site_content_gap_items"
    __table_args__ = (
        UniqueConstraint(
            "review_run_id",
            "source_candidate_id",
            name="uq_site_content_gap_items_run_candidate",
        ),
        Index("ix_site_content_gap_items_site_id", "site_id"),
        Index("ix_site_content_gap_items_basis_crawl_job_id", "basis_crawl_job_id"),
        Index("ix_site_content_gap_items_review_run_id", "review_run_id"),
        Index("ix_site_content_gap_items_source_candidate_id", "source_candidate_id"),
        Index("ix_site_content_gap_items_item_status", "item_status"),
        Index(
            "ix_site_content_gap_items_site_crawl_visible",
            "site_id",
            "basis_crawl_job_id",
            "visible_in_results",
        ),
        Index(
            "ix_site_content_gap_items_site_crawl_group",
            "site_id",
            "basis_crawl_job_id",
            "review_group_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    basis_crawl_job_id: Mapped[int] = mapped_column(
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    review_run_id: Mapped[int] = mapped_column(
        ForeignKey("site_content_gap_review_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_candidate_id: Mapped[int] = mapped_column(
        ForeignKey("site_content_gap_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_candidate_key: Mapped[str] = mapped_column(String(96), nullable=False)
    source_candidate_input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    item_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    decision_action: Mapped[str] = mapped_column(String(32), nullable=False)
    display_state: Mapped[str] = mapped_column(String(32), nullable=False, default="visible")
    review_group_key: Mapped[str] = mapped_column(String(96), nullable=False)
    group_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    original_phrase: Mapped[str] = mapped_column(String(255), nullable=False)
    original_topic_label: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewed_phrase: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_topic_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_normalized_topic_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_gap_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fit_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    decision_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    merge_target_candidate_key: Mapped[str | None] = mapped_column(String(96), nullable=True)
    merge_target_phrase: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remove_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remove_reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    rewrite_reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    own_site_alignment_json: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
    )
    gsc_support_json: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
    )
    competitor_evidence_json: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
    )
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    response_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_decision_json: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
    )
    visible_in_results: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="content_gap_items")
    basis_crawl_job: Mapped[CrawlJob] = relationship(back_populates="content_gap_items")
    review_run: Mapped[SiteContentGapReviewRun] = relationship(back_populates="items")
    source_candidate: Mapped[SiteContentGapCandidate] = relationship(back_populates="content_gap_items")


class SiteCompetitorPageExtraction(Base):
    __tablename__ = "site_competitor_page_extractions"
    __table_args__ = (
        Index("ix_site_competitor_page_extractions_site_id", "site_id"),
        Index("ix_site_competitor_page_extractions_competitor_id", "competitor_id"),
        Index("ix_site_competitor_page_extractions_competitor_page_id", "competitor_page_id"),
        Index("ix_site_competitor_page_extractions_topic_key", "topic_key"),
        Index("ix_site_competitor_page_extractions_site_id_topic_key", "site_id", "topic_key"),
        Index("ix_site_competitor_page_extractions_semantic_input_hash", "semantic_input_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("site_competitors.id", ondelete="CASCADE"), nullable=False)
    competitor_page_id: Mapped[int] = mapped_column(
        ForeignKey("site_competitor_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_hash_at_extraction: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    semantic_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    semantic_input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    topic_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic_key: Mapped[str] = mapped_column(String(255), nullable=False)
    search_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_format: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_snippets_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    semantic_card_json: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
    )
    chunk_summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=True,
    )
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    competitor: Mapped[SiteCompetitor] = relationship(back_populates="extractions")
    competitor_page: Mapped[SiteCompetitorPage] = relationship(back_populates="extractions")


class CrawlPageSemanticProfile(Base):
    __tablename__ = "crawl_page_semantic_profiles"
    __table_args__ = (
        UniqueConstraint(
            "page_id",
            "semantic_input_hash",
            name="uq_crawl_page_semantic_profiles_page_id_hash",
        ),
        Index("ix_crawl_page_semantic_profiles_site_id", "site_id"),
        Index("ix_crawl_page_semantic_profiles_crawl_job_id", "crawl_job_id"),
        Index("ix_crawl_page_semantic_profiles_page_id", "page_id"),
        Index(
            "ix_crawl_page_semantic_profiles_crawl_job_id_current",
            "crawl_job_id",
            "current",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    crawl_job_id: Mapped[int] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    semantic_input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    semantic_version: Mapped[str] = mapped_column(String(64), nullable=False)
    llm_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    semantic_card_json: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    crawl_job: Mapped[CrawlJob] = relationship(back_populates="semantic_profiles")
    page: Mapped[Page] = relationship(back_populates="semantic_profiles")


class GscProperty(Base):
    __tablename__ = "gsc_properties"
    __table_args__ = (
        UniqueConstraint("site_id", name="uq_gsc_properties_site_id"),
        Index("ix_gsc_properties_property_uri", "property_uri"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    property_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    permission_level: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    site: Mapped[Site] = relationship(back_populates="gsc_property")
    url_metrics: Mapped[list["GscUrlMetric"]] = relationship(back_populates="gsc_property")
    top_queries: Mapped[list["GscTopQuery"]] = relationship(back_populates="gsc_property")


class GscUrlMetric(Base):
    __tablename__ = "gsc_url_metrics"
    __table_args__ = (
        UniqueConstraint(
            "crawl_job_id",
            "normalized_url",
            "date_range_label",
            name="uq_gsc_url_metrics_job_url_range",
        ),
        Index("ix_gsc_url_metrics_job_range", "crawl_job_id", "date_range_label"),
        Index("ix_gsc_url_metrics_page_range", "page_id", "date_range_label"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gsc_property_id: Mapped[int] = mapped_column(ForeignKey("gsc_properties.id", ondelete="CASCADE"), nullable=False)
    crawl_job_id: Mapped[int] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[int | None] = mapped_column(ForeignKey("pages.id", ondelete="SET NULL"), nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    date_range_label: Mapped[str] = mapped_column(String(32), nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    position: Mapped[float | None] = mapped_column(Float, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    gsc_property: Mapped[GscProperty] = relationship(back_populates="url_metrics")
    crawl_job: Mapped[CrawlJob] = relationship(back_populates="gsc_url_metrics")
    page: Mapped[Page | None] = relationship(back_populates="gsc_url_metrics")


class GscTopQuery(Base):
    __tablename__ = "gsc_top_queries"
    __table_args__ = (
        UniqueConstraint(
            "crawl_job_id",
            "normalized_url",
            "date_range_label",
            "query",
            name="uq_gsc_top_queries_job_url_range_query",
        ),
        Index("ix_gsc_top_queries_job_range", "crawl_job_id", "date_range_label"),
        Index("ix_gsc_top_queries_page_range", "page_id", "date_range_label"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gsc_property_id: Mapped[int] = mapped_column(ForeignKey("gsc_properties.id", ondelete="CASCADE"), nullable=False)
    crawl_job_id: Mapped[int] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[int | None] = mapped_column(ForeignKey("pages.id", ondelete="SET NULL"), nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    date_range_label: Mapped[str] = mapped_column(String(32), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    position: Mapped[float | None] = mapped_column(Float, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    gsc_property: Mapped[GscProperty] = relationship(back_populates="top_queries")
    crawl_job: Mapped[CrawlJob] = relationship(back_populates="gsc_top_queries")
    page: Mapped[Page | None] = relationship(back_populates="gsc_top_queries")


def _sync_site_competitor_page_text_fields(target: SiteCompetitorPage) -> None:
    prepared = prepare_visible_text(target.visible_text)
    target.visible_text = prepared.stored_text
    target.content_text_hash = prepared.content_hash
    diagnostics = dict(target.fetch_diagnostics_json or {})
    diagnostics["visible_text_truncated"] = prepared.truncated
    target.fetch_diagnostics_json = diagnostics


@event.listens_for(SiteCompetitorPage, "before_insert")
def _before_insert_site_competitor_page(_mapper: Any, _connection: Any, target: SiteCompetitorPage) -> None:
    _sync_site_competitor_page_text_fields(target)


@event.listens_for(SiteCompetitorPage, "before_update")
def _before_update_site_competitor_page(_mapper: Any, _connection: Any, target: SiteCompetitorPage) -> None:
    _sync_site_competitor_page_text_fields(target)
