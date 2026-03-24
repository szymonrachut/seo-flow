from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CrawlJob, GscTopQuery
from app.schemas.opportunities import ImpactLevel
from app.services.cannibalization_rules import (
    CannibalizationRecommendationType,
    CannibalizationRules,
    CannibalizationSeverity,
    get_cannibalization_rules,
)
from app.services.priority_service import apply_priority_metadata
from app.services.seo_analysis import build_page_records, text_value_missing

GSC_DATE_RANGE_SUFFIX = {
    "last_28_days": "28d",
    "last_90_days": "90d",
}
SEVERITY_ORDER: dict[CannibalizationSeverity, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}
IMPACT_ORDER: dict[ImpactLevel, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
}
WHITESPACE_RE = re.compile(r"\s+")


class CannibalizationServiceError(RuntimeError):
    pass


@dataclass(slots=True)
class QueryMetric:
    normalized_query: str
    display_query: str
    clicks: int = 0
    impressions: int = 0
    position_weighted_sum: float = 0.0
    position_weight: float = 0.0
    best_impressions: int = 0
    best_clicks: int = 0

    def add(self, *, query: str, clicks: int, impressions: int, position: float | None) -> None:
        self.clicks += int(clicks)
        self.impressions += int(impressions)

        position_weight = max(int(impressions), 1)
        if position is not None:
            self.position_weighted_sum += float(position) * position_weight
            self.position_weight += position_weight

        if (
            int(impressions) > self.best_impressions
            or (int(impressions) == self.best_impressions and int(clicks) > self.best_clicks)
            or (int(impressions) == self.best_impressions and int(clicks) == self.best_clicks and len(query) < len(self.display_query))
        ):
            self.display_query = query
            self.best_impressions = int(impressions)
            self.best_clicks = int(clicks)

    @property
    def average_position(self) -> float | None:
        if self.position_weight <= 0:
            return None
        return self.position_weighted_sum / self.position_weight


@dataclass(slots=True)
class PageQueryProfile:
    page_id: int
    url: str
    normalized_url: str
    priority_score: int
    priority_level: str
    priority_rationale: str
    primary_opportunity_type: str | None
    clicks: int
    impressions: int
    ctr: float
    position: float | None
    queries: dict[str, QueryMetric] = field(default_factory=dict)

    @property
    def total_query_impressions(self) -> int:
        return sum(int(metric.impressions) for metric in self.queries.values())

    @property
    def total_query_clicks(self) -> int:
        return sum(int(metric.clicks) for metric in self.queries.values())

    @property
    def query_count(self) -> int:
        return len(self.queries)


@dataclass(slots=True)
class PairAccumulator:
    page_a_id: int
    page_b_id: int
    query_keys: set[str] = field(default_factory=set)
    shared_query_impressions: int = 0
    shared_query_clicks: int = 0


class UnionFind:
    def __init__(self) -> None:
        self.parents: dict[int, int] = {}

    def add(self, value: int) -> None:
        self.parents.setdefault(value, value)

    def find(self, value: int) -> int:
        parent = self.parents.setdefault(value, value)
        if parent != value:
            self.parents[value] = self.find(parent)
        return self.parents[value]

    def union(self, left: int, right: int) -> None:
        self.add(left)
        self.add(right)
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parents[right_root] = left_root


def build_cannibalization_report(
    session: Session,
    crawl_job_id: int,
    *,
    gsc_date_range: str = "last_28_days",
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "severity",
    sort_order: str = "desc",
    severity: CannibalizationSeverity | None = None,
    impact_level: ImpactLevel | None = None,
    recommendation_type: CannibalizationRecommendationType | None = None,
    has_clear_primary: bool | None = None,
    url_contains: str | None = None,
    rules: CannibalizationRules | None = None,
) -> dict[str, Any]:
    dataset = _build_cannibalization_dataset(
        session,
        crawl_job_id,
        gsc_date_range=gsc_date_range,
        rules=rules,
    )
    rows = _filter_cluster_rows(
        dataset["clusters"],
        severity=severity,
        impact_level=impact_level,
        recommendation_type=recommendation_type,
        has_clear_primary=has_clear_primary,
        url_contains=url_contains,
    )
    _sort_cluster_rows(rows, sort_by=sort_by, sort_order=sort_order)

    total_items = len(rows)
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "summary": dataset["summary"],
        "items": rows[start:end],
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


def get_all_cannibalization_cluster_rows(
    session: Session,
    crawl_job_id: int,
    *,
    gsc_date_range: str = "last_28_days",
    sort_by: str = "severity",
    sort_order: str = "desc",
    severity: CannibalizationSeverity | None = None,
    impact_level: ImpactLevel | None = None,
    recommendation_type: CannibalizationRecommendationType | None = None,
    has_clear_primary: bool | None = None,
    url_contains: str | None = None,
    rules: CannibalizationRules | None = None,
) -> list[dict[str, Any]]:
    dataset = _build_cannibalization_dataset(
        session,
        crawl_job_id,
        gsc_date_range=gsc_date_range,
        rules=rules,
    )
    rows = _filter_cluster_rows(
        dataset["clusters"],
        severity=severity,
        impact_level=impact_level,
        recommendation_type=recommendation_type,
        has_clear_primary=has_clear_primary,
        url_contains=url_contains,
    )
    _sort_cluster_rows(rows, sort_by=sort_by, sort_order=sort_order)
    return rows


def build_cannibalization_page_details(
    session: Session,
    crawl_job_id: int,
    page_id: int,
    *,
    gsc_date_range: str = "last_28_days",
    rules: CannibalizationRules | None = None,
) -> dict[str, Any]:
    dataset = _build_cannibalization_dataset(
        session,
        crawl_job_id,
        gsc_date_range=gsc_date_range,
        rules=rules,
    )
    details = dataset["page_details"].get(page_id)
    if details is None:
        raise CannibalizationServiceError(f"Page {page_id} was not found in crawl job {crawl_job_id}.")
    return details


def apply_cannibalization_page_metadata(
    session: Session,
    crawl_job_id: int,
    page_records: list[dict[str, Any]],
    *,
    gsc_date_range: str = "last_28_days",
    rules: CannibalizationRules | None = None,
) -> None:
    dataset = _build_cannibalization_dataset(
        session,
        crawl_job_id,
        gsc_date_range=gsc_date_range,
        rules=rules,
        page_records=page_records,
    )
    page_details = dataset["page_details"]
    for record in page_records:
        metadata = page_details.get(int(record["id"]))
        if metadata is None:
            _apply_default_page_metadata(record)
            continue
        _apply_page_metadata(record, metadata)


def _build_cannibalization_dataset(
    session: Session,
    crawl_job_id: int,
    *,
    gsc_date_range: str,
    rules: CannibalizationRules | None = None,
    page_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    resolved_rules = rules or get_cannibalization_rules()
    crawl_job = session.get(CrawlJob, crawl_job_id)
    if crawl_job is None:
        raise CannibalizationServiceError(f"Crawl job {crawl_job_id} not found.")

    resolved_page_records = [dict(record) for record in page_records] if page_records is not None else build_page_records(session, crawl_job_id)
    if page_records is None:
        apply_priority_metadata(resolved_page_records, gsc_date_range=gsc_date_range)

    internal_page_records = [record for record in resolved_page_records if bool(record.get("is_internal"))]
    page_lookup = {int(record["id"]): record for record in internal_page_records}

    profiles = _build_page_query_profiles(
        session,
        crawl_job_id,
        gsc_date_range=gsc_date_range,
        page_lookup=page_lookup,
        rules=resolved_rules,
    )
    pair_relations = _build_pair_relations(profiles, resolved_rules)
    relevant_pairs = [relation for relation in pair_relations if bool(relation["is_relevant"])]
    page_overlaps = _build_page_overlaps(profiles, relevant_pairs)
    clusters = _build_clusters(
        crawl_job_id=crawl_job_id,
        profiles=profiles,
        relevant_pairs=relevant_pairs,
        page_overlaps=page_overlaps,
        rules=resolved_rules,
    )
    page_details = _build_page_details(
        crawl_job_id=crawl_job_id,
        gsc_date_range=gsc_date_range,
        page_lookup=page_lookup,
        page_overlaps=page_overlaps,
        clusters=clusters,
    )
    summary = _build_summary(
        crawl_job_id=crawl_job_id,
        gsc_date_range=gsc_date_range,
        profiles=profiles,
        clusters=clusters,
    )

    return {
        "summary": summary,
        "clusters": clusters,
        "page_details": page_details,
    }


def _build_page_query_profiles(
    session: Session,
    crawl_job_id: int,
    *,
    gsc_date_range: str,
    page_lookup: dict[int, dict[str, Any]],
    rules: CannibalizationRules,
) -> dict[int, PageQueryProfile]:
    suffix = _resolve_gsc_suffix(gsc_date_range)
    rows = session.scalars(
        select(GscTopQuery)
        .where(
            GscTopQuery.crawl_job_id == crawl_job_id,
            GscTopQuery.date_range_label == gsc_date_range,
            GscTopQuery.page_id.is_not(None),
        )
        .order_by(GscTopQuery.id.asc())
    ).all()

    profiles: dict[int, PageQueryProfile] = {}
    for row in rows:
        if row.page_id is None:
            continue
        page_record = page_lookup.get(int(row.page_id))
        if page_record is None:
            continue

        normalized_query = _normalize_query(row.query)
        if normalized_query is None:
            continue

        clicks = int(row.clicks or 0)
        impressions = int(row.impressions or 0)
        if impressions < rules.min_query_impressions and clicks < rules.min_query_clicks:
            continue

        profile = profiles.get(int(row.page_id))
        if profile is None:
            profile = PageQueryProfile(
                page_id=int(row.page_id),
                url=str(page_record.get("url") or ""),
                normalized_url=str(page_record.get("normalized_url") or ""),
                priority_score=int(page_record.get("priority_score") or 0),
                priority_level=str(page_record.get("priority_level") or "low"),
                priority_rationale=str(page_record.get("priority_rationale") or ""),
                primary_opportunity_type=page_record.get("primary_opportunity_type"),
                clicks=int(page_record.get(f"clicks_{suffix}") or 0),
                impressions=int(page_record.get(f"impressions_{suffix}") or 0),
                ctr=float(page_record.get(f"ctr_{suffix}") or 0.0),
                position=_optional_float(page_record.get(f"position_{suffix}")),
            )
            profiles[profile.page_id] = profile

        metric = profile.queries.get(normalized_query)
        if metric is None:
            metric = QueryMetric(
                normalized_query=normalized_query,
                display_query=str(row.query).strip(),
            )
            profile.queries[normalized_query] = metric

        metric.add(
            query=str(row.query).strip(),
            clicks=clicks,
            impressions=impressions,
            position=_optional_float(row.position),
        )

    return {page_id: profile for page_id, profile in profiles.items() if profile.query_count > 0}


def _build_pair_relations(
    profiles: dict[int, PageQueryProfile],
    rules: CannibalizationRules,
) -> list[dict[str, Any]]:
    query_index: dict[str, list[int]] = defaultdict(list)
    for profile in profiles.values():
        for query_key in profile.queries:
            query_index[query_key].append(profile.page_id)

    accumulators: dict[tuple[int, int], PairAccumulator] = {}
    for query_key, page_ids in query_index.items():
        if len(page_ids) < 2:
            continue

        for left_id, right_id in combinations(sorted(page_ids), 2):
            left_metric = profiles[left_id].queries[query_key]
            right_metric = profiles[right_id].queries[query_key]
            pair_key = (left_id, right_id)
            accumulator = accumulators.get(pair_key)
            if accumulator is None:
                accumulator = PairAccumulator(page_a_id=left_id, page_b_id=right_id)
                accumulators[pair_key] = accumulator
            accumulator.query_keys.add(query_key)
            accumulator.shared_query_impressions += min(int(left_metric.impressions), int(right_metric.impressions))
            accumulator.shared_query_clicks += min(int(left_metric.clicks), int(right_metric.clicks))

    relations: list[dict[str, Any]] = []
    for pair_key in sorted(accumulators):
        accumulator = accumulators[pair_key]
        left = profiles[accumulator.page_a_id]
        right = profiles[accumulator.page_b_id]
        common_queries_count = len(accumulator.query_keys)
        overlap_ratio = _ratio(common_queries_count, min(left.query_count, right.query_count))
        weighted_overlap_by_impressions = _ratio(
            accumulator.shared_query_impressions,
            min(left.total_query_impressions, right.total_query_impressions),
        )
        weighted_overlap_by_clicks = _ratio(
            accumulator.shared_query_clicks,
            min(left.total_query_clicks, right.total_query_clicks),
        )
        pair_overlap_score = (
            weighted_overlap_by_impressions * rules.overlap_impressions_weight
            + weighted_overlap_by_clicks * rules.overlap_clicks_weight
            + overlap_ratio * rules.overlap_query_ratio_weight
        )
        dominant_page_id, dominance_score, dominance_confidence = _compute_pair_dominance(
            left,
            right,
            accumulator.query_keys,
            rules,
        )
        dominant_url = profiles[dominant_page_id].url if dominant_page_id is not None else None

        relation = {
            "page_ids": pair_key,
            "page_a_id": left.page_id,
            "page_b_id": right.page_id,
            "page_a_url": left.url,
            "page_b_url": right.url,
            "query_keys": sorted(accumulator.query_keys),
            "common_queries_count": common_queries_count,
            "weighted_overlap_by_impressions": round(weighted_overlap_by_impressions, 4),
            "weighted_overlap_by_clicks": round(weighted_overlap_by_clicks, 4),
            "overlap_ratio": round(overlap_ratio, 4),
            "pair_overlap_score": round(pair_overlap_score, 4),
            "shared_query_impressions": int(accumulator.shared_query_impressions),
            "shared_query_clicks": int(accumulator.shared_query_clicks),
            "shared_top_queries": _build_query_samples(left, right, accumulator.query_keys, limit=rules.per_url_sample_queries_limit),
            "dominant_page_id": dominant_page_id,
            "dominant_url": dominant_url,
            "dominance_score": round(dominance_score, 4),
            "dominance_confidence": round(dominance_confidence, 4),
        }
        relation["is_relevant"] = _pair_is_relevant(relation, rules)
        relations.append(relation)

    return relations


def _build_page_overlaps(
    profiles: dict[int, PageQueryProfile],
    relevant_pairs: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    page_overlaps: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for relation in relevant_pairs:
        for page_id, competitor_id in (
            (int(relation["page_a_id"]), int(relation["page_b_id"])),
            (int(relation["page_b_id"]), int(relation["page_a_id"])),
        ):
            competitor = profiles[competitor_id]
            page_overlaps[page_id].append(
                {
                    "competing_page_id": competitor.page_id,
                    "competing_url": competitor.url,
                    "common_queries_count": int(relation["common_queries_count"]),
                    "weighted_overlap_by_impressions": float(relation["weighted_overlap_by_impressions"]),
                    "weighted_overlap_by_clicks": float(relation["weighted_overlap_by_clicks"]),
                    "overlap_ratio": float(relation["overlap_ratio"]),
                    "pair_overlap_score": float(relation["pair_overlap_score"]),
                    "shared_query_impressions": int(relation["shared_query_impressions"]),
                    "shared_query_clicks": int(relation["shared_query_clicks"]),
                    "shared_top_queries": list(relation["shared_top_queries"]),
                    "dominant_url": relation["dominant_url"],
                    "dominance_score": float(relation["dominance_score"]),
                    "dominance_confidence": float(relation["dominance_confidence"]),
                    "competitor_priority_score": int(competitor.priority_score),
                    "competitor_priority_level": competitor.priority_level,
                    "competitor_primary_opportunity_type": competitor.primary_opportunity_type,
                    "competitor_clicks": int(competitor.clicks),
                    "competitor_impressions": int(competitor.impressions),
                    "competitor_position": competitor.position,
                }
            )

    for overlaps in page_overlaps.values():
        overlaps.sort(
            key=lambda row: (
                float(row["pair_overlap_score"]),
                int(row["shared_query_impressions"]),
                str(row["competing_url"]).lower(),
            ),
            reverse=True,
        )
    return page_overlaps


def _build_clusters(
    *,
    crawl_job_id: int,
    profiles: dict[int, PageQueryProfile],
    relevant_pairs: list[dict[str, Any]],
    page_overlaps: dict[int, list[dict[str, Any]]],
    rules: CannibalizationRules,
) -> list[dict[str, Any]]:
    if not relevant_pairs:
        return []

    union_find = UnionFind()
    for relation in relevant_pairs:
        left_id = int(relation["page_a_id"])
        right_id = int(relation["page_b_id"])
        union_find.union(left_id, right_id)

    components: dict[int, set[int]] = defaultdict(set)
    for relation in relevant_pairs:
        for page_id in relation["page_ids"]:
            components[union_find.find(int(page_id))].add(int(page_id))

    clusters: list[dict[str, Any]] = []
    for page_ids in sorted(components.values(), key=lambda item: min(item)):
        sorted_page_ids = sorted(page_ids, key=lambda page_id: profiles[page_id].url.lower())
        component_pairs = [
            relation
            for relation in relevant_pairs
            if int(relation["page_a_id"]) in page_ids and int(relation["page_b_id"]) in page_ids
        ]
        cluster_shared_queries = _cluster_shared_queries(component_pairs)
        shared_query_count_by_page = _cluster_shared_query_count_by_page(component_pairs)
        cluster_query_demand = _cluster_query_demand(profiles, sorted_page_ids, cluster_shared_queries)
        dominant_page_id, dominant_url_score, dominant_url_confidence = _compute_cluster_dominance(
            profiles,
            sorted_page_ids,
            shared_query_count_by_page,
            rules,
        )
        dominant_url = profiles[dominant_page_id].url if dominant_page_id is not None else None
        dominant_url_page_id = dominant_page_id
        has_clear_primary = bool(
            dominant_page_id is not None and dominant_url_confidence >= rules.clear_primary_confidence_threshold
        )

        candidate_urls = _build_cluster_candidate_urls(
            profiles=profiles,
            page_ids=sorted_page_ids,
            shared_query_count_by_page=shared_query_count_by_page,
            cluster_shared_queries=cluster_shared_queries,
            cluster_shared_clicks=cluster_query_demand["page_clicks_total"],
            cluster_shared_impressions=cluster_query_demand["page_impressions_total"],
            dominant_page_id=dominant_page_id,
            page_overlaps=page_overlaps,
        )
        weighted_overlap = round(
            sum(float(pair["pair_overlap_score"]) for pair in component_pairs) / len(component_pairs),
            4,
        )
        impact_level = _classify_impact_level(
            shared_impressions=int(cluster_query_demand["demand_impressions"]),
            shared_clicks=int(cluster_query_demand["demand_clicks"]),
            rules=rules,
        )
        recommendation_type = _classify_recommendation(
            candidate_urls=candidate_urls,
            weighted_overlap=weighted_overlap,
            impact_level=impact_level,
            has_clear_primary=has_clear_primary,
            shared_impressions=int(cluster_query_demand["demand_impressions"]),
            shared_clicks=int(cluster_query_demand["demand_clicks"]),
            rules=rules,
        )
        severity_score = _compute_severity_score(
            candidate_urls=candidate_urls,
            weighted_overlap=weighted_overlap,
            shared_queries_count=len(cluster_shared_queries),
            impact_level=impact_level,
            recommendation_type=recommendation_type,
            rules=rules,
        )
        severity = _resolve_severity_from_score(severity_score, rules)
        rationale = _build_cluster_rationale(
            recommendation_type=recommendation_type,
            severity=severity,
            impact_level=impact_level,
            weighted_overlap=weighted_overlap,
            shared_impressions=int(cluster_query_demand["demand_impressions"]),
            shared_clicks=int(cluster_query_demand["demand_clicks"]),
            dominant_url=dominant_url,
            dominant_url_confidence=dominant_url_confidence,
            shared_queries_count=len(cluster_shared_queries),
        )

        cluster_row = {
            "cluster_id": f"cannibalization-{crawl_job_id}-{min(sorted_page_ids)}",
            "urls_count": len(sorted_page_ids),
            "shared_queries_count": len(cluster_shared_queries),
            "shared_query_impressions": int(cluster_query_demand["demand_impressions"]),
            "shared_query_clicks": int(cluster_query_demand["demand_clicks"]),
            "weighted_overlap": weighted_overlap,
            "severity": severity,
            "severity_score": severity_score,
            "impact_level": impact_level,
            "recommendation_type": recommendation_type,
            "has_clear_primary": has_clear_primary,
            "dominant_url": dominant_url,
            "dominant_url_page_id": dominant_url_page_id,
            "dominant_url_confidence": round(dominant_url_confidence, 4),
            "dominant_url_score": round(dominant_url_score, 4),
            "sample_queries": _cluster_sample_queries(
                profiles,
                sorted_page_ids,
                cluster_shared_queries,
                limit=rules.cluster_sample_queries_limit,
            ),
            "candidate_urls": candidate_urls,
            "rationale": rationale,
            "page_ids": sorted_page_ids,
        }
        clusters.append(cluster_row)

    clusters.sort(
        key=lambda row: (
            SEVERITY_ORDER.get(str(row["severity"]), 0),
            IMPACT_ORDER.get(str(row["impact_level"]), 0),
            float(row["weighted_overlap"]),
            int(row["shared_query_impressions"]),
            str(row["cluster_id"]).lower(),
        ),
        reverse=True,
    )
    return clusters


def _build_page_details(
    *,
    crawl_job_id: int,
    gsc_date_range: str,
    page_lookup: dict[int, dict[str, Any]],
    page_overlaps: dict[int, list[dict[str, Any]]],
    clusters: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    details: dict[int, dict[str, Any]] = {}
    cluster_by_page: dict[int, dict[str, Any]] = {}
    for cluster in clusters:
        for page_id in cluster["page_ids"]:
            cluster_by_page[int(page_id)] = cluster

    for page_id, page_record in page_lookup.items():
        overlaps = list(page_overlaps.get(page_id) or [])
        strongest_overlap = overlaps[0] if overlaps else None
        cluster = cluster_by_page.get(page_id)
        dominant_competing_url: str | None = None
        dominant_competing_page_id: int | None = None
        if cluster is not None:
            dominant_url_page_id = cluster.get("dominant_url_page_id")
            if dominant_url_page_id is not None and int(dominant_url_page_id) != page_id:
                dominant_competing_page_id = int(dominant_url_page_id)
                dominant_competing_url = cluster.get("dominant_url")
            elif strongest_overlap is not None:
                dominant_competing_page_id = int(strongest_overlap["competing_page_id"])
                dominant_competing_url = str(strongest_overlap["competing_url"])

        details[page_id] = {
            "crawl_job_id": crawl_job_id,
            "gsc_date_range": gsc_date_range,
            "page_id": page_id,
            "url": str(page_record.get("url") or ""),
            "normalized_url": str(page_record.get("normalized_url") or ""),
            "has_cannibalization": cluster is not None,
            "cluster_id": cluster.get("cluster_id") if cluster is not None else None,
            "severity": cluster.get("severity") if cluster is not None else None,
            "impact_level": cluster.get("impact_level") if cluster is not None else None,
            "recommendation_type": cluster.get("recommendation_type") if cluster is not None else None,
            "rationale": cluster.get("rationale") if cluster is not None else None,
            "competing_urls_count": len(overlaps),
            "strongest_competing_url": strongest_overlap.get("competing_url") if strongest_overlap else None,
            "strongest_competing_page_id": strongest_overlap.get("competing_page_id") if strongest_overlap else None,
            "common_queries_count": int(strongest_overlap.get("common_queries_count") or 0) if strongest_overlap else 0,
            "weighted_overlap_by_impressions": float(strongest_overlap.get("weighted_overlap_by_impressions") or 0.0)
            if strongest_overlap
            else 0.0,
            "weighted_overlap_by_clicks": float(strongest_overlap.get("weighted_overlap_by_clicks") or 0.0)
            if strongest_overlap
            else 0.0,
            "overlap_ratio": float(strongest_overlap.get("overlap_ratio") or 0.0) if strongest_overlap else 0.0,
            "overlap_strength": float(strongest_overlap.get("pair_overlap_score") or 0.0) if strongest_overlap else 0.0,
            "shared_top_queries": list(strongest_overlap.get("shared_top_queries") or []) if strongest_overlap else [],
            "dominant_competing_url": dominant_competing_url,
            "dominant_competing_page_id": dominant_competing_page_id,
            "overlaps": overlaps,
        }

    return details


def _build_summary(
    *,
    crawl_job_id: int,
    gsc_date_range: str,
    profiles: dict[int, PageQueryProfile],
    clusters: list[dict[str, Any]],
) -> dict[str, Any]:
    pages_in_conflicts = {candidate["page_id"] for cluster in clusters for candidate in cluster["candidate_urls"]}
    return {
        "crawl_job_id": crawl_job_id,
        "gsc_date_range": gsc_date_range,
        "total_candidate_pages": len(profiles),
        "pages_in_conflicts": len(pages_in_conflicts),
        "clusters_count": len(clusters),
        "critical_clusters": sum(1 for cluster in clusters if cluster["severity"] == "critical"),
        "high_severity_clusters": sum(1 for cluster in clusters if cluster["severity"] in {"high", "critical"}),
        "high_impact_clusters": sum(1 for cluster in clusters if cluster["impact_level"] == "high"),
        "no_clear_primary_clusters": sum(1 for cluster in clusters if not bool(cluster["has_clear_primary"])),
        "merge_candidates": sum(1 for cluster in clusters if cluster["recommendation_type"] == "MERGE_CANDIDATE"),
        "split_intent_candidates": sum(
            1 for cluster in clusters if cluster["recommendation_type"] == "SPLIT_INTENT_CANDIDATE"
        ),
        "reinforce_primary_candidates": sum(
            1 for cluster in clusters if cluster["recommendation_type"] == "REINFORCE_PRIMARY_URL"
        ),
        "low_value_overlap_clusters": sum(
            1 for cluster in clusters if cluster["recommendation_type"] == "LOW_VALUE_OVERLAP"
        ),
        "average_weighted_overlap": round(
            sum(float(cluster["weighted_overlap"]) for cluster in clusters) / len(clusters),
            4,
        )
        if clusters
        else 0.0,
    }


def _filter_cluster_rows(
    rows: list[dict[str, Any]],
    *,
    severity: CannibalizationSeverity | None,
    impact_level: ImpactLevel | None,
    recommendation_type: CannibalizationRecommendationType | None,
    has_clear_primary: bool | None,
    url_contains: str | None,
) -> list[dict[str, Any]]:
    filtered = list(rows)

    if severity is not None:
        filtered = [row for row in filtered if row.get("severity") == severity]
    if impact_level is not None:
        filtered = [row for row in filtered if row.get("impact_level") == impact_level]
    if recommendation_type is not None:
        filtered = [row for row in filtered if row.get("recommendation_type") == recommendation_type]
    if has_clear_primary is not None:
        filtered = [row for row in filtered if bool(row.get("has_clear_primary")) is has_clear_primary]
    if url_contains:
        token = url_contains.strip().lower()
        if token:
            filtered = [
                row
                for row in filtered
                if token in str(row.get("dominant_url") or "").lower()
                or any(token in str(candidate.get("url") or "").lower() for candidate in row.get("candidate_urls") or [])
                or any(token in str(query).lower() for query in row.get("sample_queries") or [])
            ]

    return filtered


def _sort_cluster_rows(rows: list[dict[str, Any]], *, sort_by: str, sort_order: str) -> None:
    reverse = sort_order == "desc"

    def sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        if sort_by == "severity":
            primary = SEVERITY_ORDER.get(str(row.get("severity")), 0)
        elif sort_by == "impact_level":
            primary = IMPACT_ORDER.get(str(row.get("impact_level")), 0)
        elif sort_by == "weighted_overlap":
            primary = float(row.get("weighted_overlap") or 0.0)
        elif sort_by == "shared_queries_count":
            primary = int(row.get("shared_queries_count") or 0)
        elif sort_by == "shared_query_impressions":
            primary = int(row.get("shared_query_impressions") or 0)
        elif sort_by == "shared_query_clicks":
            primary = int(row.get("shared_query_clicks") or 0)
        elif sort_by == "urls_count":
            primary = int(row.get("urls_count") or 0)
        elif sort_by == "dominant_url_confidence":
            primary = float(row.get("dominant_url_confidence") or 0.0)
        elif sort_by == "recommendation_type":
            primary = str(row.get("recommendation_type") or "").lower()
        else:
            primary = str(row.get("cluster_id") or "").lower()

        return (
            primary,
            float(row.get("weighted_overlap") or 0.0),
            int(row.get("shared_query_impressions") or 0),
            str(row.get("cluster_id") or "").lower(),
        )

    rows.sort(key=sort_key, reverse=reverse)


def _pair_is_relevant(relation: dict[str, Any], rules: CannibalizationRules) -> bool:
    if int(relation["common_queries_count"]) < rules.min_shared_queries:
        return False
    if (
        int(relation["shared_query_impressions"]) < rules.min_pair_shared_impressions
        and int(relation["shared_query_clicks"]) < rules.min_pair_shared_clicks
    ):
        return False
    if (
        float(relation["weighted_overlap_by_impressions"]) < rules.min_weighted_overlap_by_impressions
        and float(relation["weighted_overlap_by_clicks"]) < rules.min_weighted_overlap_by_clicks
        and float(relation["pair_overlap_score"]) < rules.min_pair_overlap_score
    ):
        return False
    return True


def _build_query_samples(
    left: PageQueryProfile,
    right: PageQueryProfile,
    query_keys: set[str],
    *,
    limit: int,
) -> list[str]:
    scored_queries: list[tuple[int, int, str]] = []
    for query_key in query_keys:
        left_metric = left.queries[query_key]
        right_metric = right.queries[query_key]
        scored_queries.append(
            (
                min(int(left_metric.impressions), int(right_metric.impressions)),
                min(int(left_metric.clicks), int(right_metric.clicks)),
                left_metric.display_query if len(left_metric.display_query) <= len(right_metric.display_query) else right_metric.display_query,
            )
        )

    scored_queries.sort(key=lambda item: (item[0], item[1], item[2].lower()), reverse=True)
    return [item[2] for item in scored_queries[:limit]]


def _aggregate_profile_metrics(profile: PageQueryProfile, query_keys: set[str]) -> dict[str, Any]:
    clicks = sum(int(profile.queries[query_key].clicks) for query_key in query_keys if query_key in profile.queries)
    impressions = sum(
        int(profile.queries[query_key].impressions) for query_key in query_keys if query_key in profile.queries
    )
    position_weighted_sum = 0.0
    position_weight = 0.0
    for query_key in query_keys:
        metric = profile.queries.get(query_key)
        if metric is None or metric.average_position is None:
            continue
        weight = max(int(metric.impressions), 1)
        position_weighted_sum += float(metric.average_position) * weight
        position_weight += weight

    average_position = position_weighted_sum / position_weight if position_weight > 0 else None
    return {
        "clicks": clicks,
        "impressions": impressions,
        "average_position": average_position,
    }


def _compute_pair_dominance(
    left: PageQueryProfile,
    right: PageQueryProfile,
    query_keys: set[str],
    rules: CannibalizationRules,
) -> tuple[int | None, float, float]:
    left_metrics = _aggregate_profile_metrics(left, query_keys)
    right_metrics = _aggregate_profile_metrics(right, query_keys)

    total_clicks = int(left_metrics["clicks"]) + int(right_metrics["clicks"])
    total_impressions = int(left_metrics["impressions"]) + int(right_metrics["impressions"])
    left_score = _dominance_score(
        subject_clicks=int(left_metrics["clicks"]),
        total_clicks=total_clicks,
        subject_impressions=int(left_metrics["impressions"]),
        total_impressions=total_impressions,
        subject_position=_optional_float(left_metrics["average_position"]),
        other_position=_optional_float(right_metrics["average_position"]),
        rules=rules,
    )
    right_score = _dominance_score(
        subject_clicks=int(right_metrics["clicks"]),
        total_clicks=total_clicks,
        subject_impressions=int(right_metrics["impressions"]),
        total_impressions=total_impressions,
        subject_position=_optional_float(right_metrics["average_position"]),
        other_position=_optional_float(left_metrics["average_position"]),
        rules=rules,
    )

    if left_score >= right_score:
        dominant_page_id = left.page_id
        best_score = left_score
        next_score = right_score
    else:
        dominant_page_id = right.page_id
        best_score = right_score
        next_score = left_score

    margin = best_score - next_score
    confidence = _dominance_confidence(best_score, margin, rules)
    if best_score < rules.dominance_min_score or margin < rules.dominance_min_margin:
        return None, round(best_score, 4), round(confidence, 4)
    return dominant_page_id, round(best_score, 4), round(confidence, 4)


def _dominance_score(
    *,
    subject_clicks: int,
    total_clicks: int,
    subject_impressions: int,
    total_impressions: int,
    subject_position: float | None,
    other_position: float | None,
    rules: CannibalizationRules,
) -> float:
    click_share = _ratio(subject_clicks, total_clicks)
    impression_share = _ratio(subject_impressions, total_impressions)
    position_share = _position_share(subject_position, other_position)
    return (
        click_share * rules.dominance_click_weight
        + impression_share * rules.dominance_impressions_weight
        + position_share * rules.dominance_position_weight
    )


def _position_share(subject_position: float | None, other_position: float | None) -> float:
    if subject_position is None and other_position is None:
        return 0.5
    if subject_position is None:
        return 0.0
    if other_position is None:
        return 1.0

    subject_score = 1 / max(subject_position, 1.0)
    other_score = 1 / max(other_position, 1.0)
    denominator = subject_score + other_score
    if denominator <= 0:
        return 0.5
    return subject_score / denominator


def _dominance_confidence(best_score: float, margin: float, rules: CannibalizationRules) -> float:
    score_component = max(0.0, best_score - rules.dominance_min_score) / max(0.0001, 1 - rules.dominance_min_score)
    margin_component = max(0.0, margin) / max(0.0001, rules.dominance_min_margin * 3)
    return min(1.0, (score_component * 0.6) + (min(1.0, margin_component) * 0.4))


def _cluster_shared_queries(component_pairs: list[dict[str, Any]]) -> set[str]:
    shared_queries: set[str] = set()
    for pair in component_pairs:
        shared_queries.update(pair.get("query_keys") or [])
    return shared_queries


def _cluster_shared_query_count_by_page(component_pairs: list[dict[str, Any]]) -> dict[int, set[str]]:
    shared_query_count_by_page: dict[int, set[str]] = defaultdict(set)
    for pair in component_pairs:
        for page_id in (int(pair["page_a_id"]), int(pair["page_b_id"])):
            shared_query_count_by_page[page_id].update(pair.get("query_keys") or [])
    return shared_query_count_by_page


def _cluster_query_demand(
    profiles: dict[int, PageQueryProfile],
    page_ids: list[int],
    cluster_shared_queries: set[str],
) -> dict[str, int]:
    demand_impressions = 0
    demand_clicks = 0
    page_clicks_total = 0
    page_impressions_total = 0

    for page_id in page_ids:
        profile = profiles[page_id]
        page_queries = [profile.queries[query_key] for query_key in cluster_shared_queries if query_key in profile.queries]
        page_clicks_total += sum(int(metric.clicks) for metric in page_queries)
        page_impressions_total += sum(int(metric.impressions) for metric in page_queries)

    for query_key in cluster_shared_queries:
        metrics = [profiles[page_id].queries[query_key] for page_id in page_ids if query_key in profiles[page_id].queries]
        if not metrics:
            continue
        demand_impressions += max(int(metric.impressions) for metric in metrics)
        demand_clicks += max(int(metric.clicks) for metric in metrics)

    return {
        "demand_impressions": int(demand_impressions),
        "demand_clicks": int(demand_clicks),
        "page_clicks_total": int(page_clicks_total),
        "page_impressions_total": int(page_impressions_total),
    }


def _compute_cluster_dominance(
    profiles: dict[int, PageQueryProfile],
    page_ids: list[int],
    shared_query_count_by_page: dict[int, set[str]],
    rules: CannibalizationRules,
) -> tuple[int | None, float, float]:
    page_scores: dict[int, float] = {}
    cluster_clicks_total = sum(
        sum(int(profiles[page_id].queries[query_key].clicks) for query_key in shared_query_count_by_page.get(page_id, set()))
        for page_id in page_ids
    )
    cluster_impressions_total = sum(
        sum(
            int(profiles[page_id].queries[query_key].impressions)
            for query_key in shared_query_count_by_page.get(page_id, set())
        )
        for page_id in page_ids
    )

    position_scores: dict[int, float] = {}
    for page_id in page_ids:
        shared_queries = shared_query_count_by_page.get(page_id, set())
        metrics = _aggregate_profile_metrics(profiles[page_id], shared_queries)
        average_position = _optional_float(metrics["average_position"])
        if average_position is None:
            position_scores[page_id] = 0.0
        else:
            position_scores[page_id] = 1 / max(average_position, 1.0)

    position_total = sum(position_scores.values())
    for page_id in page_ids:
        shared_queries = shared_query_count_by_page.get(page_id, set())
        metrics = _aggregate_profile_metrics(profiles[page_id], shared_queries)
        click_share = _ratio(int(metrics["clicks"]), cluster_clicks_total)
        impression_share = _ratio(int(metrics["impressions"]), cluster_impressions_total)
        position_share = position_scores[page_id] / position_total if position_total > 0 else 0.0
        page_scores[page_id] = (
            click_share * rules.dominance_click_weight
            + impression_share * rules.dominance_impressions_weight
            + position_share * rules.dominance_position_weight
        )

    ranked = sorted(page_scores.items(), key=lambda item: (item[1], -item[0]), reverse=True)
    if not ranked:
        return None, 0.0, 0.0

    best_page_id, best_score = ranked[0]
    next_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = best_score - next_score
    confidence = _dominance_confidence(best_score, margin, rules)
    if best_score < rules.dominance_min_score or margin < rules.dominance_min_margin:
        return None, round(best_score, 4), round(confidence, 4)
    return best_page_id, round(best_score, 4), round(confidence, 4)


def _build_cluster_candidate_urls(
    *,
    profiles: dict[int, PageQueryProfile],
    page_ids: list[int],
    shared_query_count_by_page: dict[int, set[str]],
    cluster_shared_queries: set[str],
    cluster_shared_clicks: int,
    cluster_shared_impressions: int,
    dominant_page_id: int | None,
    page_overlaps: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page_id in page_ids:
        profile = profiles[page_id]
        shared_queries = shared_query_count_by_page.get(page_id, set())
        shared_metrics = _aggregate_profile_metrics(profile, shared_queries)
        strongest_overlap = (page_overlaps.get(page_id) or [None])[0]
        rows.append(
            {
                "page_id": page_id,
                "url": profile.url,
                "priority_score": int(profile.priority_score),
                "priority_level": profile.priority_level,
                "primary_opportunity_type": profile.primary_opportunity_type,
                "clicks": int(profile.clicks),
                "impressions": int(profile.impressions),
                "position": profile.position,
                "query_count": int(profile.query_count),
                "shared_query_count": len(shared_queries),
                "exclusive_query_count": max(0, int(profile.query_count) - len(shared_queries)),
                "click_share": round(_ratio(int(shared_metrics["clicks"]), cluster_shared_clicks), 4),
                "impression_share": round(_ratio(int(shared_metrics["impressions"]), cluster_shared_impressions), 4),
                "avg_shared_position": _optional_float(shared_metrics["average_position"]),
                "strongest_competing_url": strongest_overlap.get("competing_url") if strongest_overlap else None,
                "is_dominant": dominant_page_id == page_id,
            }
        )

    rows.sort(
        key=lambda row: (
            bool(row["is_dominant"]),
            float(row["click_share"]),
            int(row["priority_score"]),
            str(row["url"]).lower(),
        ),
        reverse=True,
    )
    return rows


def _cluster_sample_queries(
    profiles: dict[int, PageQueryProfile],
    page_ids: list[int],
    cluster_shared_queries: set[str],
    *,
    limit: int,
) -> list[str]:
    scored_queries: list[tuple[int, int, str]] = []
    for query_key in cluster_shared_queries:
        metrics = [profiles[page_id].queries[query_key] for page_id in page_ids if query_key in profiles[page_id].queries]
        if not metrics:
            continue
        display_query = min((metric.display_query for metric in metrics), key=len)
        scored_queries.append(
            (
                max(int(metric.impressions) for metric in metrics),
                max(int(metric.clicks) for metric in metrics),
                display_query,
            )
        )

    scored_queries.sort(key=lambda item: (item[0], item[1], item[2].lower()), reverse=True)
    return [item[2] for item in scored_queries[:limit]]


def _classify_impact_level(
    *,
    shared_impressions: int,
    shared_clicks: int,
    rules: CannibalizationRules,
) -> ImpactLevel:
    if (
        shared_impressions >= rules.high_impact_min_shared_impressions
        or shared_clicks >= rules.high_impact_min_shared_clicks
    ):
        return "high"
    if (
        shared_impressions >= rules.medium_impact_min_shared_impressions
        or shared_clicks >= rules.medium_impact_min_shared_clicks
    ):
        return "medium"
    return "low"


def _classify_recommendation(
    *,
    candidate_urls: list[dict[str, Any]],
    weighted_overlap: float,
    impact_level: ImpactLevel,
    has_clear_primary: bool,
    shared_impressions: int,
    shared_clicks: int,
    rules: CannibalizationRules,
) -> CannibalizationRecommendationType:
    if (
        impact_level == "low"
        and shared_impressions <= rules.low_value_max_shared_impressions
        and shared_clicks <= rules.low_value_max_shared_clicks
    ):
        return "LOW_VALUE_OVERLAP"

    dominant_row = next((row for row in candidate_urls if bool(row["is_dominant"])), None)
    secondary_rows = [row for row in candidate_urls if not bool(row["is_dominant"])]
    top_secondary = secondary_rows[0] if secondary_rows else None

    if (
        len(candidate_urls) == 2
        and has_clear_primary
        and dominant_row is not None
        and top_secondary is not None
        and weighted_overlap >= rules.merge_candidate_min_overlap
        and float(top_secondary["click_share"]) <= rules.merge_candidate_secondary_click_share_max
        and float(top_secondary["impression_share"]) <= rules.merge_candidate_secondary_impression_share_max
        and int(top_secondary["exclusive_query_count"]) <= rules.merge_candidate_max_exclusive_queries
    ):
        return "MERGE_CANDIDATE"

    if (
        impact_level == "high"
        and weighted_overlap >= rules.reinforce_primary_min_overlap
        and (
            not has_clear_primary
            or top_secondary is None
            or float(top_secondary["click_share"]) > rules.reinforce_primary_secondary_click_share_max
            or len(candidate_urls) > 2
        )
    ):
        return "HIGH_IMPACT_CANNIBALIZATION"

    urls_with_exclusive_queries = sum(
        1 for row in candidate_urls if int(row["exclusive_query_count"]) >= rules.split_intent_min_exclusive_queries
    )
    if (
        not has_clear_primary
        and weighted_overlap >= rules.split_intent_min_overlap
        and urls_with_exclusive_queries >= rules.split_intent_min_urls_with_exclusive_queries
    ):
        return "SPLIT_INTENT_CANDIDATE"

    if not has_clear_primary:
        return "QUERY_CLUSTER_WITHOUT_CLEAR_PRIMARY"

    if (
        has_clear_primary
        and weighted_overlap >= rules.reinforce_primary_min_overlap
        and top_secondary is not None
        and float(top_secondary["click_share"]) <= 0.45
    ):
        return "REINFORCE_PRIMARY_URL"

    return "LOW_VALUE_OVERLAP"


def _compute_severity_score(
    *,
    candidate_urls: list[dict[str, Any]],
    weighted_overlap: float,
    shared_queries_count: int,
    impact_level: ImpactLevel,
    recommendation_type: CannibalizationRecommendationType,
    rules: CannibalizationRules,
) -> int:
    impact_points = {
        "low": 10,
        "medium": 25,
        "high": 45,
    }[impact_level]
    max_priority_score = max((int(candidate["priority_score"]) for candidate in candidate_urls), default=0)
    score = (
        impact_points
        + (weighted_overlap * 25)
        + min(shared_queries_count * 4, 20)
        + (max_priority_score * rules.severity_priority_weight)
        + rules.severity_recommendation_bonus[recommendation_type]
    )
    return max(0, min(100, int(round(score))))


def _resolve_severity_from_score(
    score: int,
    rules: CannibalizationRules,
) -> CannibalizationSeverity:
    for severity, threshold in sorted(
        rules.severity_thresholds.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        if score >= threshold:
            return severity
    return "low"


def _build_cluster_rationale(
    *,
    recommendation_type: CannibalizationRecommendationType,
    severity: CannibalizationSeverity,
    impact_level: ImpactLevel,
    weighted_overlap: float,
    shared_impressions: int,
    shared_clicks: int,
    dominant_url: str | None,
    dominant_url_confidence: float,
    shared_queries_count: int,
) -> str:
    overlap_percent = int(round(weighted_overlap * 100))
    confidence_percent = int(round(dominant_url_confidence * 100))
    if recommendation_type == "MERGE_CANDIDATE":
        return (
            f"Two URLs share {shared_queries_count} meaningful queries and overlap around {overlap_percent}%, "
            f"while {dominant_url or 'one URL'} clearly leads the cluster."
        )
    if recommendation_type == "SPLIT_INTENT_CANDIDATE":
        return (
            f"Cluster shares {shared_queries_count} queries with {overlap_percent}% overlap, but there is still "
            "no clear primary URL and multiple URLs keep exclusive query coverage."
        )
    if recommendation_type == "REINFORCE_PRIMARY_URL":
        return (
            f"{dominant_url or 'A primary URL'} leads with about {confidence_percent}% confidence, "
            f"but overlap remains meaningful at {overlap_percent}%."
        )
    if recommendation_type == "QUERY_CLUSTER_WITHOUT_CLEAR_PRIMARY":
        return (
            f"Cluster shares {shared_queries_count} queries and {shared_impressions} impressions, but no dominant "
            "URL separates itself strongly enough."
        )
    if recommendation_type == "HIGH_IMPACT_CANNIBALIZATION":
        return (
            f"High-impact overlap affects about {shared_impressions} impressions and {shared_clicks} clicks across "
            f"{shared_queries_count} shared queries."
        )
    return (
        f"Overlap remains limited at {overlap_percent}%, which keeps the expected impact {impact_level} and "
        f"severity {severity}."
    )


def _apply_default_page_metadata(record: dict[str, Any]) -> None:
    record["has_cannibalization"] = False
    record["cannibalization_cluster_id"] = None
    record["cannibalization_severity"] = None
    record["cannibalization_impact_level"] = None
    record["cannibalization_recommendation_type"] = None
    record["cannibalization_rationale"] = None
    record["cannibalization_competing_urls_count"] = 0
    record["cannibalization_strongest_competing_url"] = None
    record["cannibalization_strongest_competing_page_id"] = None
    record["cannibalization_dominant_competing_url"] = None
    record["cannibalization_dominant_competing_page_id"] = None
    record["cannibalization_common_queries_count"] = 0
    record["cannibalization_weighted_overlap_by_impressions"] = 0.0
    record["cannibalization_weighted_overlap_by_clicks"] = 0.0
    record["cannibalization_overlap_ratio"] = 0.0
    record["cannibalization_overlap_strength"] = 0.0
    record["cannibalization_shared_top_queries"] = []


def _apply_page_metadata(record: dict[str, Any], metadata: dict[str, Any]) -> None:
    _apply_default_page_metadata(record)
    record["has_cannibalization"] = bool(metadata["has_cannibalization"])
    record["cannibalization_cluster_id"] = metadata.get("cluster_id")
    record["cannibalization_severity"] = metadata.get("severity")
    record["cannibalization_impact_level"] = metadata.get("impact_level")
    record["cannibalization_recommendation_type"] = metadata.get("recommendation_type")
    record["cannibalization_rationale"] = metadata.get("rationale")
    record["cannibalization_competing_urls_count"] = int(metadata.get("competing_urls_count") or 0)
    record["cannibalization_strongest_competing_url"] = metadata.get("strongest_competing_url")
    record["cannibalization_strongest_competing_page_id"] = metadata.get("strongest_competing_page_id")
    record["cannibalization_dominant_competing_url"] = metadata.get("dominant_competing_url")
    record["cannibalization_dominant_competing_page_id"] = metadata.get("dominant_competing_page_id")
    record["cannibalization_common_queries_count"] = int(metadata.get("common_queries_count") or 0)
    record["cannibalization_weighted_overlap_by_impressions"] = round(
        float(metadata.get("weighted_overlap_by_impressions") or 0.0),
        4,
    )
    record["cannibalization_weighted_overlap_by_clicks"] = round(
        float(metadata.get("weighted_overlap_by_clicks") or 0.0),
        4,
    )
    record["cannibalization_overlap_ratio"] = round(float(metadata.get("overlap_ratio") or 0.0), 4)
    record["cannibalization_overlap_strength"] = round(float(metadata.get("overlap_strength") or 0.0), 4)
    record["cannibalization_shared_top_queries"] = list(metadata.get("shared_top_queries") or [])


def _normalize_query(query: str | None) -> str | None:
    if text_value_missing(query):
        return None
    normalized = WHITESPACE_RE.sub(" ", str(query).strip().lower())
    return normalized or None


def _resolve_gsc_suffix(gsc_date_range: str) -> str:
    suffix = GSC_DATE_RANGE_SUFFIX.get(gsc_date_range)
    if suffix is None:
        raise CannibalizationServiceError(f"Unsupported gsc_date_range '{gsc_date_range}'.")
    return suffix


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
