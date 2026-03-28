from __future__ import annotations

from sqlalchemy import select

from app.db.models import GscProperty, GscTopQuery
from app.services import semstorm_coverage_service
from tests.competitive_gap_test_utils import FIXED_TIME, seed_competitive_gap_site


def _add_gsc_top_query(
    session_factory,
    *,
    site_id: int,
    crawl_job_id: int,
    page_id: int,
    url: str,
    query: str,
    clicks: int,
    impressions: int,
    ctr: float,
    position: float,
) -> None:
    with session_factory() as session:
        gsc_property_id = session.scalar(select(GscProperty.id).where(GscProperty.site_id == site_id))
        assert gsc_property_id is not None
        session.add(
            GscTopQuery(
                gsc_property_id=int(gsc_property_id),
                crawl_job_id=crawl_job_id,
                page_id=page_id,
                url=url,
                normalized_url=url,
                date_range_label="last_28_days",
                query=query,
                clicks=clicks,
                impressions=impressions,
                ctr=ctr,
                position=position,
                fetched_at=FIXED_TIME,
                created_at=FIXED_TIME,
            )
        )
        session.commit()


def test_evaluate_keyword_coverage_classifies_covered_weak_and_missing(sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        context = semstorm_coverage_service.build_site_coverage_context(session, ids["site_id"])
        covered = semstorm_coverage_service.evaluate_keyword_coverage(context, "seo audit")
        weak = semstorm_coverage_service.evaluate_keyword_coverage(context, "content strategy template")
        missing = semstorm_coverage_service.evaluate_keyword_coverage(context, "local seo pricing")

    assert context.active_crawl_id == ids["crawl_job_id"]

    assert covered["coverage_status"] == "covered"
    assert covered["matched_pages_count"] == 1
    assert covered["best_match_page"]["page_id"] == ids["audit_page_id"]
    assert "title_exact" in covered["best_match_page"]["match_signals"]
    assert covered["coverage_score_v1"] >= 85

    assert weak["coverage_status"] == "weak_coverage"
    assert weak["matched_pages_count"] == 1
    assert weak["best_match_page"]["page_id"] == ids["content_strategy_page_id"]
    assert any(signal.endswith("partial") for signal in weak["best_match_page"]["match_signals"])
    assert 25 <= weak["coverage_score_v1"] < 70

    assert missing == {
        "coverage_status": "missing",
        "matched_pages_count": 0,
        "best_match_page": None,
        "coverage_score_v1": 0,
    }


def test_evaluate_keyword_gsc_signal_prefers_exact_query_then_page_metric(sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    _add_gsc_top_query(
        sqlite_session_factory,
        site_id=ids["site_id"],
        crawl_job_id=ids["crawl_job_id"],
        page_id=ids["audit_page_id"],
        url="https://example.com/seo-audit",
        query="seo audit",
        clicks=17,
        impressions=190,
        ctr=0.089,
        position=4.1,
    )

    with sqlite_session_factory() as session:
        context = semstorm_coverage_service.build_site_coverage_context(session, ids["site_id"])
        exact = semstorm_coverage_service.evaluate_keyword_gsc_signal(
            context,
            "seo audit",
            best_match_page_id=ids["audit_page_id"],
        )
        weak = semstorm_coverage_service.evaluate_keyword_gsc_signal(
            context,
            "content strategy template",
            best_match_page_id=ids["content_strategy_page_id"],
        )
        none = semstorm_coverage_service.evaluate_keyword_gsc_signal(
            context,
            "local seo pricing",
            best_match_page_id=None,
        )

    assert exact["gsc_signal_status"] == "present"
    assert exact["gsc_summary"] == {
        "clicks": 17,
        "impressions": 190,
        "ctr": 0.0895,
        "avg_position": 4.1,
    }

    assert weak["gsc_signal_status"] == "weak"
    assert weak["gsc_summary"] == {
        "clicks": 11,
        "impressions": 180,
        "ctr": 0.061,
        "avg_position": 8.1,
    }

    assert none == {
        "gsc_signal_status": "none",
        "gsc_summary": None,
    }
