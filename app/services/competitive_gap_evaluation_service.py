from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services import competitive_gap_service
from app.services.competitive_gap_semantic_rules import resolve_semantic_exclusion_reason
from app.services.competitive_gap_topic_quality_service import analyze_topic_quality


@dataclass(frozen=True, slots=True)
class TopicQualityBenchmarkCase:
    name: str
    page: Any
    expected_exclusion_reason: str | None
    expected_topic_key: str | None = None


@dataclass(frozen=True, slots=True)
class CoverageBenchmarkCase:
    name: str
    cluster_card: dict[str, Any]
    cluster_members: list[Any]
    own_pages: list[Any]
    allowed_coverage_types: set[str]


@dataclass(frozen=True, slots=True)
class DedupeBenchmarkCase:
    name: str
    rows: list[dict[str, Any]]
    expected_row_count: int


def run_topic_quality_benchmark(cases: list[TopicQualityBenchmarkCase]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    passed = 0
    for case in cases:
        signals = analyze_topic_quality(case.page)
        exclusion_reason = resolve_semantic_exclusion_reason(case.page, match_terms=signals.normalized_terms)
        topic_key_ok = (
            case.expected_topic_key is None
            or str(signals.dominant_topic_key or "") == str(case.expected_topic_key)
        )
        passed_case = exclusion_reason == case.expected_exclusion_reason and topic_key_ok
        if passed_case:
            passed += 1
        results.append(
            {
                "name": case.name,
                "passed": passed_case,
                "expected_exclusion_reason": case.expected_exclusion_reason,
                "actual_exclusion_reason": exclusion_reason,
                "expected_topic_key": case.expected_topic_key,
                "actual_topic_key": signals.dominant_topic_key,
            }
        )
    return {
        "cases_total": len(cases),
        "cases_passed": passed,
        "cases_failed": len(cases) - passed,
        "results": results,
    }


def run_coverage_benchmark(cases: list[CoverageBenchmarkCase]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    passed = 0
    for case in cases:
        coverage = competitive_gap_service._resolve_cluster_coverage(
            cluster_card=case.cluster_card,
            cluster_members=case.cluster_members,
            own_pages=case.own_pages,
        )
        coverage_type = str(coverage.get("coverage_type") or "")
        passed_case = coverage_type in case.allowed_coverage_types
        if passed_case:
            passed += 1
        results.append(
            {
                "name": case.name,
                "passed": passed_case,
                "allowed_coverage_types": sorted(case.allowed_coverage_types),
                "actual_coverage_type": coverage_type,
                "coverage_reason_code": coverage.get("coverage_reason_code"),
            }
        )
    return {
        "cases_total": len(cases),
        "cases_passed": passed,
        "cases_failed": len(cases) - passed,
        "results": results,
    }


def run_dedupe_benchmark(cases: list[DedupeBenchmarkCase]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    passed = 0
    for case in cases:
        deduped = competitive_gap_service._dedupe_equivalent_gap_rows(case.rows)
        row_count = len(deduped)
        passed_case = row_count == case.expected_row_count
        if passed_case:
            passed += 1
        results.append(
            {
                "name": case.name,
                "passed": passed_case,
                "expected_row_count": case.expected_row_count,
                "actual_row_count": row_count,
            }
        )
    return {
        "cases_total": len(cases),
        "cases_passed": passed,
        "cases_failed": len(cases) - passed,
        "results": results,
    }


def run_competitive_gap_quality_benchmark(
    *,
    topic_cases: list[TopicQualityBenchmarkCase],
    coverage_cases: list[CoverageBenchmarkCase],
    dedupe_cases: list[DedupeBenchmarkCase],
) -> dict[str, Any]:
    topic_summary = run_topic_quality_benchmark(topic_cases)
    coverage_summary = run_coverage_benchmark(coverage_cases)
    dedupe_summary = run_dedupe_benchmark(dedupe_cases)
    totals = {
        "cases_total": (
            int(topic_summary["cases_total"])
            + int(coverage_summary["cases_total"])
            + int(dedupe_summary["cases_total"])
        ),
        "cases_passed": (
            int(topic_summary["cases_passed"])
            + int(coverage_summary["cases_passed"])
            + int(dedupe_summary["cases_passed"])
        ),
    }
    totals["cases_failed"] = totals["cases_total"] - totals["cases_passed"]
    return {
        "summary": totals,
        "topic_quality": topic_summary,
        "coverage": coverage_summary,
        "dedupe": dedupe_summary,
    }
