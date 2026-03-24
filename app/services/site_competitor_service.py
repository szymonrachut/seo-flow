from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    SiteCompetitor,
    SiteCompetitorPage,
    SiteCompetitorPageExtraction,
    SiteCompetitorSemanticCandidate,
    SiteCompetitorSemanticDecision,
    SiteCompetitorSemanticRun,
)
from app.services.competitive_gap_page_diagnostics import (
    get_fetch_diagnostics,
    get_page_robots_meta,
    get_page_x_robots_tag,
)
from app.services import crawl_job_service
from app.services.competitive_gap_semantic_card_service import SEMANTIC_CARD_VERSION


class SiteCompetitorServiceError(RuntimeError):
    pass


SYNC_SUMMARY_INT_FIELDS = {
    "visited_urls_count",
    "stored_pages_count",
    "extracted_pages_count",
    "skipped_urls_count",
    "skipped_non_html_count",
    "skipped_non_indexable_count",
    "skipped_out_of_scope_count",
    "skipped_filtered_count",
    "skipped_low_value_count",
    "skipped_duplicate_url_count",
    "skipped_fetch_error_count",
    "extraction_created_count",
    "extraction_skipped_unchanged_count",
    "extraction_failed_count",
}


def build_empty_sync_summary_payload() -> dict[str, Any]:
    return {
        "visited_urls_count": 0,
        "stored_pages_count": 0,
        "extracted_pages_count": 0,
        "skipped_urls_count": 0,
        "skipped_non_html_count": 0,
        "skipped_non_indexable_count": 0,
        "skipped_out_of_scope_count": 0,
        "skipped_filtered_count": 0,
        "skipped_low_value_count": 0,
        "skipped_duplicate_url_count": 0,
        "skipped_fetch_error_count": 0,
        "extraction_created_count": 0,
        "extraction_skipped_unchanged_count": 0,
        "extraction_failed_count": 0,
        "sample_urls_by_reason": {},
    }


def normalize_sync_summary_payload(summary: Any) -> dict[str, Any]:
    payload = build_empty_sync_summary_payload()
    if not isinstance(summary, dict):
        return payload

    for field_name in SYNC_SUMMARY_INT_FIELDS:
        try:
            payload[field_name] = max(0, int(summary.get(field_name, 0) or 0))
        except (TypeError, ValueError):
            payload[field_name] = 0

    sample_urls = summary.get("sample_urls_by_reason")
    if isinstance(sample_urls, dict):
        normalized_samples: dict[str, list[str]] = {}
        for reason, values in sample_urls.items():
            if not isinstance(reason, str) or not isinstance(values, list):
                continue
            cleaned = [
                str(value).strip()
                for value in values
                if isinstance(value, str) and value.strip()
            ][:3]
            if cleaned:
                normalized_samples[reason] = cleaned
        payload["sample_urls_by_reason"] = normalized_samples

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


def list_site_competitors(session: Session, site_id: int) -> list[dict[str, Any]]:
    from app.services import competitive_gap_semantic_run_service, competitive_gap_sync_run_service

    _get_site_or_raise(session, site_id)
    if competitive_gap_sync_run_service.reconcile_stale_sync_runs(session, site_id=site_id):
        session.commit()
    if competitive_gap_semantic_run_service.reconcile_stale_semantic_runs(session, site_id=site_id):
        session.commit()
    competitors = session.scalars(
        select(SiteCompetitor)
        .where(SiteCompetitor.site_id == site_id)
        .order_by(SiteCompetitor.created_at.desc(), SiteCompetitor.id.desc())
    ).all()
    return [_serialize_competitor(session, competitor) for competitor in competitors]


def get_site_competitor_payload(session: Session, site_id: int, competitor_id: int) -> dict[str, Any]:
    from app.services import competitive_gap_semantic_run_service, competitive_gap_sync_run_service

    _get_site_or_raise(session, site_id)
    if competitive_gap_sync_run_service.reconcile_stale_sync_runs(
        session,
        site_id=site_id,
        competitor_id=competitor_id,
    ):
        session.commit()
    if competitive_gap_semantic_run_service.reconcile_stale_semantic_runs(
        session,
        site_id=site_id,
        competitor_id=competitor_id,
    ):
        session.commit()
    competitor = _get_competitor_or_raise(session, site_id, competitor_id)
    return _serialize_competitor(session, competitor)


def list_site_competitor_review_records(
    session: Session,
    site_id: int,
    competitor_id: int,
    *,
    review_status: str = "all",
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    _get_site_or_raise(session, site_id)
    competitor = _get_competitor_or_raise(session, site_id, competitor_id)
    pages = session.scalars(
        select(SiteCompetitorPage)
        .where(SiteCompetitorPage.competitor_id == competitor.id)
        .order_by(
            SiteCompetitorPage.semantic_eligible.desc(),
            SiteCompetitorPage.fetched_at.desc(),
            SiteCompetitorPage.id.desc(),
        )
    ).all()
    extractions = session.scalars(
        select(SiteCompetitorPageExtraction)
        .where(SiteCompetitorPageExtraction.competitor_id == competitor.id)
        .order_by(SiteCompetitorPageExtraction.extracted_at.desc(), SiteCompetitorPageExtraction.id.desc())
    ).all()
    latest_valid_extractions_by_page_id = _build_latest_valid_extractions_by_page_id(pages, extractions)

    accepted_pages = [page for page in pages if bool(page.semantic_eligible)]
    rejected_pages = [page for page in pages if not bool(page.semantic_eligible)]
    filtered_pages = pages
    if review_status == "accepted":
        filtered_pages = accepted_pages
    elif review_status == "rejected":
        filtered_pages = rejected_pages

    normalized_page = max(1, int(page or 1))
    normalized_page_size = max(1, int(page_size or 25))
    total_items = len(filtered_pages)
    total_pages = max(1, (total_items + normalized_page_size - 1) // normalized_page_size)
    normalized_page = min(normalized_page, total_pages)
    start = (normalized_page - 1) * normalized_page_size
    paged_pages = filtered_pages[start : start + normalized_page_size]

    return {
        "site_id": site_id,
        "competitor_id": competitor_id,
        "review_status": review_status if review_status in {"accepted", "rejected"} else "all",
        "summary": {
            "total_pages": len(pages),
            "accepted_pages": len(accepted_pages),
            "rejected_pages": len(rejected_pages),
            "current_extractions_count": len(latest_valid_extractions_by_page_id),
            "counts_by_reason": _build_review_reason_counts(
                pages,
                latest_valid_extractions_by_page_id=latest_valid_extractions_by_page_id,
            ),
        },
        "items": [
            _serialize_competitor_review_record(
                page,
                latest_extraction=latest_valid_extractions_by_page_id.get(page.id),
            )
            for page in paged_pages
        ],
        "page": normalized_page,
        "page_size": normalized_page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def create_site_competitor(
    session: Session,
    site_id: int,
    *,
    root_url: str,
    label: str | None,
    notes: str | None,
    is_active: bool,
) -> dict[str, Any]:
    site = _get_site_or_raise(session, site_id)
    normalized_root_url, domain = crawl_job_service.normalize_start_url_or_raise(root_url)
    _validate_competitor_domain(site.domain, domain)

    competitor = SiteCompetitor(
        site_id=site_id,
        label=_resolve_label(label, domain),
        root_url=normalized_root_url,
        domain=domain,
        notes=_strip_or_none(notes),
        is_active=is_active,
    )
    session.add(competitor)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise SiteCompetitorServiceError(
            f"Competitor '{domain}' already exists for site {site_id}."
        ) from exc

    session.refresh(competitor)
    return _serialize_competitor(session, competitor)


def update_site_competitor(
    session: Session,
    site_id: int,
    competitor_id: int,
    *,
    root_url: str | None,
    label: str | None,
    notes: str | None,
    is_active: bool | None,
) -> dict[str, Any]:
    site = _get_site_or_raise(session, site_id)
    competitor = _get_competitor_or_raise(session, site_id, competitor_id)

    if root_url is not None:
        normalized_root_url, domain = crawl_job_service.normalize_start_url_or_raise(root_url)
        _validate_competitor_domain(site.domain, domain)
        previous_domain = competitor.domain
        competitor.root_url = normalized_root_url
        competitor.domain = domain
        if label is None and competitor.label == previous_domain:
            competitor.label = domain

    if label is not None:
        competitor.label = _resolve_label(label, competitor.domain)
    if notes is not None:
        competitor.notes = _strip_or_none(notes)
    if is_active is not None:
        competitor.is_active = bool(is_active)

    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise SiteCompetitorServiceError(
            f"Competitor '{competitor.domain}' already exists for site {site_id}."
        ) from exc

    session.refresh(competitor)
    return _serialize_competitor(session, competitor)


def delete_site_competitor(session: Session, site_id: int, competitor_id: int) -> None:
    _get_site_or_raise(session, site_id)
    competitor = _get_competitor_or_raise(session, site_id, competitor_id)
    session.delete(competitor)
    session.flush()


def page_requires_extraction(
    page: SiteCompetitorPage,
    latest_extraction: SiteCompetitorPageExtraction | None,
) -> bool:
    if latest_extraction is None:
        return True
    if page.content_text_hash != latest_extraction.content_hash_at_extraction:
        return True
    if not latest_extraction.semantic_card_json:
        return True
    if (latest_extraction.semantic_version or "").strip() != SEMANTIC_CARD_VERSION:
        return True
    return False


def _get_site_or_raise(session: Session, site_id: int):
    site = crawl_job_service.get_site(session, site_id)
    if site is None:
        raise SiteCompetitorServiceError(f"Site {site_id} not found.")
    return site


def _get_competitor_or_raise(session: Session, site_id: int, competitor_id: int) -> SiteCompetitor:
    competitor = session.get(SiteCompetitor, competitor_id)
    if competitor is None or competitor.site_id != site_id:
        raise SiteCompetitorServiceError(f"Competitor {competitor_id} not found for site {site_id}.")
    return competitor


def _validate_competitor_domain(site_domain: str, competitor_domain: str) -> None:
    if site_domain.lower() == competitor_domain.lower():
        raise SiteCompetitorServiceError("Competitor domain must be different from the site domain.")


def _serialize_competitor(session: Session, competitor: SiteCompetitor) -> dict[str, Any]:
    from app.services import competitive_gap_semantic_run_service

    pages = session.scalars(
        select(SiteCompetitorPage)
        .where(SiteCompetitorPage.competitor_id == competitor.id)
        .order_by(SiteCompetitorPage.id.asc())
    ).all()
    extractions = session.scalars(
        select(SiteCompetitorPageExtraction)
        .where(SiteCompetitorPageExtraction.competitor_id == competitor.id)
        .order_by(SiteCompetitorPageExtraction.extracted_at.desc(), SiteCompetitorPageExtraction.id.desc())
    ).all()
    latest_valid_extractions_by_page_id = _build_latest_valid_extractions_by_page_id(pages, extractions)

    current_semantic_candidates = session.scalars(
        select(SiteCompetitorSemanticCandidate)
        .where(
            SiteCompetitorSemanticCandidate.competitor_id == competitor.id,
            SiteCompetitorSemanticCandidate.current.is_(True),
        )
        .order_by(SiteCompetitorSemanticCandidate.id.asc())
    ).all()
    semantic_candidates_count = len(current_semantic_candidates)
    semantic_runs = session.scalars(
        select(SiteCompetitorSemanticRun)
        .where(SiteCompetitorSemanticRun.competitor_id == competitor.id)
        .order_by(SiteCompetitorSemanticRun.id.desc())
        .limit(25)
    ).all()
    latest_semantic_run = semantic_runs[0] if semantic_runs else None
    semantic_display_run = _resolve_semantic_display_run(semantic_runs)
    semantic_summary = (
        competitive_gap_semantic_run_service.normalize_semantic_summary_payload(semantic_display_run.summary_json)
        if semantic_display_run is not None
        else competitive_gap_semantic_run_service.build_empty_semantic_summary_payload()
    )
    latest_semantic_summary = (
        competitive_gap_semantic_run_service.normalize_semantic_summary_payload(latest_semantic_run.summary_json)
        if latest_semantic_run is not None
        else competitive_gap_semantic_run_service.build_empty_semantic_summary_payload()
    )
    semantic_status = _resolve_semantic_status(
        latest_semantic_run.status if latest_semantic_run is not None else None,
        semantic_summary=semantic_summary,
        semantic_candidates_count=semantic_candidates_count,
    )
    semantic_progress_percent = _compute_semantic_progress_percent(
        semantic_candidates_count=semantic_candidates_count,
        semantic_summary=semantic_summary,
        semantic_display_run=semantic_display_run,
    )
    semantic_llm_merged_urls_count = _count_llm_merged_urls(
        session,
        current_candidates=current_semantic_candidates,
    )

    extracted_page_ids = set(latest_valid_extractions_by_page_id)
    accepted_pages_count = sum(1 for page in pages if bool(page.semantic_eligible))
    latest_valid_extraction = max(
        latest_valid_extractions_by_page_id.values(),
        key=lambda item: (item.extracted_at, item.id),
        default=None,
    )
    last_extracted_at: datetime | None = latest_valid_extraction.extracted_at if latest_valid_extraction is not None else None
    return {
        "id": competitor.id,
        "site_id": competitor.site_id,
        "label": competitor.label,
        "root_url": competitor.root_url,
        "domain": competitor.domain,
        "is_active": competitor.is_active,
        "notes": competitor.notes,
        "last_sync_run_id": competitor.last_sync_run_id,
        "last_sync_status": competitor.last_sync_status,
        "last_sync_stage": competitor.last_sync_stage,
        "last_sync_started_at": competitor.last_sync_started_at,
        "last_sync_finished_at": competitor.last_sync_finished_at,
        "last_sync_error_code": competitor.last_sync_error_code,
        "last_sync_error": competitor.last_sync_error,
        "last_sync_processed_urls": competitor.last_sync_processed_urls,
        "last_sync_url_limit": competitor.last_sync_url_limit,
        "last_sync_processed_extraction_pages": competitor.last_sync_processed_extraction_pages,
        "last_sync_total_extractable_pages": competitor.last_sync_total_extractable_pages,
        "last_sync_progress_percent": _compute_sync_progress_percent(competitor),
        "last_sync_summary": normalize_sync_summary_payload(competitor.last_sync_summary_json),
        "pages_count": len(pages),
        "accepted_pages_count": accepted_pages_count,
        "rejected_pages_count": max(0, len(pages) - accepted_pages_count),
        "extracted_pages_count": len(extracted_page_ids),
        "last_extracted_at": last_extracted_at,
        "semantic_status": semantic_status,
        "semantic_analysis_mode": _resolve_semantic_analysis_mode(
            semantic_status=semantic_status,
            semantic_summary=semantic_summary,
            semantic_candidates_count=semantic_candidates_count,
            semantic_llm_merged_urls_count=semantic_llm_merged_urls_count,
        ),
        "last_semantic_stage": latest_semantic_run.stage if latest_semantic_run is not None else None,
        "last_semantic_run_started_at": (
            semantic_display_run.started_at or semantic_display_run.created_at
            if semantic_display_run is not None
            else None
        ),
        "last_semantic_run_finished_at": semantic_display_run.finished_at if semantic_display_run is not None else None,
        "last_semantic_heartbeat_at": latest_semantic_run.last_heartbeat_at if latest_semantic_run is not None else None,
        "last_semantic_lease_expires_at": latest_semantic_run.lease_expires_at if latest_semantic_run is not None else None,
        "last_semantic_error_code": latest_semantic_run.error_code if latest_semantic_run is not None else None,
        "last_semantic_error": latest_semantic_run.error_message_safe if latest_semantic_run is not None else None,
        "semantic_candidates_count": semantic_candidates_count,
        "semantic_run_scope_candidates_count": latest_semantic_summary["semantic_candidates_count"],
        "semantic_llm_jobs_count": semantic_summary["semantic_llm_jobs_count"],
        "semantic_resolved_count": semantic_summary["semantic_resolved_count"],
        "semantic_run_scope_resolved_count": latest_semantic_summary["semantic_resolved_count"],
        "semantic_progress_percent": semantic_progress_percent,
        "semantic_cache_hits": semantic_summary["semantic_cache_hits"],
        "semantic_fallback_count": semantic_summary["semantic_fallback_count"],
        "semantic_llm_merged_urls_count": semantic_llm_merged_urls_count,
        "semantic_cluster_count": semantic_summary.get("cluster_count", 0),
        "semantic_low_confidence_count": semantic_summary.get("low_confidence_count", 0),
        "semantic_cards_count": semantic_summary.get("semantic_cards_count", 0),
        "semantic_own_page_profiles_count": semantic_summary.get("own_page_profiles_count", 0),
        "semantic_canonical_pages_count": semantic_summary.get("canonical_pages_count", 0),
        "semantic_duplicate_pages_count": semantic_summary.get("duplicate_pages_count", 0),
        "semantic_near_duplicate_pages_count": semantic_summary.get("near_duplicate_pages_count", 0),
        "semantic_version": semantic_summary.get("semantic_version"),
        "semantic_cluster_version": semantic_summary.get("cluster_version"),
        "semantic_coverage_version": semantic_summary.get("coverage_version"),
        "semantic_model": semantic_display_run.llm_model if semantic_display_run is not None else None,
        "semantic_prompt_version": semantic_display_run.prompt_version if semantic_display_run is not None else None,
        "created_at": competitor.created_at,
        "updated_at": competitor.updated_at,
    }


def _build_latest_valid_extractions_by_page_id(
    pages: list[SiteCompetitorPage],
    extractions: list[SiteCompetitorPageExtraction],
) -> dict[int, SiteCompetitorPageExtraction]:
    page_by_id = {page.id: page for page in pages}
    latest_valid_extractions_by_page_id: dict[int, SiteCompetitorPageExtraction] = {}
    for extraction in extractions:
        page = page_by_id.get(extraction.competitor_page_id)
        if page is None:
            continue
        if not bool(page.semantic_eligible):
            continue
        if page_requires_extraction(page, extraction):
            continue
        if extraction.competitor_page_id not in latest_valid_extractions_by_page_id:
            latest_valid_extractions_by_page_id[extraction.competitor_page_id] = extraction
    return latest_valid_extractions_by_page_id


def _build_review_reason_counts(
    pages: list[SiteCompetitorPage],
    *,
    latest_valid_extractions_by_page_id: dict[int, SiteCompetitorPageExtraction],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for page in pages:
        reason = _resolve_review_reason_code(
            page,
            has_current_extraction=page.id in latest_valid_extractions_by_page_id,
        )
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _serialize_competitor_review_record(
    page: SiteCompetitorPage,
    *,
    latest_extraction: SiteCompetitorPageExtraction | None,
) -> dict[str, Any]:
    diagnostics = _build_review_diagnostics(page)
    has_current_extraction = latest_extraction is not None
    review_reason_code = _resolve_review_reason_code(page, has_current_extraction=has_current_extraction)
    return {
        "id": page.id,
        "url": page.url,
        "normalized_url": page.normalized_url,
        "final_url": page.final_url,
        "status_code": page.status_code,
        "title": page.title,
        "meta_description": page.meta_description,
        "h1": page.h1,
        "page_type": page.page_type,
        "page_bucket": page.page_bucket,
        "page_type_confidence": float(page.page_type_confidence or 0.0),
        "semantic_eligible": bool(page.semantic_eligible),
        "semantic_exclusion_reason": page.semantic_exclusion_reason,
        "review_status": "accepted" if bool(page.semantic_eligible) else "rejected",
        "review_reason_code": review_reason_code,
        "review_reason_detail": _build_review_reason_detail(
            page,
            diagnostics=diagnostics,
            has_current_extraction=has_current_extraction,
        ),
        "has_current_extraction": has_current_extraction,
        "current_extraction_topic_label": latest_extraction.topic_label if latest_extraction is not None else None,
        "current_extraction_confidence": float(latest_extraction.confidence) if latest_extraction is not None else None,
        "last_extracted_at": latest_extraction.extracted_at if latest_extraction is not None else None,
        "diagnostics": diagnostics,
        "fetched_at": page.fetched_at,
        "updated_at": page.updated_at,
    }


def _build_review_diagnostics(page: SiteCompetitorPage) -> dict[str, Any]:
    raw_diagnostics = get_fetch_diagnostics(page)
    diagnostics: dict[str, Any] = {}
    for field_name in (
        "title_h1_alignment_score",
        "meta_support_score",
        "body_conflict_score",
        "boilerplate_contamination_score",
        "dominant_topic_strength",
        "weak_evidence_flag",
        "weak_evidence_reason",
        "dominant_topic_label",
        "dominant_topic_key",
        "page_role_hint",
        "normalized_terms",
        "fetch_mode_used",
        "render_reason",
        "render_error_message",
        "schema_types",
    ):
        value = raw_diagnostics.get(field_name)
        if value is None or value == []:
            continue
        diagnostics[field_name] = value

    robots_meta = get_page_robots_meta(page)
    x_robots_tag = get_page_x_robots_tag(page)
    if robots_meta:
        diagnostics["robots_meta"] = robots_meta
    if x_robots_tag:
        diagnostics["x_robots_tag"] = x_robots_tag
    return diagnostics


def _resolve_review_reason_code(page: SiteCompetitorPage, *, has_current_extraction: bool) -> str:
    if bool(page.semantic_eligible):
        return "accepted_with_extraction" if has_current_extraction else "accepted_pending_extraction"
    return str(page.semantic_exclusion_reason or "rejected_before_extraction")


def _build_review_reason_detail(
    page: SiteCompetitorPage,
    *,
    diagnostics: dict[str, Any],
    has_current_extraction: bool,
) -> str:
    signals = [
        _format_numeric_signal("dominant_topic_strength", diagnostics.get("dominant_topic_strength")),
        _format_numeric_signal("title_h1_alignment_score", diagnostics.get("title_h1_alignment_score")),
        _format_numeric_signal("meta_support_score", diagnostics.get("meta_support_score")),
        _format_numeric_signal("body_conflict_score", diagnostics.get("body_conflict_score")),
        _format_numeric_signal("boilerplate_contamination_score", diagnostics.get("boilerplate_contamination_score")),
    ]
    joined_signals = ", ".join(value for value in signals if value)
    if bool(page.semantic_eligible):
        status_detail = (
            "Accepted into the semantic foundation and already extracted."
            if has_current_extraction
            else "Accepted into the semantic foundation but waiting for a current extraction."
        )
        weak_flag = diagnostics.get("weak_evidence_flag")
        weak_reason = diagnostics.get("weak_evidence_reason")
        suffix = []
        if weak_flag is not None:
            suffix.append(f"weak_evidence_flag={bool(weak_flag)}")
        if isinstance(weak_reason, str) and weak_reason.strip():
            suffix.append(f"weak_evidence_reason={weak_reason.strip()}")
        if joined_signals:
            suffix.append(joined_signals)
        return " ".join([status_detail, *suffix]).strip()

    exclusion_reason = str(page.semantic_exclusion_reason or "rejected_before_extraction")
    detail_parts = [f"Rejected before extraction: exclusion_reason={exclusion_reason}."]
    if exclusion_reason == "non_indexable":
        robots_meta = diagnostics.get("robots_meta")
        x_robots_tag = diagnostics.get("x_robots_tag")
        if robots_meta:
            detail_parts.append(f"robots_meta={robots_meta}.")
        if x_robots_tag:
            detail_parts.append(f"x_robots_tag={x_robots_tag}.")
    else:
        weak_reason = diagnostics.get("weak_evidence_reason")
        if isinstance(weak_reason, str) and weak_reason.strip():
            detail_parts.append(f"weak_evidence_reason={weak_reason.strip()}.")
    if joined_signals:
        detail_parts.append(joined_signals)
    return " ".join(part.strip() for part in detail_parts if part).strip()


def _format_numeric_signal(label: str, value: Any) -> str | None:
    try:
        if value is None:
            return None
        return f"{label}={float(value):.2f}"
    except (TypeError, ValueError):
        return None


def _resolve_label(label: str | None, domain: str) -> str:
    if label is None:
        return domain
    stripped = label.strip()
    return stripped or domain


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _compute_sync_progress_percent(competitor: SiteCompetitor) -> int:
    if competitor.last_sync_status == "done":
        return 100
    if competitor.last_sync_stage == "extracting" and competitor.last_sync_total_extractable_pages > 0:
        return int(
            round(
                min(
                    100,
                    (competitor.last_sync_processed_extraction_pages / competitor.last_sync_total_extractable_pages) * 100,
                )
            )
        )
    if competitor.last_sync_url_limit > 0:
        return int(round(min(100, (competitor.last_sync_processed_urls / competitor.last_sync_url_limit) * 100)))
    return 0


def _resolve_semantic_status(
    latest_run_status: str | None,
    *,
    semantic_summary: dict[str, Any],
    semantic_candidates_count: int,
) -> str:
    if latest_run_status is None:
        return "not_started"
    if latest_run_status in {"queued", "running", "failed", "stale", "cancelled"}:
        return latest_run_status
    if latest_run_status == "completed":
        if semantic_candidates_count == 0:
            return "not_started"
        if semantic_summary["semantic_fallback_count"] > 0:
            return "partial"
        if semantic_summary["semantic_resolved_count"] < semantic_candidates_count:
            return "partial"
        return "ready"
    return latest_run_status


def _resolve_semantic_analysis_mode(
    *,
    semantic_status: str,
    semantic_summary: dict[str, Any],
    semantic_candidates_count: int,
    semantic_llm_merged_urls_count: int,
) -> str:
    has_llm = (
        int(semantic_summary.get("semantic_llm_jobs_count", 0) or 0) > 0
        or int(semantic_summary.get("semantic_cache_hits", 0) or 0) > 0
        or semantic_llm_merged_urls_count > 0
    )
    has_local = int(semantic_summary.get("semantic_fallback_count", 0) or 0) > 0

    if not has_llm and not has_local:
        if semantic_candidates_count > 0 and semantic_status in {"ready", "partial", "failed", "stale", "cancelled"}:
            return "local_only"
        return "not_started"
    if has_llm and has_local:
        return "mixed"
    if has_llm:
        return "llm_only"
    return "local_only"


def _compute_semantic_progress_percent(
    *,
    semantic_candidates_count: int,
    semantic_summary: dict[str, Any],
    semantic_display_run: SiteCompetitorSemanticRun | None,
) -> int:
    total_candidates = max(0, int(semantic_candidates_count or 0))
    if total_candidates <= 0:
        if semantic_display_run is not None and semantic_display_run.status == "completed":
            return 100
        return 0

    run_scope_candidates = max(0, min(total_candidates, int(semantic_summary.get("semantic_candidates_count", 0) or 0)))
    run_resolved_count = max(0, min(run_scope_candidates, int(semantic_summary.get("semantic_resolved_count", 0) or 0)))

    effective_resolved_count = run_resolved_count
    if (
        semantic_display_run is not None
        and semantic_display_run.mode == "incremental"
        and semantic_display_run.status in {"completed", "ready", "partial"}
        and run_scope_candidates > 0
    ):
        already_covered_candidates = max(0, total_candidates - run_scope_candidates)
        effective_resolved_count = min(total_candidates, already_covered_candidates + run_resolved_count)

    return int(round(min(100, (effective_resolved_count / total_candidates) * 100)))


def _resolve_semantic_display_run(
    semantic_runs: list[SiteCompetitorSemanticRun],
) -> SiteCompetitorSemanticRun | None:
    if not semantic_runs:
        return None

    latest_run = semantic_runs[0]
    if latest_run.status in {"queued", "running"}:
        return latest_run
    if _semantic_run_has_displayable_progress(latest_run):
        return latest_run

    for run in semantic_runs[1:]:
        if _semantic_run_has_displayable_progress(run):
            return run
    return latest_run


def _semantic_run_has_displayable_progress(run: SiteCompetitorSemanticRun) -> bool:
    from app.services import competitive_gap_semantic_run_service

    if run.started_at is not None:
        return True
    summary = competitive_gap_semantic_run_service.normalize_semantic_summary_payload(run.summary_json)
    return any(
        int(summary.get(field_name, 0) or 0) > 0
        for field_name in (
            "semantic_resolved_count",
            "semantic_llm_jobs_count",
            "semantic_cache_hits",
            "semantic_fallback_count",
            "merge_pairs_count",
            "own_match_pairs_count",
        )
    )


def _count_llm_merged_urls(
    session: Session,
    *,
    current_candidates: list[SiteCompetitorSemanticCandidate],
) -> int:
    if not current_candidates:
        return 0

    current_candidate_ids = {candidate.id for candidate in current_candidates}
    current_page_ids_by_candidate_id = {
        candidate.id: candidate.competitor_page_id
        for candidate in current_candidates
    }
    merge_rows = session.scalars(
        select(SiteCompetitorSemanticDecision)
        .where(
            SiteCompetitorSemanticDecision.decision_type == "merge",
            SiteCompetitorSemanticDecision.fallback_used.is_(False),
            SiteCompetitorSemanticDecision.decision_label.in_(("same_topic", "related_subtopic")),
            or_(
                SiteCompetitorSemanticDecision.source_candidate_id.in_(current_candidate_ids),
                SiteCompetitorSemanticDecision.target_candidate_id.in_(current_candidate_ids),
            ),
        )
        .order_by(SiteCompetitorSemanticDecision.id.asc())
    ).all()
    merged_page_ids: set[int] = set()
    for row in merge_rows:
        source_page_id = current_page_ids_by_candidate_id.get(int(row.source_candidate_id))
        if source_page_id is not None:
            merged_page_ids.add(source_page_id)
        target_candidate_id = int(row.target_candidate_id) if row.target_candidate_id is not None else None
        if target_candidate_id is not None:
            target_page_id = current_page_ids_by_candidate_id.get(target_candidate_id)
            if target_page_id is not None:
                merged_page_ids.add(target_page_id)
    return len(merged_page_ids)
