from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CrawlJobStatus, GscTopQuery
from app.services import priority_service, seo_analysis, site_service
from app.services.content_gap_candidate_service import DEFAULT_GSC_DATE_RANGE


COMMERCIAL_PAGE_TYPES = frozenset({"service", "category", "product", "location"})
NON_FALLBACK_PAGE_TYPES = frozenset({"utility", "legal"})
MAX_COMMERCIAL_SOURCE_PAGES = 5
MAX_GSC_QUERIES_PER_PAGE = 3


class ContentGeneratorSourceServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "content_generator_source_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ContentGeneratorSourcePage:
    page_id: int
    url: str
    normalized_url: str
    title: str | None
    h1: str | None
    meta_description: str | None
    page_type: str
    page_bucket: str
    page_type_confidence: float
    priority_score: int
    status_code: int | None
    content_type: str | None
    depth: int
    word_count: int | None
    clicks_28d: int
    impressions_28d: int
    top_queries: list[str]
    selection_reason: str
    selection_score: float


@dataclass(frozen=True, slots=True)
class ContentGeneratorSourceSelection:
    site_id: int
    site_domain: str
    site_root_url: str
    basis_crawl_job_id: int
    source_pages: list[ContentGeneratorSourcePage]
    source_urls: list[str]


def select_site_content_generator_sources(
    session: Session,
    *,
    site_id: int,
    active_crawl_id: int | None = None,
) -> ContentGeneratorSourceSelection:
    try:
        workspace = site_service.resolve_site_workspace_context(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
        )
    except site_service.SiteServiceError as exc:
        raise ContentGeneratorSourceServiceError(str(exc), code="site_context_error") from exc

    site = workspace["site"]
    active_crawl = workspace["active_crawl"]
    if active_crawl is None:
        raise ContentGeneratorSourceServiceError(
            f"Site {site_id} does not have an active crawl snapshot.",
            code="active_crawl_missing",
        )
    active_status = active_crawl.status.value if isinstance(active_crawl.status, CrawlJobStatus) else str(active_crawl.status)
    if active_status != CrawlJobStatus.FINISHED.value:
        raise ContentGeneratorSourceServiceError(
            f"Active crawl {active_crawl.id} must be finished before content assets can be generated.",
            code="active_crawl_not_finished",
        )

    records = seo_analysis.build_page_records(session, active_crawl.id)
    if not records:
        raise ContentGeneratorSourceServiceError(
            f"Active crawl {active_crawl.id} does not contain any pages.",
            code="active_crawl_has_no_pages",
        )

    priority_service.apply_priority_metadata(records, gsc_date_range=DEFAULT_GSC_DATE_RANGE)
    queries_by_url = _load_top_queries_by_url(session, crawl_job_id=active_crawl.id)
    eligible_records = [record for record in records if _record_is_eligible_source(record)]
    if not eligible_records:
        raise ContentGeneratorSourceServiceError(
            f"Active crawl {active_crawl.id} does not contain eligible HTML pages for content generation.",
            code="no_eligible_source_pages",
        )

    selected_records: list[tuple[dict[str, Any], str]] = []
    selected_urls: set[str] = set()

    _add_if_present(
        selected_records,
        selected_urls,
        _pick_best_record(
            eligible_records,
            lambda record: _is_homepage_record(record, site_root_url=str(site.root_url)),
        ),
        reason="homepage",
    )
    _add_if_present(
        selected_records,
        selected_urls,
        _pick_best_record(eligible_records, lambda record: str(record.get("page_type") or "") == "contact"),
        reason="contact",
    )
    _add_if_present(
        selected_records,
        selected_urls,
        _pick_best_record(eligible_records, lambda record: str(record.get("page_type") or "") == "about"),
        reason="about",
    )

    commercial_candidates = [
        record
        for record in eligible_records
        if _normalized_url(record) not in selected_urls and _record_is_commercial_candidate(record)
    ]
    commercial_candidates.sort(key=lambda record: (-_selection_score(record), _normalized_url(record)))
    for index, record in enumerate(commercial_candidates[:MAX_COMMERCIAL_SOURCE_PAGES], start=1):
        _add_if_present(
            selected_records,
            selected_urls,
            record,
            reason=f"commercial_{index}",
        )

    if len([item for item in selected_records if item[1].startswith("commercial_")]) < 2:
        fallback_candidates = [
            record
            for record in eligible_records
            if _normalized_url(record) not in selected_urls and str(record.get("page_type") or "other") not in NON_FALLBACK_PAGE_TYPES
        ]
        fallback_candidates.sort(key=lambda record: (-_selection_score(record), _normalized_url(record)))
        missing_slots = max(0, 2 - len([item for item in selected_records if item[1].startswith("commercial_")]))
        for index, record in enumerate(fallback_candidates[:missing_slots], start=1):
            _add_if_present(
                selected_records,
                selected_urls,
                record,
                reason=f"fallback_{index}",
            )

    source_pages = [
        _build_source_page(record, reason=reason, top_queries=queries_by_url.get(_normalized_url(record), []))
        for record, reason in selected_records
    ]
    if not source_pages:
        raise ContentGeneratorSourceServiceError(
            f"Active crawl {active_crawl.id} did not yield source pages after selection.",
            code="source_selection_empty",
        )

    return ContentGeneratorSourceSelection(
        site_id=site.id,
        site_domain=str(site.domain),
        site_root_url=str(site.root_url),
        basis_crawl_job_id=active_crawl.id,
        source_pages=source_pages,
        source_urls=[page.url for page in source_pages],
    )


def _load_top_queries_by_url(session: Session, *, crawl_job_id: int) -> dict[str, list[str]]:
    rows = session.execute(
        select(
            GscTopQuery.normalized_url,
            GscTopQuery.query,
            GscTopQuery.clicks,
            GscTopQuery.impressions,
            GscTopQuery.position,
            GscTopQuery.id,
        )
        .where(
            GscTopQuery.crawl_job_id == crawl_job_id,
            GscTopQuery.date_range_label == DEFAULT_GSC_DATE_RANGE,
        )
        .order_by(
            GscTopQuery.normalized_url.asc(),
            GscTopQuery.clicks.desc(),
            GscTopQuery.impressions.desc(),
            GscTopQuery.position.asc(),
            GscTopQuery.id.asc(),
        )
    ).all()

    grouped: dict[str, list[str]] = {}
    for row in rows:
        normalized_url = str(row.normalized_url or "").strip()
        query = str(row.query or "").strip()
        if not normalized_url or not query:
            continue
        bucket = grouped.setdefault(normalized_url, [])
        if len(bucket) >= MAX_GSC_QUERIES_PER_PAGE:
            continue
        if query in bucket:
            continue
        bucket.append(query)

    return {
        normalized_url: queries[:MAX_GSC_QUERIES_PER_PAGE]
        for normalized_url, queries in grouped.items()
    }


def _record_is_eligible_source(record: dict[str, Any]) -> bool:
    if not bool(record.get("is_internal", True)):
        return False
    if int(record.get("status_code") or 0) != 200:
        return False
    if bool(record.get("non_indexable_like")):
        return False
    if not _record_is_html_like(record):
        return False
    if _metadata_quality_score(record) <= 0:
        return False
    return True


def _record_is_html_like(record: dict[str, Any]) -> bool:
    content_type = str(record.get("content_type") or "").strip().lower()
    if not content_type:
        return True
    return "html" in content_type


def _record_is_commercial_candidate(record: dict[str, Any]) -> bool:
    page_type = str(record.get("page_type") or "other")
    if page_type in COMMERCIAL_PAGE_TYPES:
        return True
    return str(record.get("page_bucket") or "other") == "commercial" and page_type not in {"home", "other"}


def _is_homepage_record(record: dict[str, Any], *, site_root_url: str) -> bool:
    if str(record.get("page_type") or "") == "home":
        return True
    normalized_url = _normalized_url(record)
    if normalized_url and normalized_url.rstrip("/") == str(site_root_url).rstrip("/"):
        return True
    parsed = urlsplit(normalized_url)
    return (parsed.path or "/") == "/"


def _pick_best_record(records: list[dict[str, Any]], predicate) -> dict[str, Any] | None:
    candidates = [record for record in records if predicate(record)]
    if not candidates:
        return None
    candidates.sort(key=lambda record: (-_selection_score(record), _normalized_url(record)))
    return candidates[0]


def _selection_score(record: dict[str, Any]) -> float:
    page_type = str(record.get("page_type") or "other")
    page_type_weight = {
        "home": 32.0,
        "contact": 24.0,
        "about": 23.0,
        "service": 30.0,
        "category": 28.0,
        "product": 26.0,
        "location": 25.0,
        "faq": 16.0,
        "blog_article": 12.0,
        "blog_index": 8.0,
        "other": 6.0,
    }.get(page_type, 6.0)
    metadata_score = float(_metadata_quality_score(record) * 8)
    priority_score = float(int(record.get("priority_score") or 0) * 1.25)
    clicks_score = min(12.0, float(int(record.get("clicks_28d") or 0)) * 0.35)
    impressions_score = min(10.0, float(int(record.get("impressions_28d") or 0)) / 40.0)
    internal_link_score = min(6.0, float(int(record.get("incoming_internal_linking_pages") or 0)) * 0.6)
    confidence_score = min(6.0, float(record.get("page_type_confidence") or 0.0) * 6.0)
    depth_penalty = min(5.0, float(int(record.get("depth") or 0)))
    word_count = int(record.get("word_count") or 0)
    word_count_score = 5.0 if word_count >= 300 else 3.0 if word_count >= 120 else 1.0 if word_count >= 40 else 0.0
    return (
        page_type_weight
        + metadata_score
        + priority_score
        + clicks_score
        + impressions_score
        + internal_link_score
        + confidence_score
        + word_count_score
        - depth_penalty
    )


def _metadata_quality_score(record: dict[str, Any]) -> int:
    score = 0
    if not seo_analysis.text_value_missing(record.get("title")):
        score += 1
    if not seo_analysis.text_value_missing(record.get("h1")):
        score += 1
    if not seo_analysis.text_value_missing(record.get("meta_description")):
        score += 1
    return score


def _add_if_present(
    selected_records: list[tuple[dict[str, Any], str]],
    selected_urls: set[str],
    record: dict[str, Any] | None,
    *,
    reason: str,
) -> None:
    if record is None:
        return
    normalized_url = _normalized_url(record)
    if not normalized_url or normalized_url in selected_urls:
        return
    selected_records.append((record, reason))
    selected_urls.add(normalized_url)


def _build_source_page(
    record: dict[str, Any],
    *,
    reason: str,
    top_queries: list[str],
) -> ContentGeneratorSourcePage:
    normalized_url = _normalized_url(record)
    return ContentGeneratorSourcePage(
        page_id=int(record.get("id") or 0),
        url=normalized_url,
        normalized_url=normalized_url,
        title=_optional_text(record.get("title")),
        h1=_optional_text(record.get("h1")),
        meta_description=_optional_text(record.get("meta_description")),
        page_type=str(record.get("page_type") or "other"),
        page_bucket=str(record.get("page_bucket") or "other"),
        page_type_confidence=float(record.get("page_type_confidence") or 0.0),
        priority_score=int(record.get("priority_score") or 0),
        status_code=int(record.get("status_code")) if record.get("status_code") is not None else None,
        content_type=_optional_text(record.get("content_type")),
        depth=int(record.get("depth") or 0),
        word_count=int(record.get("word_count")) if record.get("word_count") is not None else None,
        clicks_28d=int(record.get("clicks_28d") or 0),
        impressions_28d=int(record.get("impressions_28d") or 0),
        top_queries=list(top_queries[:MAX_GSC_QUERIES_PER_PAGE]),
        selection_reason=reason,
        selection_score=_selection_score(record),
    )


def _normalized_url(record: dict[str, Any]) -> str:
    value = record.get("normalized_url") or record.get("final_url") or record.get("url") or ""
    return str(value).strip()


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
