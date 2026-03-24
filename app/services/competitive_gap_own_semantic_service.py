from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.text_processing import collapse_whitespace, dedupe_preserve_order, normalize_text_for_hash, tokenize_topic_text
from app.db.models import CrawlJob, CrawlPageSemanticProfile, GscTopQuery, Page, utcnow
from app.services.competitive_gap_semantic_card_service import OWN_PAGE_SEMANTIC_PROFILE_VERSION, build_semantic_card
from app.services.seo_analysis import build_page_records


OWN_PROFILE_EXCLUDED_PAGE_TYPES = {"about", "contact", "legal", "utility"}
OWN_PROFILE_EXCLUDED_BUCKETS = {"utility"}
OWN_QUERY_LIMIT = 5


class CompetitiveGapOwnSemanticServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class OwnSemanticProfileRefreshResult:
    processed_pages: int = 0
    unchanged_pages: int = 0
    inserted_profiles: int = 0
    updated_profiles: int = 0
    retired_profiles: int = 0
    current_profiles_count: int = 0


def ensure_current_own_page_semantic_profiles(
    session: Session,
    site_id: int,
    crawl_job_id: int,
    *,
    gsc_date_range: str = "last_28_days",
    page_records: list[dict[str, Any]] | None = None,
) -> OwnSemanticProfileRefreshResult:
    crawl_job = session.get(CrawlJob, crawl_job_id)
    if crawl_job is None or crawl_job.site_id != site_id:
        raise CompetitiveGapOwnSemanticServiceError(
            f"Active crawl {crawl_job_id} not found for site {site_id}."
        )

    resolved_page_records = page_records or build_page_records(session, crawl_job_id)
    if not resolved_page_records:
        return OwnSemanticProfileRefreshResult()

    page_ids = sorted(
        int(record["id"])
        for record in resolved_page_records
        if record.get("id") is not None
    )
    pages = session.scalars(
        select(Page)
        .where(Page.crawl_job_id == crawl_job_id, Page.id.in_(page_ids))
        .order_by(Page.id.asc())
    ).all()
    pages_by_id = {page.id: page for page in pages}
    top_queries_by_page_id = _load_top_queries_by_page_id(
        session,
        crawl_job_id=crawl_job_id,
        page_ids=page_ids,
        date_range_label=gsc_date_range,
    )
    existing_rows = session.scalars(
        select(CrawlPageSemanticProfile)
        .where(
            CrawlPageSemanticProfile.site_id == site_id,
            CrawlPageSemanticProfile.crawl_job_id == crawl_job_id,
            CrawlPageSemanticProfile.page_id.in_(page_ids),
        )
        .order_by(
            CrawlPageSemanticProfile.page_id.asc(),
            CrawlPageSemanticProfile.created_at.asc(),
            CrawlPageSemanticProfile.id.asc(),
        )
    ).all()
    rows_by_page_id: dict[int, list[CrawlPageSemanticProfile]] = defaultdict(list)
    for row in existing_rows:
        rows_by_page_id[int(row.page_id)].append(row)

    result = OwnSemanticProfileRefreshResult()
    touched_at = utcnow()
    seen_current_page_ids: set[int] = set()

    for record in resolved_page_records:
        page_id = int(record.get("id") or 0)
        page = pages_by_id.get(page_id)
        if page is None:
            continue
        result.processed_pages += 1

        if not _page_is_profile_eligible(record):
            result.retired_profiles += _retire_current_profiles(rows_by_page_id.get(page_id, []), touched_at=touched_at)
            continue

        top_queries = top_queries_by_page_id.get(page_id, [])
        semantic_card = _build_own_semantic_card(record, top_queries=top_queries)
        semantic_input_hash = _build_own_profile_input_hash(record, top_queries=top_queries)
        page_rows = rows_by_page_id.get(page_id, [])
        current_row = next((row for row in page_rows if row.current), None)
        if (
            current_row is not None
            and current_row.semantic_input_hash == semantic_input_hash
            and current_row.semantic_version == OWN_PAGE_SEMANTIC_PROFILE_VERSION
        ):
            current_row.semantic_card_json = dict(semantic_card)
            current_row.updated_at = touched_at
            result.unchanged_pages += 1
            seen_current_page_ids.add(page_id)
            continue

        result.retired_profiles += _retire_current_profiles(page_rows, touched_at=touched_at)
        target_row = next(
            (row for row in page_rows if row.semantic_input_hash == semantic_input_hash),
            None,
        )
        if target_row is None:
            target_row = CrawlPageSemanticProfile(
                site_id=site_id,
                crawl_job_id=crawl_job_id,
                page_id=page_id,
                semantic_input_hash=semantic_input_hash,
                semantic_version=OWN_PAGE_SEMANTIC_PROFILE_VERSION,
                llm_provider=None,
                llm_model=None,
                prompt_version=None,
                semantic_card_json=dict(semantic_card),
                current=True,
            )
            session.add(target_row)
            page_rows.append(target_row)
            result.inserted_profiles += 1
        else:
            target_row.semantic_version = OWN_PAGE_SEMANTIC_PROFILE_VERSION
            target_row.semantic_card_json = dict(semantic_card)
            target_row.current = True
            target_row.updated_at = touched_at
            result.updated_profiles += 1
        seen_current_page_ids.add(page_id)

    session.flush()
    result.current_profiles_count = int(
        session.scalar(
            select(func.count())
            .select_from(CrawlPageSemanticProfile)
            .where(
                CrawlPageSemanticProfile.site_id == site_id,
                CrawlPageSemanticProfile.crawl_job_id == crawl_job_id,
                CrawlPageSemanticProfile.current.is_(True),
            )
        )
        or len(seen_current_page_ids)
    )
    return result


def load_current_own_page_semantic_profiles(
    session: Session,
    site_id: int,
    crawl_job_id: int,
    *,
    gsc_date_range: str = "last_28_days",
    page_records: list[dict[str, Any]] | None = None,
    refresh_mode: Literal["always", "if_missing"] = "always",
) -> list[CrawlPageSemanticProfile]:
    if refresh_mode == "if_missing":
        current_rows = session.scalars(
            select(CrawlPageSemanticProfile)
            .where(
                CrawlPageSemanticProfile.site_id == site_id,
                CrawlPageSemanticProfile.crawl_job_id == crawl_job_id,
                CrawlPageSemanticProfile.current.is_(True),
            )
            .order_by(CrawlPageSemanticProfile.page_id.asc())
        ).all()
        if current_rows:
            return current_rows
    ensure_current_own_page_semantic_profiles(
        session,
        site_id,
        crawl_job_id,
        gsc_date_range=gsc_date_range,
        page_records=page_records,
    )
    return session.scalars(
        select(CrawlPageSemanticProfile)
        .where(
            CrawlPageSemanticProfile.site_id == site_id,
            CrawlPageSemanticProfile.crawl_job_id == crawl_job_id,
            CrawlPageSemanticProfile.current.is_(True),
        )
        .order_by(CrawlPageSemanticProfile.page_id.asc())
    ).all()


def _page_is_profile_eligible(record: dict[str, Any]) -> bool:
    page_type = str(record.get("page_type") or "other")
    page_bucket = str(record.get("page_bucket") or "other")
    status_code = int(record.get("status_code") or 0)
    if status_code and status_code >= 400:
        return False
    if page_type in OWN_PROFILE_EXCLUDED_PAGE_TYPES:
        return False
    if page_bucket in OWN_PROFILE_EXCLUDED_BUCKETS:
        return False
    title = collapse_whitespace(record.get("title"))
    h1 = collapse_whitespace(record.get("h1"))
    if not title and not h1 and not collapse_whitespace(record.get("normalized_url")):
        return False
    return True


def _build_own_semantic_card(record: dict[str, Any], *, top_queries: Sequence[str]) -> dict[str, Any]:
    title = collapse_whitespace(record.get("title"))
    h1 = collapse_whitespace(record.get("h1"))
    meta_description = collapse_whitespace(record.get("meta_description"))
    page_type = str(record.get("page_type") or "other")
    page_bucket = str(record.get("page_bucket") or "other")
    topic_labels = dedupe_preserve_order(
        value
        for value in [h1, title, *top_queries[:2]]
        if collapse_whitespace(value)
    )
    primary_topic = topic_labels[0] if topic_labels else _topic_from_url(record.get("normalized_url"))
    supporting_subtopics = dedupe_preserve_order(top_queries[1:4])
    evidence_snippets = dedupe_preserve_order(
        value
        for value in [title, h1, meta_description, *top_queries[:2]]
        if collapse_whitespace(value)
    )[:4]
    dominant_intent = _resolve_dominant_intent(page_type=page_type, page_bucket=page_bucket)
    page_role = _resolve_page_role(page_type)
    content_format = _resolve_content_format(page_type)
    commerciality = _resolve_commerciality(page_type=page_type, page_bucket=page_bucket)
    geo_scope = _resolve_geo_scope(record, top_queries=top_queries)
    return build_semantic_card(
        primary_topic=primary_topic,
        topic_labels=topic_labels,
        core_problem=meta_description or primary_topic,
        dominant_intent=dominant_intent,
        secondary_intents=_resolve_secondary_intents(page_type=page_type, page_bucket=page_bucket),
        page_role=page_role,
        content_format=content_format,
        target_audience=_resolve_target_audience(top_queries=top_queries),
        entities=_extract_entities(title, h1, top_queries),
        geo_scope=geo_scope,
        supporting_subtopics=supporting_subtopics,
        what_this_page_is_about=meta_description or primary_topic,
        what_this_page_is_not_about=_resolve_negative_scope(page_type=page_type, page_bucket=page_bucket),
        commerciality=commerciality,
        evidence_snippets=evidence_snippets,
        confidence=_resolve_confidence(record, top_queries=top_queries),
        semantic_version=OWN_PAGE_SEMANTIC_PROFILE_VERSION,
    )


def _build_own_profile_input_hash(record: dict[str, Any], *, top_queries: Sequence[str]) -> str:
    payload = {
        "normalized_url": normalize_text_for_hash(record.get("normalized_url")),
        "title": normalize_text_for_hash(record.get("title")),
        "meta_description": normalize_text_for_hash(record.get("meta_description")),
        "h1": normalize_text_for_hash(record.get("h1")),
        "page_type": normalize_text_for_hash(record.get("page_type")),
        "page_bucket": normalize_text_for_hash(record.get("page_bucket")),
        "page_type_version": normalize_text_for_hash(record.get("page_type_version")),
        "word_count": int(record.get("word_count") or 0),
        "schema_types": sorted(
            normalize_text_for_hash(value)
            for value in (record.get("schema_types_json") or [])
            if normalize_text_for_hash(value)
        ),
        "top_queries": sorted(
            normalize_text_for_hash(value)
            for value in top_queries
            if normalize_text_for_hash(value)
        ),
        "semantic_version": OWN_PAGE_SEMANTIC_PROFILE_VERSION,
    }
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _retire_current_profiles(rows: Sequence[CrawlPageSemanticProfile], *, touched_at: Any) -> int:
    retired = 0
    for row in rows:
        if not row.current:
            continue
        row.current = False
        row.updated_at = touched_at
        retired += 1
    return retired


def _load_top_queries_by_page_id(
    session: Session,
    *,
    crawl_job_id: int,
    page_ids: Sequence[int],
    date_range_label: str,
) -> dict[int, list[str]]:
    if not page_ids:
        return {}
    rows = session.scalars(
        select(GscTopQuery)
        .where(
            GscTopQuery.crawl_job_id == crawl_job_id,
            GscTopQuery.page_id.in_(list(page_ids)),
            GscTopQuery.date_range_label == date_range_label,
        )
        .order_by(
            GscTopQuery.page_id.asc(),
            GscTopQuery.clicks.desc(),
            GscTopQuery.impressions.desc(),
            GscTopQuery.id.asc(),
        )
    ).all()
    grouped: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        page_id = int(row.page_id or 0)
        query = collapse_whitespace(row.query)
        if not page_id or not query:
            continue
        if len(grouped[page_id]) >= OWN_QUERY_LIMIT:
            continue
        grouped[page_id].append(query)
    return grouped


def _resolve_dominant_intent(*, page_type: str, page_bucket: str) -> str:
    if page_bucket == "commercial" or page_type in {"service", "product", "category", "location", "home"}:
        return "commercial"
    if page_bucket == "informational" or page_type in {"blog_article", "blog_index", "faq"}:
        return "informational"
    if page_type in {"about", "contact"}:
        return "navigational"
    return "other"


def _resolve_secondary_intents(*, page_type: str, page_bucket: str) -> list[str]:
    secondary: list[str] = []
    if page_type in {"faq", "blog_article", "blog_index"}:
        secondary.append("commercial")
    if page_bucket == "commercial":
        secondary.append("informational")
    return dedupe_preserve_order(secondary)[:3]


def _resolve_page_role(page_type: str) -> str:
    if page_type in {"service", "product", "category", "location", "home"}:
        return "money_page"
    if page_type in {"blog_article", "faq"}:
        return "supporting_page"
    if page_type == "blog_index":
        return "hub_page"
    if page_type in {"about", "contact", "legal"}:
        return "trust_page"
    if page_type == "utility":
        return "utility_page"
    return "other"


def _resolve_content_format(page_type: str) -> str:
    mapping = {
        "service": "service_page",
        "product": "product",
        "category": "category",
        "location": "location",
        "blog_article": "blog_article",
        "blog_index": "blog_index",
        "faq": "faq",
        "about": "about",
        "contact": "contact",
        "legal": "legal",
        "utility": "utility",
    }
    return mapping.get(page_type, "other")


def _resolve_commerciality(*, page_type: str, page_bucket: str) -> str:
    if page_type in {"service", "product", "category", "location", "home"} or page_bucket == "commercial":
        return "high"
    if page_type in {"faq", "blog_index"}:
        return "medium"
    if page_type == "blog_article" or page_bucket == "informational":
        return "low"
    return "neutral"


def _resolve_target_audience(*, top_queries: Sequence[str]) -> str | None:
    if not top_queries:
        return None
    candidate = collapse_whitespace(top_queries[0])
    return candidate[:280] if candidate else None


def _resolve_geo_scope(record: dict[str, Any], *, top_queries: Sequence[str]) -> str | None:
    normalized_url = str(record.get("normalized_url") or "")
    tokens = tokenize_topic_text(normalized_url)
    for token in tokens:
        if len(token) >= 4 and token not in {"service", "services", "blog", "guide", "about"}:
            if token in {
                "warsaw",
                "krakow",
                "gdansk",
                "wroclaw",
                "poznan",
                "lodz",
                "berlin",
                "london",
                "paris",
            }:
                return token.title()
    for query in top_queries:
        query_tokens = tokenize_topic_text(query)
        for token in query_tokens:
            if token in {
                "warsaw",
                "krakow",
                "gdansk",
                "wroclaw",
                "poznan",
                "lodz",
                "poland",
                "germany",
                "uk",
            }:
                return token.title()
    return None


def _extract_entities(title: str | None, h1: str | None, top_queries: Sequence[str]) -> list[str]:
    values = [title, h1, *top_queries[:3]]
    entities: list[str] = []
    for value in values:
        cleaned = collapse_whitespace(value)
        if not cleaned:
            continue
        tokens = tokenize_topic_text(cleaned)
        if not tokens:
            continue
        normalized = " ".join(tokens[:3]).strip()
        if normalized:
            entities.append(normalized.title())
    return dedupe_preserve_order(entities)[:6]


def _resolve_negative_scope(*, page_type: str, page_bucket: str) -> str:
    if page_type in {"service", "product", "category", "location"}:
        return "Not a broad informational support article."
    if page_bucket == "informational" or page_type in {"blog_article", "blog_index", "faq"}:
        return "Not a conversion-focused money page."
    return "Not a site-wide utility or legal page."


def _resolve_confidence(record: dict[str, Any], *, top_queries: Sequence[str]) -> float:
    confidence = 0.58
    if collapse_whitespace(record.get("title")):
        confidence += 0.1
    if collapse_whitespace(record.get("h1")):
        confidence += 0.1
    if int(record.get("word_count") or 0) >= 250:
        confidence += 0.06
    if top_queries:
        confidence += min(0.12, len(top_queries) * 0.03)
    if record.get("page_type"):
        confidence += 0.04
    return round(min(0.92, confidence), 2)


def _topic_from_url(url: Any) -> str:
    tokens = tokenize_topic_text(str(url or ""))
    if not tokens:
        return "Untitled page"
    return " ".join(tokens[:4]).title()
