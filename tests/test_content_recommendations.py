from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import (
    CrawlJob,
    CrawlJobStatus,
    GscProperty,
    GscTopQuery,
    GscUrlMetric,
    Link,
    Page,
    Site,
    SiteContentRecommendationState,
)
from app.services import content_recommendation_service
from app.services.content_recommendation_keys import build_content_recommendation_key
from app.services.export_service import build_site_content_recommendations_csv


FIXED_TIME = datetime(2026, 3, 16, 12, 0, tzinfo=timezone.utc)


def _make_page(crawl_job_id: int, path: str, **overrides) -> Page:
    url = f"https://example.com{path}"
    defaults = {
      "crawl_job_id": crawl_job_id,
      "url": url,
      "normalized_url": url,
      "final_url": url,
      "status_code": 200,
      "title": path.strip("/") or "Home",
      "meta_description": f"Meta for {path}",
      "h1": path.strip("/") or "Home",
      "canonical_url": url,
      "content_type": "text/html",
      "word_count": 500,
      "h1_count": 1,
      "h2_count": 2,
      "schema_present": True,
      "schema_count": 1,
      "schema_types_json": [],
      "is_internal": True,
      "depth": len([segment for segment in path.split("/") if segment]),
      "fetched_at": FIXED_TIME,
      "created_at": FIXED_TIME,
    }
    defaults.update(overrides)
    return Page(**defaults)


def _add_gsc_metric(
    session,
    *,
    gsc_property_id: int,
    crawl_job_id: int,
    page: Page,
    clicks: int,
    impressions: int,
    ctr: float,
    position: float,
) -> None:
    session.add(
        GscUrlMetric(
            gsc_property_id=gsc_property_id,
            crawl_job_id=crawl_job_id,
            page_id=page.id,
            url=page.url,
            normalized_url=page.normalized_url,
            date_range_label="last_28_days",
            clicks=clicks,
            impressions=impressions,
            ctr=ctr,
            position=position,
            fetched_at=FIXED_TIME,
            created_at=FIXED_TIME,
        )
    )


def _add_top_query(
    session,
    *,
    gsc_property_id: int,
    crawl_job_id: int,
    page: Page,
    query: str,
    clicks: int,
    impressions: int,
    ctr: float,
    position: float,
) -> None:
    session.add(
        GscTopQuery(
            gsc_property_id=gsc_property_id,
            crawl_job_id=crawl_job_id,
            page_id=page.id,
            url=page.url,
            normalized_url=page.normalized_url,
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


def _find_recommendation(payload: dict[str, object], recommendation_type: str, target_url: str) -> dict[str, object]:
    return next(
        item
        for item in payload["items"]
        if item["recommendation_type"] == recommendation_type and item["target_url"] == target_url
    )


def seed_content_recommendation_site(session_factory) -> tuple[int, int]:
    with session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com", created_at=FIXED_TIME)
        session.add(site)
        session.flush()

        crawl_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=FIXED_TIME,
            started_at=FIXED_TIME,
            finished_at=FIXED_TIME,
            settings_json={"start_url": "https://example.com"},
            stats_json={},
        )
        session.add(crawl_job)
        session.flush()

        gsc_property = GscProperty(
            site_id=site.id,
            property_uri="sc-domain:example.com",
            permission_level="siteOwner",
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        session.add(gsc_property)
        session.flush()

        pages = {
            "audit_service": _make_page(
                crawl_job.id,
                "/audyt-seo",
                title="Audyt SEO",
                h1="Audyt SEO",
                schema_types_json=["Service"],
                word_count=780,
            ),
            "audit_location": _make_page(
                crawl_job.id,
                "/audyt-seo/warszawa",
                title="Audyt SEO Warszawa",
                h1="Audyt SEO Warszawa",
                schema_types_json=["LocalBusiness"],
                word_count=640,
            ),
            "thin_service": _make_page(
                crawl_job.id,
                "/pozycjonowanie-lokalne",
                title="Pozycjonowanie lokalne",
                h1="Pozycjonowanie lokalne",
                schema_types_json=["Service"],
                word_count=920,
                h2_count=4,
            ),
            "content_service": _make_page(
                crawl_job.id,
                "/content-strategy",
                title="Content strategy",
                h1="Content strategy",
                schema_types_json=["Service"],
                meta_description=None,
                word_count=220,
                h2_count=0,
            ),
            "content_faq": _make_page(
                crawl_job.id,
                "/content-strategy/faq",
                title="Content strategy FAQ",
                h1="Content strategy FAQ",
                schema_types_json=["FAQPage"],
                word_count=180,
            ),
            "audit_product_lite": _make_page(
                crawl_job.id,
                "/produkt/audit-lite",
                title="Audit Lite",
                h1="Audit Lite",
                schema_types_json=["Product"],
                word_count=380,
            ),
            "audit_product_pro": _make_page(
                crawl_job.id,
                "/produkt/audit-pro",
                title="Audit Pro",
                h1="Audit Pro",
                schema_types_json=["Product"],
                word_count=390,
            ),
        }
        session.add_all(pages.values())
        session.flush()

        _add_gsc_metric(session, gsc_property_id=gsc_property.id, crawl_job_id=crawl_job.id, page=pages["audit_service"], clicks=16, impressions=280, ctr=0.057, position=7.2)
        _add_gsc_metric(session, gsc_property_id=gsc_property.id, crawl_job_id=crawl_job.id, page=pages["audit_location"], clicks=6, impressions=90, ctr=0.066, position=8.5)
        _add_gsc_metric(session, gsc_property_id=gsc_property.id, crawl_job_id=crawl_job.id, page=pages["thin_service"], clicks=8, impressions=150, ctr=0.053, position=10.2)
        _add_gsc_metric(session, gsc_property_id=gsc_property.id, crawl_job_id=crawl_job.id, page=pages["content_service"], clicks=14, impressions=200, ctr=0.07, position=6.8)
        _add_gsc_metric(session, gsc_property_id=gsc_property.id, crawl_job_id=crawl_job.id, page=pages["content_faq"], clicks=3, impressions=40, ctr=0.075, position=9.5)
        _add_gsc_metric(session, gsc_property_id=gsc_property.id, crawl_job_id=crawl_job.id, page=pages["audit_product_lite"], clicks=9, impressions=130, ctr=0.069, position=9.0)
        _add_gsc_metric(session, gsc_property_id=gsc_property.id, crawl_job_id=crawl_job.id, page=pages["audit_product_pro"], clicks=7, impressions=110, ctr=0.064, position=10.0)

        _add_top_query(session, gsc_property_id=gsc_property.id, crawl_job_id=crawl_job.id, page=pages["content_service"], query="content strategy", clicks=7, impressions=90, ctr=0.078, position=7.0)
        _add_top_query(session, gsc_property_id=gsc_property.id, crawl_job_id=crawl_job.id, page=pages["content_service"], query="content strategy services", clicks=5, impressions=70, ctr=0.071, position=8.2)
        _add_top_query(session, gsc_property_id=gsc_property.id, crawl_job_id=crawl_job.id, page=pages["content_faq"], query="content strategy", clicks=2, impressions=50, ctr=0.04, position=8.7)
        _add_top_query(session, gsc_property_id=gsc_property.id, crawl_job_id=crawl_job.id, page=pages["audit_service"], query="audyt seo", clicks=8, impressions=120, ctr=0.067, position=7.1)
        _add_top_query(session, gsc_property_id=gsc_property.id, crawl_job_id=crawl_job.id, page=pages["audit_product_lite"], query="audit lite", clicks=4, impressions=45, ctr=0.089, position=8.7)

        session.add_all(
            [
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=pages["audit_location"].id,
                    source_url=pages["audit_location"].url,
                    target_url=pages["audit_service"].url,
                    target_normalized_url=pages["audit_service"].normalized_url,
                    target_domain="example.com",
                    anchor_text="audyt seo",
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=pages["content_faq"].id,
                    source_url=pages["content_faq"].url,
                    target_url=pages["content_service"].url,
                    target_normalized_url=pages["content_service"].normalized_url,
                    target_domain="example.com",
                    anchor_text="content strategy",
                    is_internal=True,
                ),
            ]
        )

        session.commit()
        return site.id, crawl_job.id


def seed_content_recommendation_site_with_baseline(session_factory) -> tuple[int, int, int]:
    with session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com", created_at=FIXED_TIME - timedelta(days=2))
        session.add(site)
        session.flush()

        baseline_crawl = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=FIXED_TIME - timedelta(days=1),
            started_at=FIXED_TIME - timedelta(days=1),
            finished_at=FIXED_TIME - timedelta(days=1),
            settings_json={"start_url": "https://example.com"},
            stats_json={},
        )
        active_crawl = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=FIXED_TIME,
            started_at=FIXED_TIME,
            finished_at=FIXED_TIME,
            settings_json={"start_url": "https://example.com"},
            stats_json={},
        )
        session.add_all([baseline_crawl, active_crawl])
        session.flush()

        gsc_property = GscProperty(
            site_id=site.id,
            property_uri="sc-domain:example.com",
            permission_level="siteOwner",
            created_at=FIXED_TIME - timedelta(days=2),
            updated_at=FIXED_TIME,
        )
        session.add(gsc_property)
        session.flush()

        baseline_pages = {
            "content_service": _make_page(
                baseline_crawl.id,
                "/content-strategy",
                title=None,
                meta_description=None,
                h1=None,
                h1_count=0,
                schema_types_json=["Service"],
                word_count=180,
                h2_count=0,
                canonical_url=None,
                created_at=FIXED_TIME - timedelta(days=1),
                fetched_at=FIXED_TIME - timedelta(days=1),
            ),
            "content_faq": _make_page(
                baseline_crawl.id,
                "/content-strategy/faq",
                title="Content strategy FAQ",
                h1="Content strategy FAQ",
                schema_types_json=["FAQPage"],
                word_count=160,
                created_at=FIXED_TIME - timedelta(days=1),
                fetched_at=FIXED_TIME - timedelta(days=1),
            ),
        }
        active_pages = {
            "content_service": _make_page(
                active_crawl.id,
                "/content-strategy",
                title="Content strategy",
                h1="Content strategy",
                schema_types_json=["Service"],
                meta_description=None,
                word_count=220,
                h2_count=0,
            ),
            "content_faq": _make_page(
                active_crawl.id,
                "/content-strategy/faq",
                title="Content strategy FAQ",
                h1="Content strategy FAQ",
                schema_types_json=["FAQPage"],
                word_count=180,
            ),
        }
        session.add_all([*baseline_pages.values(), *active_pages.values()])
        session.flush()

        _add_gsc_metric(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=baseline_crawl.id,
            page=baseline_pages["content_service"],
            clicks=9,
            impressions=120,
            ctr=0.075,
            position=9.4,
        )
        _add_gsc_metric(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=baseline_crawl.id,
            page=baseline_pages["content_faq"],
            clicks=1,
            impressions=20,
            ctr=0.05,
            position=11.2,
        )
        _add_gsc_metric(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=active_crawl.id,
            page=active_pages["content_service"],
            clicks=14,
            impressions=200,
            ctr=0.07,
            position=6.8,
        )
        _add_gsc_metric(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=active_crawl.id,
            page=active_pages["content_faq"],
            clicks=3,
            impressions=40,
            ctr=0.075,
            position=9.5,
        )

        _add_top_query(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=baseline_crawl.id,
            page=baseline_pages["content_service"],
            query="content strategy",
            clicks=5,
            impressions=60,
            ctr=0.083,
            position=8.8,
        )
        _add_top_query(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=active_crawl.id,
            page=active_pages["content_service"],
            query="content strategy",
            clicks=7,
            impressions=90,
            ctr=0.078,
            position=7.0,
        )
        _add_top_query(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=active_crawl.id,
            page=active_pages["content_service"],
            query="content strategy services",
            clicks=5,
            impressions=70,
            ctr=0.071,
            position=8.2,
        )
        _add_top_query(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=active_crawl.id,
            page=active_pages["content_faq"],
            query="content strategy",
            clicks=2,
            impressions=50,
            ctr=0.04,
            position=8.7,
        )

        session.add(
            Link(
                crawl_job_id=active_crawl.id,
                source_page_id=active_pages["content_faq"].id,
                source_url=active_pages["content_faq"].url,
                target_url=active_pages["content_service"].url,
                target_normalized_url=active_pages["content_service"].normalized_url,
                target_domain="example.com",
                anchor_text="content strategy",
                is_internal=True,
            )
        )

        session.commit()
        return site.id, active_crawl.id, baseline_crawl.id


def _add_implemented_state(
    session,
    *,
    site_id: int,
    recommendation_key: str,
    recommendation_type: str,
    segment: str,
    recommendation_text: str,
    primary_outcome_kind: str,
    implemented_at: datetime,
    implemented_crawl_job_id: int | None,
    target_url: str = "https://example.com/content-strategy",
    normalized_target_url: str = "https://example.com/content-strategy",
    target_title_snapshot: str = "Content strategy",
    cluster_label: str = "Content strategy",
    cluster_key: str = "content",
    signals_snapshot_json: dict[str, object] | None = None,
) -> None:
    session.add(
        SiteContentRecommendationState(
            site_id=site_id,
            recommendation_key=recommendation_key,
            recommendation_type=recommendation_type,
            segment=segment,
            target_url=target_url,
            normalized_target_url=normalized_target_url,
            target_title_snapshot=target_title_snapshot,
            cluster_label=cluster_label,
            cluster_key=cluster_key,
            recommendation_text=recommendation_text,
            signals_snapshot_json=signals_snapshot_json
            or {
                "signals": [],
                "reasons": [],
                "recommendation": {
                    "priority_score": 72,
                    "cluster_strength": 55,
                    "coverage_gap_score": 50,
                    "internal_support_score": 35,
                },
                "gsc": None,
                "internal_linking": None,
                "cannibalization": None,
                "issue_flags": {
                    "technical_issue_count": 0,
                    "active_flags": [],
                },
            },
            helper_snapshot_json=None,
            primary_outcome_kind=primary_outcome_kind,
            implemented_at=implemented_at,
            implemented_crawl_job_id=implemented_crawl_job_id,
            implemented_baseline_crawl_job_id=None,
            times_marked_done=1,
            created_at=implemented_at,
            updated_at=implemented_at,
        )
    )


def _seed_implemented_summary_mix(
    session,
    *,
    site_id: int,
    active_crawl_id: int,
    baseline_crawl_id: int,
) -> None:
    gsc_improved_snapshot = {
        "signals": ["Impressions: 120", "Clicks: 9"],
        "reasons": ["The page already shows demand."],
        "recommendation": {
            "priority_score": 72,
            "cluster_strength": 55,
            "coverage_gap_score": 50,
            "internal_support_score": 35,
        },
        "gsc": {
            "available": True,
            "impressions": 120,
            "clicks": 9,
            "ctr": 0.075,
            "position": 9.4,
            "top_queries_count": 1,
            "notes": [],
        },
        "internal_linking": None,
        "cannibalization": None,
        "issue_flags": {
            "technical_issue_count": 0,
            "active_flags": [],
        },
    }
    _add_implemented_state(
        session,
        site_id=site_id,
        recommendation_key="summary-improved",
        recommendation_type="EXPAND_EXISTING_PAGE",
        segment="expand_existing_page",
        recommendation_text="Improved demand recommendation",
        primary_outcome_kind="gsc",
        implemented_at=FIXED_TIME - timedelta(days=45),
        implemented_crawl_job_id=baseline_crawl_id,
        signals_snapshot_json=gsc_improved_snapshot,
    )
    _add_implemented_state(
        session,
        site_id=site_id,
        recommendation_key="summary-worsened",
        recommendation_type="EXPAND_EXISTING_PAGE",
        segment="expand_existing_page",
        recommendation_text="Worsened demand recommendation",
        primary_outcome_kind="gsc",
        implemented_at=FIXED_TIME - timedelta(days=44),
        implemented_crawl_job_id=baseline_crawl_id,
        signals_snapshot_json={
            **gsc_improved_snapshot,
            "signals": ["Impressions: 260", "Clicks: 30"],
            "gsc": {
                "available": True,
                "impressions": 260,
                "clicks": 30,
                "ctr": 0.115,
                "position": 5.5,
                "top_queries_count": 3,
                "notes": [],
            },
        },
    )
    _add_implemented_state(
        session,
        site_id=site_id,
        recommendation_key="summary-unchanged",
        recommendation_type="EXPAND_EXISTING_PAGE",
        segment="expand_existing_page",
        recommendation_text="Stable demand recommendation",
        primary_outcome_kind="gsc",
        implemented_at=FIXED_TIME - timedelta(days=43),
        implemented_crawl_job_id=baseline_crawl_id,
        signals_snapshot_json={
            **gsc_improved_snapshot,
            "signals": ["Impressions: 200", "Clicks: 14"],
            "gsc": {
                "available": True,
                "impressions": 200,
                "clicks": 14,
                "ctr": 0.07,
                "position": 6.8,
                "top_queries_count": 2,
                "notes": [],
            },
        },
    )
    _add_implemented_state(
        session,
        site_id=site_id,
        recommendation_key="summary-too-early",
        recommendation_type="EXPAND_EXISTING_PAGE",
        segment="expand_existing_page",
        recommendation_text="Fresh demand recommendation",
        primary_outcome_kind="gsc",
        implemented_at=FIXED_TIME - timedelta(days=10),
        implemented_crawl_job_id=baseline_crawl_id,
        signals_snapshot_json=gsc_improved_snapshot,
    )
    _add_implemented_state(
        session,
        site_id=site_id,
        recommendation_key="summary-pending",
        recommendation_type="EXPAND_EXISTING_PAGE",
        segment="expand_existing_page",
        recommendation_text="Pending demand recommendation",
        primary_outcome_kind="gsc",
        implemented_at=FIXED_TIME - timedelta(days=1),
        implemented_crawl_job_id=active_crawl_id,
        signals_snapshot_json=gsc_improved_snapshot,
    )
    _add_implemented_state(
        session,
        site_id=site_id,
        recommendation_key="summary-limited",
        recommendation_type="EXPAND_EXISTING_PAGE",
        segment="expand_existing_page",
        recommendation_text="Limited demand recommendation",
        primary_outcome_kind="gsc",
        implemented_at=FIXED_TIME - timedelta(days=42),
        implemented_crawl_job_id=baseline_crawl_id,
        signals_snapshot_json={
            **gsc_improved_snapshot,
            "gsc": {
                "available": False,
                "impressions": 0,
                "clicks": 0,
                "ctr": 0.0,
                "position": None,
                "top_queries_count": 0,
                "notes": [],
            },
        },
    )
    _add_implemented_state(
        session,
        site_id=site_id,
        recommendation_key="summary-unavailable",
        recommendation_type="EXPAND_EXISTING_PAGE",
        segment="expand_existing_page",
        recommendation_text="Unavailable demand recommendation",
        primary_outcome_kind="gsc",
        implemented_at=FIXED_TIME - timedelta(days=41),
        implemented_crawl_job_id=None,
        signals_snapshot_json=gsc_improved_snapshot,
    )
    _add_implemented_state(
        session,
        site_id=site_id,
        recommendation_key="summary-internal-faq",
        recommendation_type="INTERNAL_LINKING_SUPPORT",
        segment="improve_internal_support",
        recommendation_text="Strengthen internal support for the FAQ page.",
        primary_outcome_kind="internal_linking",
        implemented_at=FIXED_TIME - timedelta(days=40),
        implemented_crawl_job_id=baseline_crawl_id,
        target_url="https://example.com/content-strategy/faq",
        normalized_target_url="https://example.com/content-strategy/faq",
        target_title_snapshot="Content strategy FAQ",
        signals_snapshot_json={
            "signals": ["Internal linking snapshot: 0 links from 0 pages"],
            "reasons": ["The FAQ page is underlinked."],
            "recommendation": {
                "priority_score": 61,
                "cluster_strength": 48,
                "coverage_gap_score": 35,
                "internal_support_score": 20,
            },
            "gsc": None,
            "internal_linking": {
                "internal_linking_score": 20,
                "issue_count": 4,
                "issue_types": ["WEAKLY_LINKED_IMPORTANT"],
                "incoming_internal_links": 0,
                "incoming_internal_linking_pages": 0,
                "link_equity_score": 5.0,
                "anchor_diversity_score": 10.0,
            },
            "cannibalization": None,
            "issue_flags": {
                "technical_issue_count": 0,
                "active_flags": [],
            },
        },
    )


def _assert_implemented_summary(
    payload: dict[str, object],
    *,
    total_count: int,
    status_counts: dict[str, int] | None = None,
    mode_counts: dict[str, int] | None = None,
) -> None:
    implemented_summary = payload["implemented_summary"]
    assert implemented_summary["total_count"] == total_count
    assert list(implemented_summary["status_counts"].keys()) == list(
        content_recommendation_service.IMPLEMENTED_OUTCOME_STATUS_ORDER
    )
    if status_counts is not None:
        for status, count in status_counts.items():
            assert implemented_summary["status_counts"][status] == count
    if mode_counts is not None:
        for mode, count in mode_counts.items():
            assert implemented_summary["mode_counts"][mode] == count


def test_content_recommendations_detect_core_types_scoring_and_taxonomy_reuse(sqlite_session_factory) -> None:
    site_id, crawl_job_id = seed_content_recommendation_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            gsc_date_range="last_28_days",
            page=1,
            page_size=50,
        )

        assert payload["context"]["active_crawl_id"] == crawl_job_id
        assert payload["context"]["baseline_crawl_id"] is None

        recommendation_types = {item["recommendation_type"] for item in payload["items"]}
        assert {
            "MISSING_SUPPORTING_CONTENT",
            "THIN_CLUSTER",
            "EXPAND_EXISTING_PAGE",
            "MISSING_STRUCTURAL_PAGE_TYPE",
            "INTERNAL_LINKING_SUPPORT",
        } <= recommendation_types

        assert payload["summary"]["counts_by_type"]["MISSING_SUPPORTING_CONTENT"] >= 1
        assert payload["summary"]["counts_by_type"]["THIN_CLUSTER"] >= 1
        assert payload["summary"]["counts_by_type"]["EXPAND_EXISTING_PAGE"] >= 1
        assert payload["summary"]["counts_by_type"]["MISSING_STRUCTURAL_PAGE_TYPE"] >= 1
        assert payload["summary"]["counts_by_type"]["INTERNAL_LINKING_SUPPORT"] >= 1

        expand_existing = next(
            item
            for item in payload["items"]
            if item["recommendation_type"] == "EXPAND_EXISTING_PAGE"
            and item["target_url"] == "https://example.com/content-strategy"
        )
        assert expand_existing["target_url"] == "https://example.com/content-strategy"
        assert expand_existing["page_type"] == "service"
        assert expand_existing["target_page_type"] == "service"
        assert 0.35 <= float(expand_existing["confidence"]) <= 0.95
        assert expand_existing["impact"] in {"low", "medium", "high"}
        assert expand_existing["effort"] in {"low", "medium", "high"}
        assert expand_existing["priority_score"] > 0
        assert expand_existing["rationale"]
        assert expand_existing["signals"]
        assert expand_existing["reasons"]
        helper = expand_existing["url_improvement_helper"]
        assert helper is not None
        assert helper["target_url"] == expand_existing["target_url"]
        assert helper["title"] == "Content strategy"
        assert helper["page_type"] == "service"
        assert helper["page_bucket"] == "commercial"
        assert helper["compare_context"] is None
        assert helper["open_issues"]
        assert any(
            "Snippet inputs" in issue or "weakly linked" in issue.lower()
            for issue in helper["open_issues"]
        )
        assert any("internal links" in action.lower() for action in helper["improvement_actions"])
        assert any("Priority score:" in signal for signal in helper["supporting_signals"])
        assert helper["gsc_context"]["impressions"] == 200
        assert helper["internal_linking_context"]["incoming_internal_linking_pages"] == 1
        assert helper["cannibalization_context"]["has_active_signals"] is True
        assert "content strategy" in helper["cannibalization_context"]["shared_top_queries"]

        structural = next(
            item for item in payload["items"] if item["recommendation_type"] == "MISSING_STRUCTURAL_PAGE_TYPE"
        )
        assert structural["page_type"] == "category"
        assert structural["target_page_type"] == "product"

        content_page = session.scalars(
            select(Page).where(Page.crawl_job_id == crawl_job_id, Page.url == "https://example.com/content-strategy")
        ).one()
        assert content_page.page_type == "service"
        assert content_page.page_type_version != "unclassified"


def test_content_recommendations_helper_returns_null_when_target_url_is_missing() -> None:
    helper = content_recommendation_service._build_url_improvement_helper(
        {"target_url": None, "target_page_id": None},
        active_page_by_id={},
        active_page_lookup={},
        internal_row_by_page_id={},
        gsc_suffix="28d",
        rules=content_recommendation_service.get_content_recommendation_rules(),
        baseline_crawl_id=None,
        baseline_page_by_normalized_url={},
        baseline_internal_by_normalized_url={},
    )
    assert helper is None


def test_content_recommendations_helper_adds_compare_context_when_baseline_exists(sqlite_session_factory) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            page=1,
            page_size=20,
        )

    expand_existing = next(
        item
        for item in payload["items"]
        if item["recommendation_type"] == "EXPAND_EXISTING_PAGE"
        and item["target_url"] == "https://example.com/content-strategy"
    )
    helper = expand_existing["url_improvement_helper"]
    assert helper is not None
    compare_context = helper["compare_context"]
    assert compare_context is not None
    assert compare_context["baseline_crawl_id"] == baseline_crawl_id

    compare_statuses = {signal["key"]: signal["status"] for signal in compare_context["signals"]}
    assert compare_statuses["technical_issues"] == "improved"
    assert compare_statuses["linking_pages"] == "improved"
    assert compare_statuses["top_queries"] == "improved"
    assert compare_statuses["cannibalization"] == "worsened"


def test_content_recommendation_key_is_deterministic(sqlite_session_factory) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        first_payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            page=1,
            page_size=50,
        )
        second_payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            page=1,
            page_size=50,
        )

    first_recommendation = _find_recommendation(
        first_payload,
        "EXPAND_EXISTING_PAGE",
        "https://example.com/content-strategy",
    )
    second_recommendation = _find_recommendation(
        second_payload,
        "EXPAND_EXISTING_PAGE",
        "https://example.com/content-strategy",
    )

    assert first_recommendation["recommendation_key"] == second_recommendation["recommendation_key"]
    assert first_recommendation["recommendation_key"] == build_content_recommendation_key(first_recommendation)


def test_mark_done_persists_state_hides_same_crawl_recommendation_and_returns_implemented(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    site_id, crawl_job_id = seed_content_recommendation_site(sqlite_session_factory)
    monkeypatch.setattr(content_recommendation_service, "utcnow", lambda: FIXED_TIME)

    initial_response = api_client.get(
        f"/sites/{site_id}/content-recommendations",
        params={"active_crawl_id": crawl_job_id, "gsc_date_range": "last_28_days"},
    )
    assert initial_response.status_code == 200
    initial_payload = initial_response.json()
    recommendation = next(
        item for item in initial_payload["items"] if item["recommendation_type"] == "EXPAND_EXISTING_PAGE"
    )

    mark_done_response = api_client.post(
        f"/sites/{site_id}/content-recommendations/mark-done",
        json={
            "recommendation_key": recommendation["recommendation_key"],
            "active_crawl_id": crawl_job_id,
            "gsc_date_range": "last_28_days",
        },
    )
    assert mark_done_response.status_code == 200
    assert mark_done_response.json()["implemented_at"] in {
        FIXED_TIME.isoformat(),
        FIXED_TIME.isoformat().replace("+00:00", "Z"),
    }

    with sqlite_session_factory() as session:
        state = session.scalar(
            select(SiteContentRecommendationState).where(
                SiteContentRecommendationState.site_id == site_id,
                SiteContentRecommendationState.recommendation_key == recommendation["recommendation_key"],
            )
        )
        assert state is not None
        assert state.implemented_crawl_job_id == crawl_job_id
        assert state.implemented_at.replace(tzinfo=timezone.utc) == FIXED_TIME
        assert state.times_marked_done == 1

    refreshed_response = api_client.get(
        f"/sites/{site_id}/content-recommendations",
        params={"active_crawl_id": crawl_job_id, "gsc_date_range": "last_28_days"},
    )
    assert refreshed_response.status_code == 200
    refreshed_payload = refreshed_response.json()

    active_keys = {item["recommendation_key"] for item in refreshed_payload["items"]}
    implemented_keys = {item["recommendation_key"] for item in refreshed_payload["implemented_items"]}

    assert recommendation["recommendation_key"] not in active_keys
    assert recommendation["recommendation_key"] in implemented_keys
    implemented = next(
        item
        for item in refreshed_payload["implemented_items"]
        if item["recommendation_key"] == recommendation["recommendation_key"]
    )
    assert implemented["outcome_status"] == "pending"
    assert refreshed_payload["summary"]["implemented_recommendations"] == 1


def test_same_recommendation_can_return_to_active_on_future_crawl(sqlite_session_factory, monkeypatch) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)
    monkeypatch.setattr(content_recommendation_service, "utcnow", lambda: FIXED_TIME)

    with sqlite_session_factory() as session:
        baseline_payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            page=1,
            page_size=50,
        )
        recommendation = _find_recommendation(
            baseline_payload,
            "EXPAND_EXISTING_PAGE",
            "https://example.com/content-strategy",
        )
        content_recommendation_service.mark_site_content_recommendation_done(
            session,
            site_id,
            recommendation_key=recommendation["recommendation_key"],
            active_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
        )

    with sqlite_session_factory() as session:
        future_payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            page=1,
            page_size=50,
        )

    active_keys = {item["recommendation_key"] for item in future_payload["items"]}
    implemented_keys = {item["recommendation_key"] for item in future_payload["implemented_items"]}

    assert recommendation["recommendation_key"] in active_keys
    assert recommendation["recommendation_key"] in implemented_keys


def test_implemented_recommendation_builds_gsc_outcome(sqlite_session_factory) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        session.add(
            SiteContentRecommendationState(
                site_id=site_id,
                recommendation_key="gsc-outcome-test",
                recommendation_type="EXPAND_EXISTING_PAGE",
                segment="expand_existing_page",
                target_url="https://example.com/content-strategy",
                normalized_target_url="https://example.com/content-strategy",
                target_title_snapshot="Content strategy",
                cluster_label="Content strategy",
                cluster_key="content",
                recommendation_text="Expand the existing URL because demand is already visible.",
                signals_snapshot_json={
                    "signals": ["Impressions: 120", "Clicks: 9"],
                    "reasons": ["The page already shows demand."],
                    "recommendation": {
                        "priority_score": 72,
                        "cluster_strength": 55,
                        "coverage_gap_score": 50,
                        "internal_support_score": 35,
                    },
                    "gsc": {
                        "available": True,
                        "impressions": 120,
                        "clicks": 9,
                        "ctr": 0.075,
                        "position": 9.4,
                        "top_queries_count": 1,
                        "notes": [],
                    },
                    "internal_linking": None,
                    "cannibalization": None,
                    "issue_flags": {
                        "technical_issue_count": 1,
                        "active_flags": ["thin_content"],
                    },
                },
                helper_snapshot_json=None,
                primary_outcome_kind="gsc",
                implemented_at=FIXED_TIME - timedelta(days=1),
                implemented_crawl_job_id=baseline_crawl_id,
                implemented_baseline_crawl_job_id=None,
                times_marked_done=1,
                created_at=FIXED_TIME - timedelta(days=1),
                updated_at=FIXED_TIME - timedelta(days=1),
            )
        )
        session.commit()

        payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="all",
            page=1,
            page_size=50,
        )

    implemented = next(
        item for item in payload["implemented_items"] if item["recommendation_key"] == "gsc-outcome-test"
    )
    assert implemented["outcome_status"] == "improved"
    assert any(detail["label"] == "Impressions" for detail in implemented["outcome_details"])
    assert "+5 clicks" in implemented["outcome_summary"] or "+80 impressions" in implemented["outcome_summary"]


def test_implemented_recommendation_builds_issue_driven_outcome(sqlite_session_factory) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        session.add(
            SiteContentRecommendationState(
                site_id=site_id,
                recommendation_key="internal-outcome-test",
                recommendation_type="INTERNAL_LINKING_SUPPORT",
                segment="improve_internal_support",
                target_url="https://example.com/content-strategy",
                normalized_target_url="https://example.com/content-strategy",
                target_title_snapshot="Content strategy",
                cluster_label="Content strategy",
                cluster_key="content",
                recommendation_text="Strengthen internal linking support for the URL.",
                signals_snapshot_json={
                    "signals": ["Internal linking snapshot: 0 links from 0 pages"],
                    "reasons": ["The page is important but underlinked."],
                    "recommendation": {
                        "priority_score": 72,
                        "cluster_strength": 55,
                        "coverage_gap_score": 50,
                        "internal_support_score": 25,
                    },
                    "gsc": None,
                    "internal_linking": {
                        "internal_linking_score": 20,
                        "issue_count": 4,
                        "issue_types": ["WEAKLY_LINKED_IMPORTANT"],
                        "incoming_internal_links": 0,
                        "incoming_internal_linking_pages": 0,
                        "link_equity_score": 5.0,
                        "anchor_diversity_score": 10.0,
                    },
                    "cannibalization": None,
                    "issue_flags": {
                        "technical_issue_count": 0,
                        "active_flags": [],
                    },
                },
                helper_snapshot_json=None,
                primary_outcome_kind="internal_linking",
                implemented_at=FIXED_TIME - timedelta(days=1),
                implemented_crawl_job_id=baseline_crawl_id,
                implemented_baseline_crawl_job_id=None,
                times_marked_done=1,
                created_at=FIXED_TIME - timedelta(days=1),
                updated_at=FIXED_TIME - timedelta(days=1),
            )
        )
        session.commit()

        payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="all",
            page=1,
            page_size=50,
        )

    implemented = next(
        item for item in payload["implemented_items"] if item["recommendation_key"] == "internal-outcome-test"
    )
    assert implemented["outcome_status"] == "improved"
    assert implemented["outcome_summary"] in {
        "Internal issues 4 -> 1",
        "Internal score 20 -> 54",
        "Linking pages 0 -> 1",
    }


def test_implemented_outcome_windows_and_too_early(sqlite_session_factory) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        _add_implemented_state(
            session,
            site_id=site_id,
            recommendation_key="windowed-gsc",
            recommendation_type="EXPAND_EXISTING_PAGE",
            segment="expand_existing_page",
            recommendation_text="Windowed GSC recommendation",
            primary_outcome_kind="gsc",
            implemented_at=FIXED_TIME - timedelta(days=10),
            implemented_crawl_job_id=baseline_crawl_id,
            signals_snapshot_json={
                "signals": ["Impressions: 120", "Clicks: 9"],
                "reasons": ["The page already shows demand."],
                "recommendation": {
                    "priority_score": 72,
                    "cluster_strength": 55,
                    "coverage_gap_score": 50,
                    "internal_support_score": 35,
                },
                "gsc": {
                    "available": True,
                    "impressions": 120,
                    "clicks": 9,
                    "ctr": 0.075,
                    "position": 9.4,
                    "top_queries_count": 1,
                    "notes": [],
                },
                "internal_linking": None,
                "cannibalization": None,
                "issue_flags": {
                    "technical_issue_count": 0,
                    "active_flags": [],
                },
            },
        )
        session.commit()

        payload_7d = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="7d",
            page=1,
            page_size=50,
        )
        payload_30d = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="30d",
            page=1,
            page_size=50,
        )
        payload_90d = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="90d",
            page=1,
            page_size=50,
        )
        payload_all = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="all",
            page=1,
            page_size=50,
        )

    outcome_7d = next(item for item in payload_7d["implemented_items"] if item["recommendation_key"] == "windowed-gsc")
    outcome_30d = next(item for item in payload_30d["implemented_items"] if item["recommendation_key"] == "windowed-gsc")
    outcome_90d = next(item for item in payload_90d["implemented_items"] if item["recommendation_key"] == "windowed-gsc")
    outcome_all = next(item for item in payload_all["implemented_items"] if item["recommendation_key"] == "windowed-gsc")

    assert outcome_7d["outcome_window"] == "7d"
    assert outcome_7d["outcome_status"] == "improved"
    assert outcome_7d["is_too_early"] is False
    assert outcome_7d["days_since_implemented"] == 10
    assert outcome_7d["eligible_for_window"] is True

    assert outcome_30d["outcome_window"] == "30d"
    assert outcome_30d["outcome_status"] == "too_early"
    assert outcome_30d["is_too_early"] is True
    assert outcome_30d["eligible_for_window"] is False
    assert outcome_30d["outcome_summary"] == "Too early to evaluate (30d window)."

    assert outcome_90d["outcome_window"] == "90d"
    assert outcome_90d["outcome_status"] == "too_early"
    assert outcome_90d["is_too_early"] is True

    assert outcome_all["outcome_window"] == "all"
    assert outcome_all["outcome_status"] == "improved"
    assert outcome_all["is_too_early"] is False
    assert outcome_all["eligible_for_window"] is True


def test_implemented_summary_counts_cover_status_mix(sqlite_session_factory) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        _seed_implemented_summary_mix(
            session,
            site_id=site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
        )
        session.commit()

        payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="30d",
            page=1,
            page_size=50,
        )

    assert payload["implemented_total"] == 8
    _assert_implemented_summary(
        payload,
        total_count=8,
        status_counts={
            "improved": 2,
            "worsened": 1,
            "unchanged": 1,
            "pending": 1,
            "limited": 1,
            "unavailable": 1,
            "too_early": 1,
        },
        mode_counts={
            "gsc": 7,
            "internal_linking": 1,
            "cannibalization": 0,
            "issue_flags": 0,
            "mixed": 0,
            "unknown": 0,
        },
    )


def test_implemented_summary_is_calculated_before_status_filter(sqlite_session_factory) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        _seed_implemented_summary_mix(
            session,
            site_id=site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
        )
        session.commit()

        payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="30d",
            implemented_status_filter="worsened",
            page=1,
            page_size=50,
        )

    assert payload["implemented_total"] == 1
    assert [item["recommendation_key"] for item in payload["implemented_items"]] == ["summary-worsened"]
    _assert_implemented_summary(
        payload,
        total_count=8,
        status_counts={
            "improved": 2,
            "worsened": 1,
            "unchanged": 1,
            "pending": 1,
            "limited": 1,
            "unavailable": 1,
            "too_early": 1,
        },
    )


def test_implemented_summary_reacts_to_mode_filter(sqlite_session_factory) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        _seed_implemented_summary_mix(
            session,
            site_id=site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
        )
        session.commit()

        payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="30d",
            implemented_mode_filter="internal_linking",
            page=1,
            page_size=50,
        )

    assert payload["implemented_total"] == 1
    assert [item["recommendation_key"] for item in payload["implemented_items"]] == ["summary-internal-faq"]
    _assert_implemented_summary(
        payload,
        total_count=1,
        status_counts={
            "improved": 1,
            "worsened": 0,
            "unchanged": 0,
            "pending": 0,
            "limited": 0,
            "unavailable": 0,
            "too_early": 0,
        },
        mode_counts={
            "gsc": 0,
            "internal_linking": 1,
            "cannibalization": 0,
            "issue_flags": 0,
            "mixed": 0,
            "unknown": 0,
        },
    )


def test_implemented_summary_reacts_to_outcome_window(sqlite_session_factory) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        _seed_implemented_summary_mix(
            session,
            site_id=site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
        )
        session.commit()

        payload_30d = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="30d",
            page=1,
            page_size=50,
        )
        payload_7d = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="7d",
            page=1,
            page_size=50,
        )

    _assert_implemented_summary(payload_30d, total_count=8)
    _assert_implemented_summary(payload_7d, total_count=8)
    assert payload_30d["implemented_summary"]["status_counts"]["too_early"] == 1
    assert payload_7d["implemented_summary"]["status_counts"]["too_early"] == 0
    assert payload_30d["implemented_summary"]["status_counts"]["improved"] == 2
    assert payload_7d["implemented_summary"]["status_counts"]["improved"] == 3


def test_implemented_summary_reacts_to_search(sqlite_session_factory) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        _seed_implemented_summary_mix(
            session,
            site_id=site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
        )
        session.commit()

        payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="30d",
            implemented_search="faq",
            page=1,
            page_size=50,
        )

    assert payload["implemented_total"] == 1
    assert [item["recommendation_key"] for item in payload["implemented_items"]] == ["summary-internal-faq"]
    _assert_implemented_summary(
        payload,
        total_count=1,
        status_counts={
            "improved": 1,
            "worsened": 0,
            "unchanged": 0,
            "pending": 0,
            "limited": 0,
            "unavailable": 0,
            "too_early": 0,
        },
        mode_counts={
            "gsc": 0,
            "internal_linking": 1,
            "cannibalization": 0,
            "issue_flags": 0,
            "mixed": 0,
            "unknown": 0,
        },
    )


def test_implemented_summary_survives_status_drilldown_after_mode_and_search(sqlite_session_factory) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        _seed_implemented_summary_mix(
            session,
            site_id=site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
        )
        session.commit()

        payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="30d",
            implemented_mode_filter="internal_linking",
            implemented_search="faq",
            implemented_status_filter="too_early",
            page=1,
            page_size=50,
        )

    assert payload["implemented_total"] == 0
    assert payload["implemented_items"] == []
    _assert_implemented_summary(
        payload,
        total_count=1,
        status_counts={
            "improved": 1,
            "unchanged": 0,
            "pending": 0,
            "too_early": 0,
            "limited": 0,
            "unavailable": 0,
            "worsened": 0,
        },
        mode_counts={
            "gsc": 0,
            "internal_linking": 1,
            "cannibalization": 0,
            "issue_flags": 0,
            "mixed": 0,
            "unknown": 0,
        },
    )


def test_implemented_filters_sort_and_search_are_applied_by_backend(sqlite_session_factory) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        _add_implemented_state(
            session,
            site_id=site_id,
            recommendation_key="improved-gsc",
            recommendation_type="EXPAND_EXISTING_PAGE",
            segment="expand_existing_page",
            recommendation_text="Improved demand recommendation",
            primary_outcome_kind="gsc",
            implemented_at=FIXED_TIME - timedelta(days=45),
            implemented_crawl_job_id=baseline_crawl_id,
            signals_snapshot_json={
                "signals": ["Impressions: 120", "Clicks: 9"],
                "reasons": ["The page already shows demand."],
                "recommendation": {
                    "priority_score": 72,
                    "cluster_strength": 55,
                    "coverage_gap_score": 50,
                    "internal_support_score": 35,
                },
                "gsc": {
                    "available": True,
                    "impressions": 120,
                    "clicks": 9,
                    "ctr": 0.075,
                    "position": 9.4,
                    "top_queries_count": 1,
                    "notes": [],
                },
                "internal_linking": None,
                "cannibalization": None,
                "issue_flags": {
                    "technical_issue_count": 0,
                    "active_flags": [],
                },
            },
        )
        _add_implemented_state(
            session,
            site_id=site_id,
            recommendation_key="worsened-gsc",
            recommendation_type="EXPAND_EXISTING_PAGE",
            segment="expand_existing_page",
            recommendation_text="Worsened demand recommendation",
            primary_outcome_kind="gsc",
            implemented_at=FIXED_TIME - timedelta(days=44),
            implemented_crawl_job_id=baseline_crawl_id,
            signals_snapshot_json={
                "signals": ["Impressions: 260", "Clicks: 30"],
                "reasons": ["Traffic was stronger at implementation time."],
                "recommendation": {
                    "priority_score": 72,
                    "cluster_strength": 55,
                    "coverage_gap_score": 50,
                    "internal_support_score": 35,
                },
                "gsc": {
                    "available": True,
                    "impressions": 260,
                    "clicks": 30,
                    "ctr": 0.115,
                    "position": 5.5,
                    "top_queries_count": 3,
                    "notes": [],
                },
                "internal_linking": None,
                "cannibalization": None,
                "issue_flags": {
                    "technical_issue_count": 0,
                    "active_flags": [],
                },
            },
        )
        _add_implemented_state(
            session,
            site_id=site_id,
            recommendation_key="fresh-gsc",
            recommendation_type="EXPAND_EXISTING_PAGE",
            segment="expand_existing_page",
            recommendation_text="Fresh demand recommendation",
            primary_outcome_kind="gsc",
            implemented_at=FIXED_TIME - timedelta(days=10),
            implemented_crawl_job_id=baseline_crawl_id,
            signals_snapshot_json={
                "signals": ["Impressions: 120", "Clicks: 9"],
                "reasons": ["Fresh recommendation for the same URL."],
                "recommendation": {
                    "priority_score": 72,
                    "cluster_strength": 55,
                    "coverage_gap_score": 50,
                    "internal_support_score": 35,
                },
                "gsc": {
                    "available": True,
                    "impressions": 120,
                    "clicks": 9,
                    "ctr": 0.075,
                    "position": 9.4,
                    "top_queries_count": 1,
                    "notes": [],
                },
                "internal_linking": None,
                "cannibalization": None,
                "issue_flags": {
                    "technical_issue_count": 0,
                    "active_flags": [],
                },
            },
        )
        _add_implemented_state(
            session,
            site_id=site_id,
            recommendation_key="internal-faq",
            recommendation_type="INTERNAL_LINKING_SUPPORT",
            segment="improve_internal_support",
            recommendation_text="Strengthen internal support for the secondary page.",
            primary_outcome_kind="internal_linking",
            implemented_at=FIXED_TIME - timedelta(days=45),
            implemented_crawl_job_id=baseline_crawl_id,
            target_url="https://example.com/content-strategy/faq",
            normalized_target_url="https://example.com/content-strategy/faq",
            target_title_snapshot="Content strategy FAQ",
            signals_snapshot_json={
                "signals": ["Internal linking snapshot: 0 links from 0 pages"],
                "reasons": ["The FAQ page is underlinked."],
                "recommendation": {
                    "priority_score": 61,
                    "cluster_strength": 48,
                    "coverage_gap_score": 35,
                    "internal_support_score": 20,
                },
                "gsc": None,
                "internal_linking": {
                    "internal_linking_score": 20,
                    "issue_count": 4,
                    "issue_types": ["WEAKLY_LINKED_IMPORTANT"],
                    "incoming_internal_links": 0,
                    "incoming_internal_linking_pages": 0,
                    "link_equity_score": 5.0,
                    "anchor_diversity_score": 10.0,
                },
                "cannibalization": None,
                "issue_flags": {
                    "technical_issue_count": 0,
                    "active_flags": [],
                },
            },
        )
        session.commit()

        too_early_payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="30d",
            implemented_status_filter="too_early",
            page=1,
            page_size=50,
        )
        mode_payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="all",
            implemented_mode_filter="internal_linking",
            page=1,
            page_size=50,
        )
        search_payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="all",
            implemented_search="faq",
            page=1,
            page_size=50,
        )
        sorted_payload = content_recommendation_service.build_site_content_recommendations(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
            baseline_crawl_id=baseline_crawl_id,
            gsc_date_range="last_28_days",
            implemented_outcome_window="30d",
            implemented_sort="outcome",
            page=1,
            page_size=50,
        )

    too_early_keys = {item["recommendation_key"] for item in too_early_payload["implemented_items"]}
    assert too_early_keys == {"fresh-gsc"}

    mode_keys = {item["recommendation_key"] for item in mode_payload["implemented_items"]}
    assert mode_keys == {"internal-faq"}
    assert all(item["primary_outcome_kind"] == "internal_linking" for item in mode_payload["implemented_items"])

    search_keys = {item["recommendation_key"] for item in search_payload["implemented_items"]}
    assert search_keys == {"internal-faq"}

    sorted_keys = [item["recommendation_key"] for item in sorted_payload["implemented_items"]]
    sorted_statuses = list(dict.fromkeys(str(item["outcome_status"]) for item in sorted_payload["implemented_items"]))
    expected_statuses = [
        status
        for status in content_recommendation_service.IMPLEMENTED_OUTCOME_STATUS_ORDER
        if status in set(sorted_statuses)
    ]
    assert sorted_statuses == expected_statuses
    assert sorted_keys.index("improved-gsc") < sorted_keys.index("fresh-gsc")
    assert sorted_keys.index("fresh-gsc") < sorted_keys.index("worsened-gsc")


def test_content_recommendations_endpoint_accepts_implemented_query_params(
    api_client,
    sqlite_session_factory,
) -> None:
    site_id, active_crawl_id, baseline_crawl_id = seed_content_recommendation_site_with_baseline(sqlite_session_factory)

    with sqlite_session_factory() as session:
        _add_implemented_state(
            session,
            site_id=site_id,
            recommendation_key="fresh-gsc-endpoint",
            recommendation_type="EXPAND_EXISTING_PAGE",
            segment="expand_existing_page",
            recommendation_text="Fresh endpoint recommendation",
            primary_outcome_kind="gsc",
            implemented_at=FIXED_TIME - timedelta(days=10),
            implemented_crawl_job_id=baseline_crawl_id,
            signals_snapshot_json={
                "signals": ["Impressions: 120", "Clicks: 9"],
                "reasons": ["Fresh recommendation for endpoint test."],
                "recommendation": {
                    "priority_score": 72,
                    "cluster_strength": 55,
                    "coverage_gap_score": 50,
                    "internal_support_score": 35,
                },
                "gsc": {
                    "available": True,
                    "impressions": 120,
                    "clicks": 9,
                    "ctr": 0.075,
                    "position": 9.4,
                    "top_queries_count": 1,
                    "notes": [],
                },
                "internal_linking": None,
                "cannibalization": None,
                "issue_flags": {
                    "technical_issue_count": 0,
                    "active_flags": [],
                },
            },
        )
        session.commit()

    response = api_client.get(
        f"/sites/{site_id}/content-recommendations",
        params={
            "active_crawl_id": active_crawl_id,
            "baseline_crawl_id": baseline_crawl_id,
            "gsc_date_range": "last_28_days",
            "implemented_outcome_window": "30d",
            "implemented_status_filter": "too_early",
            "implemented_mode_filter": "gsc",
            "implemented_search": "endpoint",
            "implemented_sort": "outcome",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["implemented_total"] == 1
    assert payload["implemented_summary"]["total_count"] == 1
    assert payload["implemented_summary"]["status_counts"]["too_early"] == 1
    assert payload["implemented_summary"]["mode_counts"]["gsc"] == 1
    assert payload["implemented_items"][0]["recommendation_key"] == "fresh-gsc-endpoint"
    assert payload["implemented_items"][0]["outcome_status"] == "too_early"
    assert payload["implemented_items"][0]["outcome_window"] == "30d"


def test_content_recommendations_endpoint_filters_and_sorts(api_client, sqlite_session_factory) -> None:
    site_id, _ = seed_content_recommendation_site(sqlite_session_factory)

    response = api_client.get(
        f"/sites/{site_id}/content-recommendations",
        params={
            "recommendation_type": "EXPAND_EXISTING_PAGE",
            "page_type": "service",
            "sort_by": "confidence",
            "sort_order": "desc",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["context"]["baseline_crawl_id"] is None
    assert payload["total_items"] >= 1
    assert payload["summary"]["implemented_recommendations"] == 0
    assert payload["implemented_items"] == []
    assert all(item["recommendation_type"] == "EXPAND_EXISTING_PAGE" for item in payload["items"])
    assert all(item["page_type"] == "service" for item in payload["items"])
    assert all("url_improvement_helper" in item for item in payload["items"])
    assert all("recommendation_key" in item for item in payload["items"])
    confidences = [item["confidence"] for item in payload["items"]]
    assert confidences == sorted(confidences, reverse=True)
    assert all(item["target_url"].startswith("https://example.com/") for item in payload["items"])


def test_content_recommendations_csv_export_reuses_filtered_payload(sqlite_session_factory) -> None:
    site_id, _ = seed_content_recommendation_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        csv_content = build_site_content_recommendations_csv(
            session,
            site_id,
            recommendation_type="MISSING_STRUCTURAL_PAGE_TYPE",
            sort_by="priority_score",
            sort_order="desc",
        )

    plain = csv_content.lstrip("\ufeff")
    rows = list(csv.DictReader(io.StringIO(plain)))

    assert "recommendation_type" in plain
    assert "cluster_label" in plain
    assert "suggested_page_type" in plain
    assert "priority_score" in plain
    assert "confidence" in plain
    assert "rationale" in plain
    assert len(rows) >= 1
    assert all(row["recommendation_type"] == "MISSING_STRUCTURAL_PAGE_TYPE" for row in rows)
    assert rows[0]["suggested_page_type"] == "category"
