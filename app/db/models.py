from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    root_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    crawl_jobs: Mapped[list["CrawlJob"]] = relationship(back_populates="site", cascade="all, delete-orphan")


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


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("crawl_job_id", "normalized_url", name="uq_pages_crawl_job_id_normalized_url"),
        Index("ix_pages_crawl_job_id", "crawl_job_id"),
        Index("ix_pages_status_code", "status_code"),
        Index("ix_pages_is_internal", "is_internal"),
        Index("ix_pages_depth", "depth"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crawl_job_id: Mapped[int] = mapped_column(ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    final_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    robots_meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    crawl_job: Mapped[CrawlJob] = relationship(back_populates="pages")
    outgoing_links: Mapped[list["Link"]] = relationship(back_populates="source_page", cascade="all, delete-orphan")


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
