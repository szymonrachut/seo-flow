from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.text_processing import normalize_ascii
from app.db.models import GscTopQuery, GscUrlMetric, Page
from app.services import site_service


NORMALIZE_MATCH_RE = re.compile(r"[^a-z0-9]+")
PREFERRED_GSC_DATE_RANGES = ("last_28_days", "last_90_days")
TITLE_EXACT_SCORE = 85
H1_EXACT_SCORE = 85
TITLE_ALL_TOKENS_SCORE = 72
H1_ALL_TOKENS_SCORE = 72
TITLE_PARTIAL_SCORE = 38
H1_PARTIAL_SCORE = 38
URL_EXACT_SCORE = 52
URL_ALL_TOKENS_SCORE = 40
URL_PARTIAL_SCORE = 26
META_EXACT_SCORE = 45
META_ALL_TOKENS_SCORE = 34
META_PARTIAL_SCORE = 24
MIN_WEAK_COVERAGE_SCORE = 25
MIN_COVERED_SCORE = 70


@dataclass(slots=True)
class CoveragePageCandidate:
    page_id: int
    url: str
    title: str | None
    normalized_title: str
    normalized_h1: str
    normalized_meta_description: str
    normalized_url_text: str


@dataclass(slots=True)
class GscMetricSignal:
    clicks: int
    impressions: int
    ctr: float | None
    avg_position: float | None


@dataclass(slots=True)
class GscQuerySignal:
    page_id: int | None
    query: str
    normalized_query: str
    clicks: int
    impressions: int
    ctr: float | None
    position: float | None


@dataclass(slots=True)
class SiteCoverageContext:
    site_id: int
    active_crawl_id: int | None
    pages: list[CoveragePageCandidate]
    url_metrics_by_page_id: dict[int, GscMetricSignal]
    top_queries: list[GscQuerySignal]


def build_site_coverage_context(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
) -> SiteCoverageContext:
    workspace = site_service.resolve_site_workspace_context(
        session,
        site_id,
        active_crawl_id=active_crawl_id,
    )
    active_crawl = workspace["active_crawl"]
    if active_crawl is None:
        return SiteCoverageContext(
            site_id=site_id,
            active_crawl_id=None,
            pages=[],
            url_metrics_by_page_id={},
            top_queries=[],
        )

    pages = session.scalars(
        select(Page)
        .where(
            Page.crawl_job_id == active_crawl.id,
            Page.is_internal.is_(True),
        )
        .order_by(Page.id.asc())
    ).all()
    page_candidates = [
        CoveragePageCandidate(
            page_id=int(page.id),
            url=str(page.final_url or page.normalized_url or page.url),
            title=page.title,
            normalized_title=_normalize_match_text(page.title),
            normalized_h1=_normalize_match_text(page.h1),
            normalized_meta_description=_normalize_match_text(page.meta_description),
            normalized_url_text=_normalize_match_text(page.final_url or page.normalized_url or page.url),
        )
        for page in pages
    ]
    return SiteCoverageContext(
        site_id=site_id,
        active_crawl_id=int(active_crawl.id),
        pages=page_candidates,
        url_metrics_by_page_id=_load_url_metrics_by_page_id(session, crawl_job_id=int(active_crawl.id)),
        top_queries=_load_top_queries(session, crawl_job_id=int(active_crawl.id)),
    )


def evaluate_keyword_coverage(
    context: SiteCoverageContext,
    keyword: str,
) -> dict[str, Any]:
    normalized_keyword = _normalize_match_text(keyword)
    keyword_tokens = _tokenize(normalized_keyword)
    if not context.pages or not normalized_keyword or not keyword_tokens:
        return {
            "coverage_status": "missing",
            "matched_pages_count": 0,
            "best_match_page": None,
            "coverage_score_v1": 0,
        }

    matches: list[dict[str, Any]] = []
    for page in context.pages:
        match = _score_page_match(page, normalized_keyword=normalized_keyword, keyword_tokens=keyword_tokens)
        if match["coverage_score_v1"] > 0:
            matches.append(match)

    if not matches:
        return {
            "coverage_status": "missing",
            "matched_pages_count": 0,
            "best_match_page": None,
            "coverage_score_v1": 0,
        }

    matches.sort(
        key=lambda item: (
            -int(item["coverage_score_v1"]),
            int(item["page_id"]),
        )
    )
    best_match = matches[0]
    best_score = int(best_match["coverage_score_v1"])
    matched_pages = [item for item in matches if int(item["coverage_score_v1"]) >= MIN_WEAK_COVERAGE_SCORE]

    if best_score >= MIN_COVERED_SCORE or _has_strong_coverage_signal(best_match["match_signals"]):
        coverage_status = "covered"
    elif best_score >= MIN_WEAK_COVERAGE_SCORE:
        coverage_status = "weak_coverage"
    else:
        coverage_status = "missing"

    if coverage_status == "missing":
        return {
            "coverage_status": "missing",
            "matched_pages_count": 0,
            "best_match_page": None,
            "coverage_score_v1": 0,
        }

    return {
        "coverage_status": coverage_status,
        "matched_pages_count": len(matched_pages),
        "best_match_page": {
            "page_id": best_match["page_id"],
            "url": best_match["url"],
            "title": best_match["title"],
            "match_signals": list(best_match["match_signals"]),
        },
        "coverage_score_v1": best_score,
    }


def _score_page_match(
    page: CoveragePageCandidate,
    *,
    normalized_keyword: str,
    keyword_tokens: list[str],
) -> dict[str, Any]:
    signals: list[str] = []
    score = 0
    score = _merge_field_signal(
        score,
        signals,
        field_name="title",
        text=page.normalized_title,
        normalized_keyword=normalized_keyword,
        keyword_tokens=keyword_tokens,
        exact_score=TITLE_EXACT_SCORE,
        all_tokens_score=TITLE_ALL_TOKENS_SCORE,
        partial_score=TITLE_PARTIAL_SCORE,
    )
    score = _merge_field_signal(
        score,
        signals,
        field_name="h1",
        text=page.normalized_h1,
        normalized_keyword=normalized_keyword,
        keyword_tokens=keyword_tokens,
        exact_score=H1_EXACT_SCORE,
        all_tokens_score=H1_ALL_TOKENS_SCORE,
        partial_score=H1_PARTIAL_SCORE,
    )
    score = _merge_field_signal(
        score,
        signals,
        field_name="url",
        text=page.normalized_url_text,
        normalized_keyword=normalized_keyword,
        keyword_tokens=keyword_tokens,
        exact_score=URL_EXACT_SCORE,
        all_tokens_score=URL_ALL_TOKENS_SCORE,
        partial_score=URL_PARTIAL_SCORE,
    )
    score = _merge_field_signal(
        score,
        signals,
        field_name="meta",
        text=page.normalized_meta_description,
        normalized_keyword=normalized_keyword,
        keyword_tokens=keyword_tokens,
        exact_score=META_EXACT_SCORE,
        all_tokens_score=META_ALL_TOKENS_SCORE,
        partial_score=META_PARTIAL_SCORE,
    )

    field_names = {signal.split("_", 1)[0] for signal in signals}
    if {"title", "h1"} & field_names and len(field_names) >= 2:
        score = min(100, score + 10)
    elif len(field_names) >= 2:
        score = min(100, score + 5)

    return {
        "page_id": page.page_id,
        "url": page.url,
        "title": page.title,
        "match_signals": signals,
        "coverage_score_v1": score,
    }


def evaluate_keyword_gsc_signal(
    context: SiteCoverageContext,
    keyword: str,
    *,
    best_match_page_id: int | None,
) -> dict[str, Any]:
    normalized_keyword = _normalize_match_text(keyword)
    if not normalized_keyword:
        return {
            "gsc_signal_status": "none",
            "gsc_summary": None,
        }

    page_metric = context.url_metrics_by_page_id.get(int(best_match_page_id)) if best_match_page_id else None
    preferred_rows = [row for row in context.top_queries if row.page_id == best_match_page_id] if best_match_page_id else []
    exact_rows = [row for row in preferred_rows if row.normalized_query == normalized_keyword]
    weak_rows = [
        row
        for row in preferred_rows
        if row.normalized_query != normalized_keyword and _is_contains_match(row.normalized_query, normalized_keyword)
    ]
    if not exact_rows and not weak_rows:
        exact_rows = [row for row in context.top_queries if row.normalized_query == normalized_keyword]
        weak_rows = [
            row
            for row in context.top_queries
            if row.normalized_query != normalized_keyword and _is_contains_match(row.normalized_query, normalized_keyword)
        ]

    if exact_rows:
        return {
            "gsc_signal_status": "present",
            "gsc_summary": _aggregate_query_rows(exact_rows),
        }
    if weak_rows:
        return {
            "gsc_signal_status": "weak",
            "gsc_summary": _aggregate_query_rows(weak_rows),
        }
    if page_metric is not None:
        return {
            "gsc_signal_status": "weak",
            "gsc_summary": {
                "clicks": page_metric.clicks,
                "impressions": page_metric.impressions,
                "ctr": page_metric.ctr,
                "avg_position": page_metric.avg_position,
            },
        }
    return {
        "gsc_signal_status": "none",
        "gsc_summary": None,
    }


def _load_url_metrics_by_page_id(session: Session, *, crawl_job_id: int) -> dict[int, GscMetricSignal]:
    rows = session.scalars(
        select(GscUrlMetric)
        .where(
            GscUrlMetric.crawl_job_id == crawl_job_id,
            GscUrlMetric.page_id.is_not(None),
        )
        .order_by(GscUrlMetric.id.asc())
    ).all()
    selected: dict[int, tuple[int, GscMetricSignal]] = {}
    for row in rows:
        if row.page_id is None:
            continue
        priority = _date_range_priority(row.date_range_label)
        signal = GscMetricSignal(
            clicks=int(row.clicks),
            impressions=int(row.impressions),
            ctr=float(row.ctr) if row.ctr is not None else None,
            avg_position=float(row.position) if row.position is not None else None,
        )
        existing = selected.get(int(row.page_id))
        if existing is None or priority < existing[0]:
            selected[int(row.page_id)] = (priority, signal)
    return {page_id: payload[1] for page_id, payload in selected.items()}


def _load_top_queries(session: Session, *, crawl_job_id: int) -> list[GscQuerySignal]:
    rows = session.scalars(
        select(GscTopQuery)
        .where(GscTopQuery.crawl_job_id == crawl_job_id)
        .order_by(GscTopQuery.id.asc())
    ).all()
    available_labels = {str(row.date_range_label) for row in rows}
    preferred_label = next((label for label in PREFERRED_GSC_DATE_RANGES if label in available_labels), None)
    return [
        GscQuerySignal(
            page_id=int(row.page_id) if row.page_id is not None else None,
            query=row.query,
            normalized_query=_normalize_match_text(row.query),
            clicks=int(row.clicks),
            impressions=int(row.impressions),
            ctr=float(row.ctr) if row.ctr is not None else None,
            position=float(row.position) if row.position is not None else None,
        )
        for row in rows
        if preferred_label is None or str(row.date_range_label) == preferred_label
    ]


def _merge_field_signal(
    current_score: int,
    signals: list[str],
    *,
    field_name: str,
    text: str,
    normalized_keyword: str,
    keyword_tokens: list[str],
    exact_score: int,
    all_tokens_score: int,
    partial_score: int,
) -> int:
    if not text:
        return current_score
    if _contains_phrase(text, normalized_keyword):
        signals.append(f"{field_name}_exact")
        return max(current_score, exact_score)

    token_set = set(_tokenize(text))
    if len(keyword_tokens) > 1 and all(token in token_set for token in keyword_tokens):
        signals.append(f"{field_name}_all_tokens")
        return max(current_score, all_tokens_score)

    if len(keyword_tokens) >= 3:
        matched_tokens = sum(1 for token in keyword_tokens if token in token_set)
        if matched_tokens >= len(keyword_tokens) - 1:
            signals.append(f"{field_name}_partial")
            return max(current_score, partial_score)
    return current_score


def _aggregate_query_rows(rows: list[GscQuerySignal]) -> dict[str, Any]:
    clicks = sum(int(row.clicks) for row in rows)
    impressions = sum(int(row.impressions) for row in rows)
    avg_position = None
    weighted_position = sum(float(row.position or 0.0) * max(1, int(row.impressions)) for row in rows if row.position is not None)
    weighted_impressions = sum(max(1, int(row.impressions)) for row in rows if row.position is not None)
    if weighted_impressions > 0:
        avg_position = round(weighted_position / weighted_impressions, 2)
    ctr = round(clicks / impressions, 4) if impressions > 0 else None
    return {
        "clicks": clicks,
        "impressions": impressions,
        "ctr": ctr,
        "avg_position": avg_position,
    }


def _has_strong_coverage_signal(signals: list[str]) -> bool:
    return any(signal in {"title_exact", "title_all_tokens", "h1_exact", "h1_all_tokens"} for signal in signals)


def _contains_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    return f" {phrase} " in f" {text} "


def _is_contains_match(query_text: str, keyword_text: str) -> bool:
    if not query_text or not keyword_text:
        return False
    return _contains_phrase(query_text, keyword_text) or _contains_phrase(keyword_text, query_text)


def _date_range_priority(value: str | None) -> int:
    if value is None:
        return len(PREFERRED_GSC_DATE_RANGES) + 1
    try:
        return PREFERRED_GSC_DATE_RANGES.index(str(value))
    except ValueError:
        return len(PREFERRED_GSC_DATE_RANGES)


def _tokenize(value: str) -> list[str]:
    return [token for token in value.split(" ") if token]


def _normalize_match_text(value: str | None) -> str:
    ascii_value = normalize_ascii(value).lower()
    collapsed = NORMALIZE_MATCH_RE.sub(" ", ascii_value)
    return " ".join(part for part in collapsed.split(" ") if part)
