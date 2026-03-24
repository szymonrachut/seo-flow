from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from time import monotonic
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlsplit
from urllib.request import Request, urlopen

from scrapy.http import Headers, HtmlResponse
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crawler.extraction.page_extractor import ExtractedPageData, extract_page_data
from app.crawler.normalization.urls import extract_host, normalize_url
from app.db.models import Site, SiteCompetitor, SiteCompetitorPage, SiteCompetitorPageExtraction, utcnow
from app.db.session import SessionLocal
from app.services import (
    content_gap_candidate_service,
    competitive_gap_extraction_service,
    competitive_gap_topic_quality_service,
    competitive_gap_page_diagnostics,
    competitive_gap_semantic_rules,
    competitive_gap_semantic_service,
    competitive_gap_sync_run_service,
    crawl_job_service,
    page_taxonomy_service,
    site_competitor_service,
)
from app.services.seo_analysis import has_noindex_directive


COMPETITOR_SYNC_MAX_URLS = 400
COMPETITOR_SYNC_MAX_DEPTH = 4
SYNCABLE_STATUSES = {"idle", "done", "failed", "not_started"}
SYNC_IN_PROGRESS_STATUSES = {"queued", "running"}
SYNC_STAGES = {"idle", "queued", "crawling", "extracting", "done", "failed"}
SKIP_PATH_TOKENS = {
    "login",
    "logowanie",
    "account",
    "konto",
    "my-account",
    "cart",
    "koszyk",
    "checkout",
    "search",
    "szukaj",
    "tag",
    "tags",
    "author",
    "feed",
    "admin",
    "wp-admin",
    "wp-json",
}
SKIP_QUERY_KEYS = {
    "q",
    "query",
    "search",
    "s",
    "filter",
    "filters",
    "facet",
    "facets",
    "sort",
    "order",
    "dir",
    "page",
    "p",
    "color",
    "size",
    "brand",
    "price",
    "min_price",
    "max_price",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
}
SYNC_SUMMARY_SAMPLE_LIMIT = 3
logger = logging.getLogger(__name__)


class CompetitiveGapSyncServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "sync_failed") -> None:
        super().__init__(message)
        self.code = code


class CompetitiveGapSyncCancelled(CompetitiveGapSyncServiceError):
    pass


@dataclass(slots=True)
class FetchedCompetitorDocument:
    requested_url: str
    final_url: str
    normalized_url: str
    status_code: int
    headers: dict[str, str]
    body: bytes
    fetched_at: object
    response_time_ms: int | None


@dataclass(slots=True)
class FetchCompetitorResult:
    document: FetchedCompetitorDocument | None = None
    skip_reason: str | None = None


@dataclass(slots=True)
class CrawledCompetitorPage:
    requested_url: str
    normalized_url: str
    final_url: str
    status_code: int
    content_type: str | None
    fetched_at: object
    extracted_data: ExtractedPageData


@dataclass(slots=True)
class CrawledCompetitorPagesResult:
    pages: list[CrawledCompetitorPage]
    processed_urls: int


@dataclass(slots=True)
class PersistedCompetitorPagesResult:
    saved_page_ids: list[int]
    processed_urls: int


@dataclass(slots=True)
class CompetitorSyncResult:
    pages_saved: int
    extraction_created: int
    extraction_skipped: int
    extraction_failed: int
    processed_urls: int
    processed_extraction_pages: int
    total_extractable_pages: int
    summary_payload: dict[str, Any]
    extracted_page_ids: list[int] = field(default_factory=list)
    semantic_changed_candidate_ids: list[int] = field(default_factory=list)
    content_gap_candidates_generated: int = 0
    content_gap_candidates_reused: int = 0
    content_gap_candidates_superseded: int = 0
    content_gap_candidates_invalidated: int = 0


@dataclass(slots=True)
class SyncSummaryAccumulator:
    visited_urls_count: int = 0
    stored_pages_count: int = 0
    extracted_pages_count: int = 0
    skipped_non_html_count: int = 0
    skipped_non_indexable_count: int = 0
    skipped_out_of_scope_count: int = 0
    skipped_filtered_count: int = 0
    skipped_low_value_count: int = 0
    skipped_duplicate_url_count: int = 0
    skipped_fetch_error_count: int = 0
    extraction_created_count: int = 0
    extraction_skipped_unchanged_count: int = 0
    extraction_failed_count: int = 0
    sample_urls_by_reason: dict[str, list[str]] = field(default_factory=dict)
    counted_skip_urls_by_reason: dict[str, set[str]] = field(default_factory=dict, repr=False)

    def record_skip(self, *, reason: str, url: str | None = None) -> None:
        field_name = {
            "non_html": "skipped_non_html_count",
            "non_indexable": "skipped_non_indexable_count",
            "out_of_scope": "skipped_out_of_scope_count",
            "filtered": "skipped_filtered_count",
            "low_value": "skipped_low_value_count",
            "weak_contact": "skipped_low_value_count",
            "weak_about": "skipped_low_value_count",
            "weak_location": "skipped_low_value_count",
            "weak_certificate": "skipped_low_value_count",
            "weak_gallery": "skipped_low_value_count",
            "weak_partner_brand": "skipped_low_value_count",
            "weak_support": "skipped_low_value_count",
            "weak_low_strength": "skipped_low_value_count",
            "thin": "skipped_low_value_count",
            "contact": "skipped_low_value_count",
            "utility_page": "skipped_low_value_count",
            "duplicate_url": "skipped_duplicate_url_count",
            "fetch_error": "skipped_fetch_error_count",
        }.get(reason)
        if field_name is None:
            return
        cleaned_url = str(url).strip() if url else ""
        if cleaned_url:
            counted_urls = self.counted_skip_urls_by_reason.setdefault(reason, set())
            if cleaned_url in counted_urls:
                return
            counted_urls.add(cleaned_url)
        setattr(self, field_name, getattr(self, field_name) + 1)
        if not cleaned_url:
            return
        bucket = self.sample_urls_by_reason.setdefault(reason, [])
        if cleaned_url and cleaned_url not in bucket and len(bucket) < SYNC_SUMMARY_SAMPLE_LIMIT:
            bucket.append(cleaned_url)

    def to_payload(self) -> dict[str, Any]:
        payload = site_competitor_service.build_empty_sync_summary_payload()
        payload.update(
            {
                "visited_urls_count": self.visited_urls_count,
                "stored_pages_count": self.stored_pages_count,
                "extracted_pages_count": self.extracted_pages_count,
                "skipped_non_html_count": self.skipped_non_html_count,
                "skipped_non_indexable_count": self.skipped_non_indexable_count,
                "skipped_out_of_scope_count": self.skipped_out_of_scope_count,
                "skipped_filtered_count": self.skipped_filtered_count,
                "skipped_low_value_count": self.skipped_low_value_count,
                "skipped_duplicate_url_count": self.skipped_duplicate_url_count,
                "skipped_fetch_error_count": self.skipped_fetch_error_count,
                "extraction_created_count": self.extraction_created_count,
                "extraction_skipped_unchanged_count": self.extraction_skipped_unchanged_count,
                "extraction_failed_count": self.extraction_failed_count,
                "sample_urls_by_reason": {
                    reason: list(values[:SYNC_SUMMARY_SAMPLE_LIMIT])
                    for reason, values in self.sample_urls_by_reason.items()
                    if values
                },
            }
        )
        payload["skipped_urls_count"] = (
            payload["skipped_non_html_count"]
            + payload["skipped_non_indexable_count"]
            + payload["skipped_out_of_scope_count"]
            + payload["skipped_filtered_count"]
            + payload["skipped_low_value_count"]
            + payload["skipped_duplicate_url_count"]
            + payload["skipped_fetch_error_count"]
        )
        return payload


FetchDocumentFn = Callable[[str], FetchCompetitorResult | FetchedCompetitorDocument | None]
ExtractCompetitorPageFn = Callable[[SiteCompetitorPage], competitive_gap_extraction_service.CompetitorExtractionResult]
CrawlProgressFn = Callable[[int], None]
ShouldContinueFn = Callable[[], bool]


def queue_site_competitor_sync(session: Session, site_id: int, competitor_id: int) -> dict[str, object]:
    competitor = _get_competitor_or_raise(session, site_id, competitor_id)
    try:
        competitive_gap_sync_run_service.queue_sync_run(
            session,
            site_id=site_id,
            competitor_id=competitor_id,
            trigger_source="manual_single",
            url_limit=COMPETITOR_SYNC_MAX_URLS,
        )
    except competitive_gap_sync_run_service.CompetitiveGapSyncRunServiceError as exc:
        raise CompetitiveGapSyncServiceError(str(exc), code=exc.code) from exc

    session.flush()
    payload = site_competitor_service.get_site_competitor_payload(session, site_id, competitor_id)
    return payload


def queue_all_site_competitor_syncs(session: Session, site_id: int) -> dict[str, object]:
    site = crawl_job_service.get_site(session, site_id)
    if site is None:
        raise CompetitiveGapSyncServiceError(f"Site {site_id} not found.")

    competitors = session.scalars(
        select(SiteCompetitor)
        .where(SiteCompetitor.site_id == site_id, SiteCompetitor.is_active.is_(True))
        .order_by(SiteCompetitor.id.asc())
    ).all()
    if not competitors:
        raise CompetitiveGapSyncServiceError(f"Site {site_id} has no active competitors to sync.")

    queued_ids: list[int] = []
    already_running_ids: list[int] = []
    queued_runs: list[dict[str, Any]] = []
    for competitor in competitors:
        try:
            queued_run = competitive_gap_sync_run_service.queue_sync_run(
                session,
                site_id=site_id,
                competitor_id=competitor.id,
                trigger_source="manual_all",
                url_limit=COMPETITOR_SYNC_MAX_URLS,
            )
        except competitive_gap_sync_run_service.CompetitiveGapSyncRunServiceError as exc:
            if exc.code == "already_running":
                already_running_ids.append(competitor.id)
                continue
            raise CompetitiveGapSyncServiceError(str(exc), code=exc.code) from exc
        queued_ids.append(competitor.id)
        queued_runs.append(queued_run)

    if not queued_ids:
        raise CompetitiveGapSyncServiceError(
            "All active competitors are already queued or running.",
            code="already_running",
        )

    session.flush()
    return {
        "site_id": site_id,
        "queued_competitor_ids": queued_ids,
        "already_running_competitor_ids": already_running_ids,
        "queued_count": len(queued_ids),
        "queued_runs": queued_runs,
    }


def reset_site_competitor_sync(session: Session, site_id: int, competitor_id: int) -> dict[str, object]:
    _get_competitor_or_raise(session, site_id, competitor_id)
    try:
        competitive_gap_sync_run_service.reset_sync_runtime(
            session,
            site_id=site_id,
            competitor_id=competitor_id,
            url_limit=COMPETITOR_SYNC_MAX_URLS,
        )
    except competitive_gap_sync_run_service.CompetitiveGapSyncRunServiceError as exc:
        raise CompetitiveGapSyncServiceError(str(exc), code=exc.code) from exc
    session.flush()
    return site_competitor_service.get_site_competitor_payload(session, site_id, competitor_id)


def retry_site_competitor_sync(session: Session, site_id: int, competitor_id: int) -> dict[str, object]:
    competitor = _get_competitor_or_raise(session, site_id, competitor_id)
    try:
        competitive_gap_sync_run_service.retry_last_sync_run(
            session,
            site_id=site_id,
            competitor_id=competitor_id,
            trigger_source="retry",
            url_limit=COMPETITOR_SYNC_MAX_URLS,
        )
    except competitive_gap_sync_run_service.CompetitiveGapSyncRunServiceError as exc:
        raise CompetitiveGapSyncServiceError(str(exc), code=exc.code) from exc
    session.flush()
    payload = site_competitor_service.get_site_competitor_payload(session, site_id, competitor_id)
    logger.info(
        "competitor_sync.retry_queued site_id=%s competitor_id=%s run_id=%s",
        site_id,
        competitor_id,
        payload["last_sync_run_id"],
    )
    return payload


def list_site_competitor_sync_runs(
    session: Session,
    site_id: int,
    competitor_id: int,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    _get_competitor_or_raise(session, site_id, competitor_id)
    try:
        return competitive_gap_sync_run_service.list_sync_runs(
            session,
            site_id=site_id,
            competitor_id=competitor_id,
            limit=limit,
        )
    except competitive_gap_sync_run_service.CompetitiveGapSyncRunServiceError as exc:
        raise CompetitiveGapSyncServiceError(str(exc), code=exc.code) from exc


def run_site_competitor_sync_task(
    site_id: int,
    competitor_id: int,
    run_id: int,
    output_language: str = "en",
) -> None:
    with SessionLocal() as session:
        if not _mark_competitor_sync_running(session, site_id, competitor_id, run_id):
            return

        try:
            result = run_site_competitor_sync(
                session,
                site_id,
                competitor_id,
                sync_run_id=run_id,
                persist_sync_progress=True,
                checkpoint_after_save=True,
                checkpoint_each_extraction=True,
                output_language=output_language,
            )
        except CompetitiveGapSyncCancelled:
            session.rollback()
            return
        except Exception as exc:  # pragma: no cover - background task fallback
            session.rollback()
            error_code, error_message = _normalize_sync_error(exc)
            _mark_competitor_sync_failed(
                site_id,
                competitor_id,
                run_id,
                error=error_message,
                error_code=error_code,
            )
            return

    _mark_competitor_sync_done(site_id, competitor_id, run_id, result=result)
    logger.info(
        "competitor_sync.semantic_auto_review_not_started site_id=%s competitor_id=%s generated=%s reused=%s superseded=%s invalidated=%s",
        site_id,
        competitor_id,
        result.content_gap_candidates_generated,
        result.content_gap_candidates_reused,
        result.content_gap_candidates_superseded,
        result.content_gap_candidates_invalidated,
    )


def run_site_competitor_sync(
    session: Session,
    site_id: int,
    competitor_id: int,
    *,
    fetch_document: FetchDocumentFn | None = None,
    extract_competitor_page: ExtractCompetitorPageFn | None = None,
    sync_run_id: int | None = None,
    persist_sync_progress: bool = False,
    checkpoint_after_save: bool = False,
    checkpoint_each_extraction: bool = False,
    output_language: str = "en",
) -> CompetitorSyncResult:
    site = _get_site_or_raise(session, site_id)
    competitor = _get_competitor_or_raise(session, site_id, competitor_id)
    sync_summary = SyncSummaryAccumulator()
    semantic_changed_candidate_ids: list[int] = []

    crawl_kwargs: dict[str, object] = {
        "fetch_document": fetch_document or _fetch_competitor_document,
    }
    if persist_sync_progress:
        crawl_kwargs["progress_callback"] = lambda processed_urls: _persist_crawl_progress(
            session,
            competitor,
            processed_urls=processed_urls,
            summary_payload=sync_summary.to_payload(),
            sync_run_id=sync_run_id,
        )
    if sync_run_id is not None:
        crawl_kwargs["should_continue"] = lambda: _sync_run_is_current(session, competitor, sync_run_id)

    try:
        raw_crawl_result = _crawl_competitor_pages(
            competitor,
            sync_summary=sync_summary,
            **crawl_kwargs,
        )
    except TypeError as exc:
        if "sync_summary" not in str(exc):
            raise
        raw_crawl_result = _crawl_competitor_pages(
            competitor,
            **crawl_kwargs,
        )
    crawl_result = (
        raw_crawl_result
        if isinstance(raw_crawl_result, CrawledCompetitorPagesResult)
        else CrawledCompetitorPagesResult(
            pages=list(raw_crawl_result),
            processed_urls=len(raw_crawl_result),
        )
    )
    if not crawl_result.pages:
        raise CompetitiveGapSyncServiceError(
            f"No eligible HTML pages were discovered for competitor '{competitor.domain}'.",
            code="no_competitor_pages",
        )

    _ensure_current_sync_run(session, competitor, sync_run_id)

    persisted_pages = _persist_crawled_pages(
        session,
        site=site,
        competitor=competitor,
        crawled_pages=crawl_result.pages,
        processed_urls=crawl_result.processed_urls,
        sync_summary=sync_summary,
    )
    if not persisted_pages.saved_page_ids:
        raise CompetitiveGapSyncServiceError(
            f"Competitor '{competitor.domain}' returned pages, but none were eligible for content gap analysis.",
            code="no_competitor_pages",
        )

    try:
        semantic_refresh = competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
            session,
            site_id=site.id,
            competitor_id=competitor.id,
            page_ids=persisted_pages.saved_page_ids,
        )
        semantic_changed_candidate_ids = list(semantic_refresh.changed_candidate_ids or [])
    except Exception as exc:  # pragma: no cover - defensive fail-safe
        logger.warning(
            "competitor_sync.semantic_foundation_failed site_id=%s competitor_id=%s error=%s",
            site.id,
            competitor.id,
            exc,
        )

    if checkpoint_after_save and persist_sync_progress:
        _persist_extraction_progress(
            session,
            competitor,
            processed_urls=persisted_pages.processed_urls,
            processed_extraction_pages=0,
            total_extractable_pages=len(persisted_pages.saved_page_ids),
            summary_payload=sync_summary.to_payload(),
            sync_run_id=sync_run_id,
        )

    result = _extract_saved_pages(
        session,
        site=site,
        competitor=competitor,
        saved_page_ids=persisted_pages.saved_page_ids,
        processed_urls=persisted_pages.processed_urls,
        extract_competitor_page=extract_competitor_page or competitive_gap_extraction_service.extract_competitor_page,
        sync_run_id=sync_run_id,
        persist_sync_progress=persist_sync_progress,
        checkpoint_each_extraction=checkpoint_each_extraction,
        sync_summary=sync_summary,
        output_language=output_language,
    )
    if result.extracted_page_ids:
        try:
            post_extraction_refresh = competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
                session,
                site_id=site.id,
                competitor_id=competitor.id,
                page_ids=result.extracted_page_ids,
            )
            semantic_changed_candidate_ids.extend(post_extraction_refresh.changed_candidate_ids or [])
        except Exception as exc:  # pragma: no cover - defensive fail-safe
            logger.warning(
                "competitor_sync.post_extraction_semantic_refresh_failed site_id=%s competitor_id=%s error=%s",
                site.id,
                competitor.id,
                exc,
            )
    try:
        candidate_refresh = content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            site.id,
        )
        result.content_gap_candidates_generated = candidate_refresh.generated_count
        result.content_gap_candidates_reused = candidate_refresh.reused_count
        result.content_gap_candidates_superseded = candidate_refresh.superseded_count
        result.content_gap_candidates_invalidated = candidate_refresh.invalidated_count
        logger.info(
            "competitor_sync.content_gap_candidates_refreshed site_id=%s competitor_id=%s basis_crawl_job_id=%s generated=%s reused=%s superseded=%s invalidated=%s skipped_reason=%s",
            site.id,
            competitor.id,
            candidate_refresh.basis_crawl_job_id,
            candidate_refresh.generated_count,
            candidate_refresh.reused_count,
            candidate_refresh.superseded_count,
            candidate_refresh.invalidated_count,
            candidate_refresh.skipped_reason,
        )
    except Exception as exc:  # pragma: no cover - defensive fail-safe
        logger.warning(
            "competitor_sync.content_gap_candidate_refresh_failed site_id=%s competitor_id=%s error=%s",
            site.id,
            competitor.id,
            exc,
        )
    result.semantic_changed_candidate_ids = sorted({int(candidate_id) for candidate_id in semantic_changed_candidate_ids})
    return result


def _persist_crawled_pages(
    session: Session,
    *,
    site: Site,
    competitor: SiteCompetitor,
    crawled_pages: list[CrawledCompetitorPage],
    processed_urls: int,
    sync_summary: SyncSummaryAccumulator,
) -> PersistedCompetitorPagesResult:
    existing_pages = session.scalars(
        select(SiteCompetitorPage)
        .where(SiteCompetitorPage.competitor_id == competitor.id)
        .order_by(SiteCompetitorPage.id.asc())
    ).all()
    existing_by_url = {page.normalized_url: page for page in existing_pages}

    saved_pages_by_url: dict[str, SiteCompetitorPage] = {}
    seen_urls: set[str] = set()
    for crawled_page in crawled_pages:
        classification = page_taxonomy_service.classify_page(
            url=crawled_page.final_url,
            normalized_url=crawled_page.normalized_url,
            title=crawled_page.extracted_data.title,
            h1=crawled_page.extracted_data.h1,
            schema_types=crawled_page.extracted_data.schema_types_json,
        )
        low_value_reason = _resolve_low_value_skip_reason(crawled_page, classification.page_type)
        if low_value_reason is not None:
            sync_summary.record_skip(reason=low_value_reason, url=crawled_page.normalized_url)
            continue
        if crawled_page.normalized_url in saved_pages_by_url:
            sync_summary.record_skip(reason="duplicate_url", url=crawled_page.normalized_url)

        page = existing_by_url.get(crawled_page.normalized_url)
        if page is None:
            page = SiteCompetitorPage(
                site_id=site.id,
                competitor_id=competitor.id,
                url=crawled_page.requested_url,
                normalized_url=crawled_page.normalized_url,
            )
            session.add(page)
            existing_by_url[crawled_page.normalized_url] = page

        page.url = crawled_page.requested_url
        page.normalized_url = crawled_page.normalized_url
        page.final_url = crawled_page.final_url
        page.status_code = crawled_page.status_code
        page.title = crawled_page.extracted_data.title
        page.meta_description = crawled_page.extracted_data.meta_description
        page.h1 = crawled_page.extracted_data.h1
        page.canonical_url = crawled_page.extracted_data.canonical_url
        page.content_type = crawled_page.content_type
        page.visible_text = crawled_page.extracted_data.visible_text
        page.page_type = classification.page_type
        page.page_bucket = classification.page_bucket
        page.page_type_confidence = classification.page_type_confidence
        page.fetch_diagnostics_json = competitive_gap_page_diagnostics.build_fetch_diagnostics_payload(
            was_rendered=False,
            render_attempted=False,
            fetch_mode_used="http",
            js_heavy_like=False,
            robots_meta=crawled_page.extracted_data.robots_meta,
            x_robots_tag=crawled_page.extracted_data.x_robots_tag,
            schema_count=crawled_page.extracted_data.schema_count,
            schema_types=crawled_page.extracted_data.schema_types_json or [],
        )
        quality_signals = competitive_gap_topic_quality_service.update_page_topic_quality_debug(page)
        pre_semantic_eligibility = competitive_gap_semantic_rules.resolve_semantic_eligibility(
            page,
            match_terms=quality_signals.normalized_terms,
        )
        page.semantic_eligible = bool(pre_semantic_eligibility.eligible)
        page.semantic_exclusion_reason = pre_semantic_eligibility.exclusion_reason
        page.fetched_at = crawled_page.fetched_at

        saved_pages_by_url[crawled_page.normalized_url] = page
        seen_urls.add(crawled_page.normalized_url)

    saved_pages = list(saved_pages_by_url.values())
    session.flush()
    sync_summary.stored_pages_count = len(saved_pages)

    for stale_page in existing_pages:
        if stale_page.normalized_url not in seen_urls:
            session.delete(stale_page)
    session.flush()

    return PersistedCompetitorPagesResult(
        saved_page_ids=[page.id for page in saved_pages],
        processed_urls=processed_urls,
    )


def _extract_saved_pages(
    session: Session,
    *,
    site: Site,
    competitor: SiteCompetitor,
    saved_page_ids: list[int],
    processed_urls: int,
    extract_competitor_page: ExtractCompetitorPageFn,
    sync_run_id: int | None,
    persist_sync_progress: bool,
    checkpoint_each_extraction: bool,
    sync_summary: SyncSummaryAccumulator,
    output_language: str,
) -> CompetitorSyncResult:
    saved_pages = session.scalars(
        select(SiteCompetitorPage)
        .where(SiteCompetitorPage.id.in_(saved_page_ids))
        .order_by(SiteCompetitorPage.id.asc())
    ).all()
    page_by_id = {page.id: page for page in saved_pages}
    ordered_pages = [page_by_id[page_id] for page_id in saved_page_ids if page_id in page_by_id]

    latest_extractions = _load_latest_valid_extractions(session, competitor_id=competitor.id)
    extraction_created = 0
    extraction_skipped = 0
    extraction_skipped_unchanged = 0
    extraction_failed = 0
    extracted_page_ids: list[int] = []
    first_extraction_error: competitive_gap_extraction_service.CompetitiveGapExtractionServiceError | None = None

    for index, page in enumerate(ordered_pages, start=1):
        _ensure_current_sync_run(session, competitor, sync_run_id)

        if not bool(page.semantic_eligible):
            extraction_skipped += 1
            sync_summary.record_skip(
                reason=str(page.semantic_exclusion_reason or "low_value"),
                url=page.normalized_url,
            )
            if checkpoint_each_extraction and persist_sync_progress:
                _persist_extraction_progress(
                    session,
                    competitor,
                    processed_urls=processed_urls,
                    processed_extraction_pages=index,
                    total_extractable_pages=len(ordered_pages),
                    summary_payload=sync_summary.to_payload(),
                    sync_run_id=sync_run_id,
                )
            continue

        latest_extraction = latest_extractions.get(page.id)
        if not site_competitor_service.page_requires_extraction(page, latest_extraction):
            extraction_skipped += 1
            extraction_skipped_unchanged += 1
            sync_summary.extraction_skipped_unchanged_count = extraction_skipped_unchanged
        else:
            try:
                try:
                    extraction_result = extract_competitor_page(page, output_language=output_language)
                except TypeError as exc:
                    if "output_language" not in str(exc):
                        raise
                    extraction_result = extract_competitor_page(page)
            except competitive_gap_extraction_service.CompetitiveGapExtractionServiceError as exc:
                extraction_failed += 1
                sync_summary.extraction_failed_count = extraction_failed
                if first_extraction_error is None:
                    first_extraction_error = exc
            else:
                session.add(
                    SiteCompetitorPageExtraction(
                        site_id=site.id,
                        competitor_id=competitor.id,
                        competitor_page_id=page.id,
                        content_hash_at_extraction=page.content_text_hash,
                        llm_provider=extraction_result.llm_provider,
                        llm_model=extraction_result.llm_model,
                        prompt_version=extraction_result.prompt_version,
                        schema_version=extraction_result.schema_version,
                        semantic_version=extraction_result.semantic_version,
                        semantic_input_hash=extraction_result.semantic_input_hash,
                        semantic_card_json=extraction_result.semantic_card_json,
                        chunk_summary_json=extraction_result.chunk_summary_json,
                        topic_label=extraction_result.topic_label,
                        topic_key=extraction_result.topic_key,
                        search_intent=extraction_result.search_intent,
                        content_format=extraction_result.content_format,
                        page_role=extraction_result.page_role,
                        evidence_snippets_json=extraction_result.evidence_snippets_json,
                        confidence=extraction_result.confidence,
                    )
                )
                extraction_created += 1
                extracted_page_ids.append(page.id)
                sync_summary.extraction_created_count = extraction_created

        sync_summary.extracted_pages_count = _count_current_valid_extractions(session, competitor.id)
        if checkpoint_each_extraction and persist_sync_progress:
            _persist_extraction_progress(
                session,
                competitor,
                processed_urls=processed_urls,
                processed_extraction_pages=index,
                total_extractable_pages=len(ordered_pages),
                summary_payload=sync_summary.to_payload(),
                sync_run_id=sync_run_id,
            )

    session.flush()
    sync_summary.extracted_pages_count = _count_current_valid_extractions(session, competitor.id)

    valid_extraction_count = session.scalar(
        select(SiteCompetitorPageExtraction.id)
        .join(
            SiteCompetitorPage,
            SiteCompetitorPage.id == SiteCompetitorPageExtraction.competitor_page_id,
        )
        .where(
            SiteCompetitorPageExtraction.competitor_id == competitor.id,
            SiteCompetitorPage.semantic_eligible.is_(True),
            SiteCompetitorPage.content_text_hash.is_not_distinct_from(
                SiteCompetitorPageExtraction.content_hash_at_extraction
            ),
        )
        .limit(1)
    )
    if valid_extraction_count is None:
        eligible_page_count = sum(1 for page in ordered_pages if bool(page.semantic_eligible))
        if eligible_page_count <= 0:
            logger.info(
                "competitor_sync.no_extractable_pages_after_gate site_id=%s competitor_id=%s pages=%s",
                site.id,
                competitor.id,
                len(ordered_pages),
            )
            return CompetitorSyncResult(
                pages_saved=len(ordered_pages),
                extraction_created=extraction_created,
                extraction_skipped=extraction_skipped,
                extraction_failed=extraction_failed,
                processed_urls=processed_urls,
                processed_extraction_pages=len(ordered_pages),
                total_extractable_pages=len(ordered_pages),
                summary_payload=sync_summary.to_payload(),
                extracted_page_ids=extracted_page_ids,
            )
        detail = ""
        if first_extraction_error is not None:
            detail = f" Last extraction error: [{first_extraction_error.code}] {first_extraction_error}."
        raise CompetitiveGapSyncServiceError(
            f"Sync finished for '{competitor.domain}', but no current competitor page extractions are available.{detail}",
            code="no_competitor_extractions",
        )

    if persist_sync_progress and not checkpoint_each_extraction:
        _persist_extraction_progress(
            session,
            competitor,
            processed_urls=processed_urls,
            processed_extraction_pages=len(ordered_pages),
            total_extractable_pages=len(ordered_pages),
            summary_payload=sync_summary.to_payload(),
            sync_run_id=sync_run_id,
        )

    return CompetitorSyncResult(
        pages_saved=len(ordered_pages),
        extraction_created=extraction_created,
        extraction_skipped=extraction_skipped,
        extraction_failed=extraction_failed,
        processed_urls=processed_urls,
        processed_extraction_pages=len(ordered_pages),
        total_extractable_pages=len(ordered_pages),
        summary_payload=sync_summary.to_payload(),
        extracted_page_ids=extracted_page_ids,
    )


def _crawl_competitor_pages(
    competitor: SiteCompetitor,
    *,
    fetch_document: FetchDocumentFn,
    sync_summary: SyncSummaryAccumulator,
    progress_callback: CrawlProgressFn | None = None,
    should_continue: ShouldContinueFn | None = None,
) -> CrawledCompetitorPagesResult:
    settings = get_settings()
    start_url = competitor.root_url
    start_normalized_url = normalize_url(start_url)
    if start_normalized_url is None:
        raise CompetitiveGapSyncServiceError(f"Competitor root URL '{start_url}' is invalid.")

    queue: deque[tuple[str, int]] = deque([(start_normalized_url, 0)])
    seen_urls = {start_normalized_url}
    crawled_pages: list[CrawledCompetitorPage] = []
    processed_urls = 0

    while queue and len(seen_urls) <= COMPETITOR_SYNC_MAX_URLS:
        if should_continue is not None and not should_continue():
            raise CompetitiveGapSyncCancelled(
                f"Competitor sync for '{competitor.domain}' was reset.",
                code="sync_reset",
            )

        current_url, depth = queue.popleft()
        processed_urls += 1
        sync_summary.visited_urls_count = processed_urls
        if progress_callback is not None:
            progress_callback(processed_urls)

        fetch_result = _normalize_fetch_result(fetch_document(current_url))
        if fetch_result.document is None:
            sync_summary.record_skip(reason=fetch_result.skip_reason or "fetch_error", url=current_url)
            continue
        document = fetch_result.document
        skip_reason = _classify_competitor_url_skip_reason(document.normalized_url, competitor=competitor)
        if skip_reason is not None:
            sync_summary.record_skip(reason=skip_reason, url=document.normalized_url)
            continue

        response = HtmlResponse(
            url=document.final_url,
            status=document.status_code,
            headers=Headers(document.headers),
            body=document.body,
            request=None,
        )
        extracted_data = extract_page_data(
            response,
            site_registered_domain=competitor.domain,
            blocked_extensions=settings.skip_extensions,
        )
        if has_noindex_directive(extracted_data.robots_meta, extracted_data.x_robots_tag):
            sync_summary.record_skip(reason="non_indexable", url=document.normalized_url)
            if depth >= COMPETITOR_SYNC_MAX_DEPTH:
                continue
            for link in extracted_data.links:
                if not link.should_crawl or not link.target_normalized_url:
                    continue
                next_url = link.target_normalized_url
                if next_url in seen_urls:
                    continue
                if len(seen_urls) >= COMPETITOR_SYNC_MAX_URLS:
                    break
                next_skip_reason = _classify_competitor_url_skip_reason(next_url, competitor=competitor)
                if next_skip_reason is not None:
                    sync_summary.record_skip(reason=next_skip_reason, url=next_url)
                    continue
                seen_urls.add(next_url)
                queue.append((next_url, depth + 1))
            continue
        crawled_pages.append(
            CrawledCompetitorPage(
                requested_url=document.requested_url,
                normalized_url=document.normalized_url,
                final_url=document.final_url,
                status_code=document.status_code,
                content_type=document.headers.get("Content-Type"),
                fetched_at=document.fetched_at,
                extracted_data=extracted_data,
            )
        )

        if depth >= COMPETITOR_SYNC_MAX_DEPTH:
            continue

        for link in extracted_data.links:
            if not link.should_crawl or not link.target_normalized_url:
                continue
            next_url = link.target_normalized_url
            if next_url in seen_urls:
                continue
            if len(seen_urls) >= COMPETITOR_SYNC_MAX_URLS:
                break
            next_skip_reason = _classify_competitor_url_skip_reason(next_url, competitor=competitor)
            if next_skip_reason is not None:
                sync_summary.record_skip(reason=next_skip_reason, url=next_url)
                continue
            seen_urls.add(next_url)
            queue.append((next_url, depth + 1))

    return CrawledCompetitorPagesResult(
        pages=crawled_pages,
        processed_urls=processed_urls,
    )


def _fetch_competitor_document(url: str) -> FetchCompetitorResult:
    settings = get_settings()
    request = Request(
        url,
        headers={
            "User-Agent": settings.scrapy_user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        },
    )
    started = monotonic()
    try:
        with urlopen(request, timeout=settings.scrapy_download_timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            if not _is_html_content_type(content_type):
                return FetchCompetitorResult(skip_reason="non_html")
            body = response.read()
            final_url = response.geturl()
            normalized_url = normalize_url(final_url) or normalize_url(url)
            if normalized_url is None:
                return FetchCompetitorResult(skip_reason="filtered")
            return FetchCompetitorResult(
                document=FetchedCompetitorDocument(
                    requested_url=url,
                    final_url=final_url,
                    normalized_url=normalized_url,
                    status_code=int(response.getcode() or 200),
                    headers={key: value for key, value in response.headers.items()},
                    body=body,
                    fetched_at=utcnow(),
                    response_time_ms=int(round((monotonic() - started) * 1000)),
                )
            )
    except HTTPError as exc:
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        if not _is_html_content_type(content_type):
            return FetchCompetitorResult(skip_reason="non_html")
        body = exc.read()
        final_url = exc.geturl()
        normalized_url = normalize_url(final_url) or normalize_url(url)
        if normalized_url is None:
            return FetchCompetitorResult(skip_reason="filtered")
        return FetchCompetitorResult(
            document=FetchedCompetitorDocument(
                requested_url=url,
                final_url=final_url,
                normalized_url=normalized_url,
                status_code=int(exc.code),
                headers={key: value for key, value in (exc.headers.items() if exc.headers else [])},
                body=body,
                fetched_at=utcnow(),
                response_time_ms=int(round((monotonic() - started) * 1000)),
            )
        )
    except (TimeoutError, URLError, ValueError):
        return FetchCompetitorResult(skip_reason="fetch_error")


def _is_html_content_type(content_type: str | None) -> bool:
    if not content_type:
        return True
    normalized = content_type.lower()
    return "text/html" in normalized or "application/xhtml+xml" in normalized


def _resolve_low_value_skip_reason(page: CrawledCompetitorPage, page_type: str) -> str | None:
    if page_type == "utility":
        return "low_value"
    if page.status_code >= 400:
        return "low_value"
    if not page.extracted_data.visible_text and not page.extracted_data.title and not page.extracted_data.h1:
        return "low_value"
    return None


def _classify_competitor_url_skip_reason(url: str, *, competitor: SiteCompetitor) -> str | None:
    normalized = normalize_url(url)
    if normalized is None:
        return "filtered"

    parsed = urlsplit(normalized)
    root_host = extract_host(competitor.root_url)
    candidate_host = parsed.hostname.lower().strip(".") if parsed.hostname else None
    if candidate_host is None:
        return "out_of_scope"
    allowed_hosts = {competitor.domain}
    if root_host:
        allowed_hosts.add(root_host)
    if root_host and candidate_host not in allowed_hosts and not candidate_host.endswith(f".{competitor.domain}"):
        return "out_of_scope"
    if not candidate_host.endswith(competitor.domain):
        return "out_of_scope"

    path_segments = [segment for segment in parsed.path.lower().split("/") if segment]
    if any(segment in SKIP_PATH_TOKENS for segment in path_segments):
        return "filtered"
    if len(path_segments) >= 2 and path_segments[-2] in {"page", "strona"} and path_segments[-1].isdigit():
        return "filtered"
    if path_segments and path_segments[-1].isdigit() and len(path_segments) == 1:
        return "filtered"

    query_keys = {key.lower() for key, _value in parse_qsl(parsed.query, keep_blank_values=False)}
    if query_keys & SKIP_QUERY_KEYS:
        return "filtered"
    if parsed.query and query_keys:
        return "filtered"
    return None


def _load_latest_valid_extractions(
    session: Session,
    *,
    competitor_id: int,
) -> dict[int, SiteCompetitorPageExtraction]:
    rows = session.scalars(
        select(SiteCompetitorPageExtraction)
        .where(SiteCompetitorPageExtraction.competitor_id == competitor_id)
        .order_by(
            SiteCompetitorPageExtraction.competitor_page_id.asc(),
            SiteCompetitorPageExtraction.extracted_at.desc(),
            SiteCompetitorPageExtraction.id.desc(),
        )
    ).all()
    latest_by_page_id: dict[int, SiteCompetitorPageExtraction] = {}
    for row in rows:
        if row.competitor_page_id not in latest_by_page_id:
            latest_by_page_id[row.competitor_page_id] = row
    return latest_by_page_id


def _get_site_or_raise(session: Session, site_id: int) -> Site:
    site = crawl_job_service.get_site(session, site_id)
    if site is None:
        raise CompetitiveGapSyncServiceError(f"Site {site_id} not found.", code="not_found")
    return site


def _get_competitor_or_raise(session: Session, site_id: int, competitor_id: int) -> SiteCompetitor:
    competitor = session.get(SiteCompetitor, competitor_id)
    if competitor is None or competitor.site_id != site_id:
        raise CompetitiveGapSyncServiceError(
            f"Competitor {competitor_id} not found for site {site_id}.",
            code="not_found",
        )
    return competitor


def _ensure_sync_not_running(competitor: SiteCompetitor) -> None:
    if competitor.last_sync_status in SYNC_IN_PROGRESS_STATUSES:
        raise CompetitiveGapSyncServiceError(
            f"Competitor '{competitor.label}' is already queued or running.",
            code="already_running",
        )


def _reset_sync_runtime_fields(competitor: SiteCompetitor) -> None:
    competitor.last_sync_started_at = None
    competitor.last_sync_finished_at = None
    competitor.last_sync_error_code = None
    competitor.last_sync_error = None
    competitor.last_sync_processed_urls = 0
    competitor.last_sync_url_limit = COMPETITOR_SYNC_MAX_URLS
    competitor.last_sync_processed_extraction_pages = 0
    competitor.last_sync_total_extractable_pages = 0
    competitor.last_sync_summary_json = site_competitor_service.build_empty_sync_summary_payload()


def _mark_competitor_sync_running(
    session: Session,
    site_id: int,
    competitor_id: int,
    run_id: int,
) -> bool:
    return competitive_gap_sync_run_service.claim_sync_run(
        session,
        site_id=site_id,
        competitor_id=competitor_id,
        run_id=run_id,
        url_limit=COMPETITOR_SYNC_MAX_URLS,
    )


def _mark_competitor_sync_failed(
    site_id: int,
    competitor_id: int,
    run_id: int,
    *,
    error: str,
    error_code: str,
) -> None:
    with SessionLocal() as session:
        competitor = _get_competitor_or_raise(session, site_id, competitor_id)
        refreshed_summary = _refresh_summary_payload_from_db(session, competitor)
        competitive_gap_sync_run_service.fail_sync_run(
            site_id,
            competitor_id,
            run_id,
            error_code=error_code,
            error_message_safe=error,
            summary_payload=refreshed_summary,
            processed_urls=competitor.last_sync_processed_urls,
            url_limit=competitor.last_sync_url_limit,
            processed_extraction_pages=competitor.last_sync_processed_extraction_pages,
            total_extractable_pages=competitor.last_sync_total_extractable_pages,
        )


def _mark_competitor_sync_done(
    site_id: int,
    competitor_id: int,
    run_id: int,
    *,
    result: CompetitorSyncResult,
) -> None:
    competitive_gap_sync_run_service.complete_sync_run(
        site_id,
        competitor_id,
        run_id,
        processed_urls=result.processed_urls,
        url_limit=COMPETITOR_SYNC_MAX_URLS,
        processed_extraction_pages=result.processed_extraction_pages,
        total_extractable_pages=result.total_extractable_pages,
        summary_payload=result.summary_payload,
    )


def _persist_crawl_progress(
    session: Session,
    competitor: SiteCompetitor,
    *,
    processed_urls: int,
    summary_payload: dict[str, Any],
    sync_run_id: int | None,
) -> None:
    _ensure_current_sync_run(session, competitor, sync_run_id)
    if sync_run_id is None:
        competitor.last_sync_status = "running"
        competitor.last_sync_stage = "crawling"
        competitor.last_sync_error_code = None
        competitor.last_sync_processed_urls = processed_urls
        competitor.last_sync_url_limit = COMPETITOR_SYNC_MAX_URLS
        competitor.last_sync_processed_extraction_pages = 0
        competitor.last_sync_total_extractable_pages = 0
        competitor.last_sync_summary_json = summary_payload
        session.commit()
        return
    competitive_gap_sync_run_service.touch_sync_run(
        session,
        site_id=competitor.site_id,
        competitor_id=competitor.id,
        run_id=sync_run_id,
        stage="crawling",
        processed_urls=processed_urls,
        url_limit=COMPETITOR_SYNC_MAX_URLS,
        processed_extraction_pages=0,
        total_extractable_pages=0,
        summary_payload=summary_payload,
    )


def _persist_extraction_progress(
    session: Session,
    competitor: SiteCompetitor,
    *,
    processed_urls: int,
    processed_extraction_pages: int,
    total_extractable_pages: int,
    summary_payload: dict[str, Any],
    sync_run_id: int | None,
) -> None:
    _ensure_current_sync_run(session, competitor, sync_run_id)
    if sync_run_id is None:
        competitor.last_sync_status = "running"
        competitor.last_sync_stage = "extracting"
        competitor.last_sync_error_code = None
        competitor.last_sync_processed_urls = processed_urls
        competitor.last_sync_url_limit = COMPETITOR_SYNC_MAX_URLS
        competitor.last_sync_processed_extraction_pages = processed_extraction_pages
        competitor.last_sync_total_extractable_pages = total_extractable_pages
        competitor.last_sync_summary_json = summary_payload
        session.commit()
        return
    competitive_gap_sync_run_service.touch_sync_run(
        session,
        site_id=competitor.site_id,
        competitor_id=competitor.id,
        run_id=sync_run_id,
        stage="extracting",
        processed_urls=processed_urls,
        url_limit=COMPETITOR_SYNC_MAX_URLS,
        processed_extraction_pages=processed_extraction_pages,
        total_extractable_pages=total_extractable_pages,
        summary_payload=summary_payload,
    )


def _sync_run_is_current(session: Session, competitor: SiteCompetitor, sync_run_id: int | None) -> bool:
    if sync_run_id is None:
        return True
    return competitive_gap_sync_run_service.is_sync_run_active(
        session,
        site_id=competitor.site_id,
        competitor_id=competitor.id,
        run_id=sync_run_id,
    )


def _ensure_current_sync_run(session: Session, competitor: SiteCompetitor, sync_run_id: int | None) -> None:
    if sync_run_id is None:
        return
    if not _sync_run_is_current(session, competitor, sync_run_id):
        raise CompetitiveGapSyncCancelled(
            f"Competitor sync for '{competitor.domain}' was reset.",
            code="sync_reset",
        )


def _normalize_fetch_result(raw_result: FetchCompetitorResult | FetchedCompetitorDocument | None) -> FetchCompetitorResult:
    if isinstance(raw_result, FetchCompetitorResult):
        return raw_result
    if isinstance(raw_result, FetchedCompetitorDocument):
        return FetchCompetitorResult(document=raw_result)
    return FetchCompetitorResult(skip_reason="fetch_error")


def _count_current_valid_extractions(session: Session, competitor_id: int) -> int:
    pages = session.scalars(
        select(SiteCompetitorPage)
        .where(SiteCompetitorPage.competitor_id == competitor_id)
        .order_by(SiteCompetitorPage.id.asc())
    ).all()
    page_hash_by_id = {page.id: page.content_text_hash for page in pages}
    eligible_page_ids = {
        page.id
        for page in pages
        if bool(page.semantic_eligible)
    }
    if not page_hash_by_id:
        return 0

    rows = session.scalars(
        select(SiteCompetitorPageExtraction)
        .where(SiteCompetitorPageExtraction.competitor_id == competitor_id)
        .order_by(
            SiteCompetitorPageExtraction.competitor_page_id.asc(),
            SiteCompetitorPageExtraction.extracted_at.desc(),
            SiteCompetitorPageExtraction.id.desc(),
        )
    ).all()
    valid_page_ids: set[int] = set()
    seen_page_ids: set[int] = set()
    for row in rows:
        if row.competitor_page_id in seen_page_ids:
            continue
        seen_page_ids.add(row.competitor_page_id)
        if row.competitor_page_id not in eligible_page_ids:
            continue
        if page_hash_by_id.get(row.competitor_page_id) == row.content_hash_at_extraction:
            valid_page_ids.add(row.competitor_page_id)
    return len(valid_page_ids)


def _refresh_summary_payload_from_db(session: Session, competitor: SiteCompetitor) -> dict[str, Any]:
    payload = site_competitor_service.normalize_sync_summary_payload(competitor.last_sync_summary_json)
    payload["stored_pages_count"] = int(
        session.scalar(
            select(func.count())
            .select_from(SiteCompetitorPage)
            .where(SiteCompetitorPage.competitor_id == competitor.id)
        )
        or 0
    )
    payload["extracted_pages_count"] = _count_current_valid_extractions(session, competitor.id)
    payload["skipped_urls_count"] = max(
        payload["skipped_urls_count"],
        payload["skipped_non_html_count"]
        + payload["skipped_non_indexable_count"]
        + payload["skipped_out_of_scope_count"]
        + payload["skipped_filtered_count"]
        + payload["skipped_low_value_count"]
        + payload["skipped_duplicate_url_count"]
        + payload["skipped_fetch_error_count"],
    )
    return payload

def _normalize_sync_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, CompetitiveGapSyncServiceError):
        return exc.code, str(exc)
    if isinstance(exc, competitive_gap_sync_run_service.CompetitiveGapSyncRunServiceError):
        return exc.code, str(exc)
    if isinstance(exc, competitive_gap_extraction_service.CompetitiveGapExtractionServiceError):
        return exc.code, str(exc)
    return "unexpected_error", "Competitor sync failed due to an unexpected backend error."
