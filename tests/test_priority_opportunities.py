from __future__ import annotations

from app.db.models import CrawlJob, CrawlJobStatus, GscProperty, GscTopQuery, GscUrlMetric, Link, Page, Site
from app.services import crawl_job_service


def seed_priority_job(session_factory) -> dict[str, int]:
    with session_factory() as session:
        site = Site(root_url="https://example.com/", domain="example.com")
        session.add(site)
        session.flush()

        crawl_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            settings_json={
                "start_url": "https://example.com/",
                "max_urls": 50,
                "max_depth": 3,
                "delay": 0.25,
                "request_delay": 0.25,
                "render_mode": "auto",
                "render_timeout_ms": 8000,
                "max_rendered_pages_per_job": 10,
            },
            stats_json={},
        )
        session.add(crawl_job)
        session.flush()

        gsc_property = GscProperty(
            site_id=site.id,
            property_uri="sc-domain:example.com",
            permission_level="siteOwner",
        )
        session.add(gsc_property)
        session.flush()

        root = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/",
            normalized_url="https://example.com/",
            final_url="https://example.com/",
            status_code=200,
            title="Home page title",
            title_length=15,
            meta_description="Home page meta description that is long enough for the test suite.",
            meta_description_length=62,
            h1="Homepage",
            h1_count=1,
            h2_count=2,
            canonical_url="https://example.com/",
            robots_meta="index,follow",
            x_robots_tag=None,
            content_type="text/html",
            word_count=500,
            content_text_hash="hash-root",
            images_count=2,
            images_missing_alt_count=0,
            html_size_bytes=1024,
            was_rendered=False,
            render_attempted=False,
            fetch_mode_used="http",
            js_heavy_like=False,
            render_reason=None,
            render_error_message=None,
            schema_present=True,
            schema_count=1,
            schema_types_json=["WebPage"],
            response_time_ms=20,
            is_internal=True,
            depth=0,
            fetched_at=None,
            error_message=None,
        )
        quick_win = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/quick-win",
            normalized_url="https://example.com/quick-win",
            final_url="https://example.com/quick-win",
            status_code=200,
            title="Q" * 72,
            title_length=72,
            meta_description="Quick win meta description that stays long enough to avoid an extra meta issue in this test.",
            meta_description_length=88,
            h1="Quick win",
            h1_count=1,
            h2_count=2,
            canonical_url="https://example.com/quick-win",
            robots_meta="index,follow",
            x_robots_tag=None,
            content_type="text/html",
            word_count=320,
            content_text_hash="hash-quick",
            images_count=3,
            images_missing_alt_count=0,
            html_size_bytes=2048,
            was_rendered=False,
            render_attempted=False,
            fetch_mode_used="http",
            js_heavy_like=False,
            render_reason=None,
            render_error_message=None,
            schema_present=True,
            schema_count=1,
            schema_types_json=["Article"],
            response_time_ms=30,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        )
        important_but_weak = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/important",
            normalized_url="https://example.com/important",
            final_url="https://example.com/important",
            status_code=200,
            title="Important page",
            title_length=14,
            meta_description="Important page meta description that is long enough.",
            meta_description_length=52,
            h1=None,
            h1_count=0,
            h2_count=0,
            canonical_url="https://example.com/important",
            robots_meta="index,follow",
            x_robots_tag=None,
            content_type="text/html",
            word_count=90,
            content_text_hash="hash-important",
            images_count=1,
            images_missing_alt_count=0,
            html_size_bytes=2048,
            was_rendered=False,
            render_attempted=False,
            fetch_mode_used="http",
            js_heavy_like=False,
            render_reason=None,
            render_error_message=None,
            schema_present=False,
            schema_count=0,
            schema_types_json=None,
            response_time_ms=26,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        )
        high_risk = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/high-risk",
            normalized_url="https://example.com/high-risk",
            final_url="https://example.com/high-risk",
            status_code=200,
            title="High risk page",
            title_length=14,
            meta_description="High risk meta description that is long enough for the audit thresholds.",
            meta_description_length=70,
            h1="High risk",
            h1_count=1,
            h2_count=1,
            canonical_url="https://example.com/",
            robots_meta="noindex,follow",
            x_robots_tag=None,
            content_type="text/html",
            word_count=240,
            content_text_hash="hash-high-risk",
            images_count=1,
            images_missing_alt_count=0,
            html_size_bytes=2048,
            was_rendered=False,
            render_attempted=False,
            fetch_mode_used="http",
            js_heavy_like=False,
            render_reason=None,
            render_error_message=None,
            schema_present=False,
            schema_count=0,
            schema_types_json=None,
            response_time_ms=28,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        )
        underlinked = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/underlinked",
            normalized_url="https://example.com/underlinked",
            final_url="https://example.com/underlinked",
            status_code=200,
            title="Underlinked page",
            title_length=16,
            meta_description="Underlinked page meta description that stays above the configured threshold.",
            meta_description_length=75,
            h1="Underlinked",
            h1_count=1,
            h2_count=2,
            canonical_url="https://example.com/underlinked",
            robots_meta="index,follow",
            x_robots_tag=None,
            content_type="text/html",
            word_count=260,
            content_text_hash="hash-underlinked",
            images_count=1,
            images_missing_alt_count=0,
            html_size_bytes=2048,
            was_rendered=False,
            render_attempted=False,
            fetch_mode_used="http",
            js_heavy_like=False,
            render_reason=None,
            render_error_message=None,
            schema_present=False,
            schema_count=0,
            schema_types_json=None,
            response_time_ms=24,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        )
        session.add_all([root, quick_win, important_but_weak, high_risk, underlinked])
        session.flush()

        session.add_all(
            [
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=root.id,
                    source_url=root.url,
                    target_url=quick_win.url,
                    target_normalized_url=quick_win.normalized_url,
                    target_domain="example.com",
                    anchor_text="Quick win",
                    rel_attr=None,
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=root.id,
                    source_url=root.url,
                    target_url=quick_win.url,
                    target_normalized_url=quick_win.normalized_url,
                    target_domain="example.com",
                    anchor_text="Quick win repeated",
                    rel_attr=None,
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=important_but_weak.id,
                    source_url=important_but_weak.url,
                    target_url=quick_win.url,
                    target_normalized_url=quick_win.normalized_url,
                    target_domain="example.com",
                    anchor_text="Quick win support",
                    rel_attr=None,
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=high_risk.id,
                    source_url=high_risk.url,
                    target_url=quick_win.url,
                    target_normalized_url=quick_win.normalized_url,
                    target_domain="example.com",
                    anchor_text="Quick win risk support",
                    rel_attr=None,
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=underlinked.id,
                    source_url=underlinked.url,
                    target_url=quick_win.url,
                    target_normalized_url=quick_win.normalized_url,
                    target_domain="example.com",
                    anchor_text="Quick win underlinked support",
                    rel_attr=None,
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=root.id,
                    source_url=root.url,
                    target_url=important_but_weak.url,
                    target_normalized_url=important_but_weak.normalized_url,
                    target_domain="example.com",
                    anchor_text="Important page",
                    rel_attr=None,
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=quick_win.id,
                    source_url=quick_win.url,
                    target_url=important_but_weak.url,
                    target_normalized_url=important_but_weak.normalized_url,
                    target_domain="example.com",
                    anchor_text="Important support",
                    rel_attr=None,
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=high_risk.id,
                    source_url=high_risk.url,
                    target_url=important_but_weak.url,
                    target_normalized_url=important_but_weak.normalized_url,
                    target_domain="example.com",
                    anchor_text="Important risk support",
                    rel_attr=None,
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=root.id,
                    source_url=root.url,
                    target_url=high_risk.url,
                    target_normalized_url=high_risk.normalized_url,
                    target_domain="example.com",
                    anchor_text="High risk page",
                    rel_attr=None,
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=important_but_weak.id,
                    source_url=important_but_weak.url,
                    target_url=high_risk.url,
                    target_normalized_url=high_risk.normalized_url,
                    target_domain="example.com",
                    anchor_text="High risk support",
                    rel_attr=None,
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=root.id,
                    source_url=root.url,
                    target_url=underlinked.url,
                    target_normalized_url=underlinked.normalized_url,
                    target_domain="example.com",
                    anchor_text="Underlinked page",
                    rel_attr=None,
                    is_nofollow=False,
                    is_internal=True,
                ),
            ]
        )

        session.add_all(
            [
                GscUrlMetric(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=quick_win.id,
                    url=quick_win.url,
                    normalized_url=quick_win.normalized_url,
                    date_range_label="last_28_days",
                    clicks=12,
                    impressions=500,
                    ctr=0.01,
                    position=8.2,
                ),
                GscUrlMetric(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=important_but_weak.id,
                    url=important_but_weak.url,
                    normalized_url=important_but_weak.normalized_url,
                    date_range_label="last_28_days",
                    clicks=18,
                    impressions=260,
                    ctr=0.0692,
                    position=11.0,
                ),
                GscUrlMetric(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=high_risk.id,
                    url=high_risk.url,
                    normalized_url=high_risk.normalized_url,
                    date_range_label="last_28_days",
                    clicks=12,
                    impressions=140,
                    ctr=0.0857,
                    position=5.6,
                ),
                GscUrlMetric(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=underlinked.id,
                    url=underlinked.url,
                    normalized_url=underlinked.normalized_url,
                    date_range_label="last_28_days",
                    clicks=4,
                    impressions=220,
                    ctr=0.018,
                    position=7.9,
                ),
            ]
        )

        session.add_all(
            [
                GscTopQuery(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=quick_win.id,
                    url=quick_win.url,
                    normalized_url=quick_win.normalized_url,
                    date_range_label="last_28_days",
                    query="quick win query",
                    clicks=6,
                    impressions=180,
                    ctr=0.0333,
                    position=7.4,
                ),
                GscTopQuery(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=quick_win.id,
                    url=quick_win.url,
                    normalized_url=quick_win.normalized_url,
                    date_range_label="last_28_days",
                    query="better ctr query",
                    clicks=3,
                    impressions=160,
                    ctr=0.0187,
                    position=8.8,
                ),
                GscTopQuery(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=quick_win.id,
                    url=quick_win.url,
                    normalized_url=quick_win.normalized_url,
                    date_range_label="last_28_days",
                    query="snippet query",
                    clicks=2,
                    impressions=90,
                    ctr=0.0222,
                    position=9.1,
                ),
                GscTopQuery(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=important_but_weak.id,
                    url=important_but_weak.url,
                    normalized_url=important_but_weak.normalized_url,
                    date_range_label="last_28_days",
                    query="important query",
                    clicks=10,
                    impressions=120,
                    ctr=0.0833,
                    position=10.4,
                ),
                GscTopQuery(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=underlinked.id,
                    url=underlinked.url,
                    normalized_url=underlinked.normalized_url,
                    date_range_label="last_28_days",
                    query="underlinked query",
                    clicks=4,
                    impressions=70,
                    ctr=0.0571,
                    position=8.0,
                ),
            ]
        )

        session.commit()
        return {
            "crawl_job_id": crawl_job.id,
            "quick_win_id": quick_win.id,
            "important_but_weak_id": important_but_weak.id,
            "high_risk_id": high_risk.id,
            "underlinked_id": underlinked.id,
        }


def test_priority_service_enriches_pages_and_classifies_opportunities(sqlite_session_factory) -> None:
    seed = seed_priority_job(sqlite_session_factory)

    with sqlite_session_factory() as session:
        records = crawl_job_service.get_all_pages_for_job(
            session,
            seed["crawl_job_id"],
            sort_by="priority_score",
            sort_order="desc",
            gsc_date_range="last_28_days",
        )

    by_url = {record["url"]: record for record in records}
    quick_win = by_url["https://example.com/quick-win"]
    important_but_weak = by_url["https://example.com/important"]
    high_risk = by_url["https://example.com/high-risk"]
    underlinked = by_url["https://example.com/underlinked"]

    assert quick_win["priority_score"] >= 45
    assert quick_win["traffic_component"] > 0
    assert quick_win["issue_component"] > 0
    assert "QUICK_WINS" in quick_win["opportunity_types"]
    assert "HIGH_IMPRESSIONS_LOW_CTR" in quick_win["opportunity_types"]
    assert "LOW_HANGING_FRUIT" in quick_win["opportunity_types"]
    assert "500 impressions" in quick_win["priority_rationale"]
    assert "title too long" in quick_win["priority_rationale"]

    assert "IMPORTANT_BUT_WEAK" in important_but_weak["opportunity_types"]
    assert "TRAFFIC_WITH_TECHNICAL_ISSUES" in important_but_weak["opportunity_types"]

    assert high_risk["priority_level"] == "critical"
    assert "HIGH_RISK_PAGES" in high_risk["opportunity_types"]
    assert "high-risk indexability or canonical problem" in high_risk["priority_rationale"]

    assert underlinked["internal_linking_component"] > 0
    assert "UNDERLINKED_OPPORTUNITIES" in underlinked["opportunity_types"]
    assert underlinked["priority_level"] in {"medium", "high"}


def test_pages_and_opportunities_endpoints_support_priority_filters(api_client, sqlite_session_factory) -> None:
    seed = seed_priority_job(sqlite_session_factory)

    pages_response = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/pages",
        params={"gsc_date_range": "last_28_days", "sort_by": "priority_score", "sort_order": "desc"},
    )
    assert pages_response.status_code == 200
    pages_payload = pages_response.json()
    assert pages_payload["items"][0]["url"] == "https://example.com/high-risk"
    assert pages_payload["items"][0]["priority_score"] >= pages_payload["items"][1]["priority_score"]

    critical_response = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/pages",
        params={"gsc_date_range": "last_28_days", "priority_level": "critical"},
    )
    assert critical_response.status_code == 200
    critical_urls = {item["url"] for item in critical_response.json()["items"]}
    assert critical_urls == {"https://example.com/high-risk"}

    underlinked_response = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/pages",
        params={"gsc_date_range": "last_28_days", "opportunity_type": "UNDERLINKED_OPPORTUNITIES"},
    )
    assert underlinked_response.status_code == 200
    underlinked_urls = {item["url"] for item in underlinked_response.json()["items"]}
    assert "https://example.com/underlinked" in underlinked_urls
    assert "https://example.com/high-risk" not in underlinked_urls

    opportunities_response = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/opportunities",
        params={"gsc_date_range": "last_28_days", "sort_by": "top_priority_score", "sort_order": "desc"},
    )
    assert opportunities_response.status_code == 200
    opportunities_payload = opportunities_response.json()
    groups = {group["type"]: group for group in opportunities_payload["groups"]}
    assert "QUICK_WINS" in groups
    assert "HIGH_IMPRESSIONS_LOW_CTR" in groups
    assert "TRAFFIC_WITH_TECHNICAL_ISSUES" in groups
    assert "IMPORTANT_BUT_WEAK" in groups
    assert "LOW_HANGING_FRUIT" in groups
    assert "HIGH_RISK_PAGES" in groups
    assert "UNDERLINKED_OPPORTUNITIES" in groups
    assert groups["HIGH_RISK_PAGES"]["top_pages"][0]["url"] == "https://example.com/high-risk"


def test_priority_exports_include_priority_and_opportunity_fields(api_client, sqlite_session_factory) -> None:
    seed = seed_priority_job(sqlite_session_factory)

    pages_export = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/export/pages.csv",
        params={"gsc_date_range": "last_28_days", "sort_by": "priority_score", "sort_order": "desc"},
    )
    assert pages_export.status_code == 200
    assert "priority_score" in pages_export.text
    assert "primary_opportunity_type" in pages_export.text
    assert "HIGH_RISK_PAGES" in pages_export.text
    assert "https://example.com/high-risk" in pages_export.text

    opportunities_export = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/export/opportunities.csv",
        params={"gsc_date_range": "last_28_days", "opportunity_type": "UNDERLINKED_OPPORTUNITIES"},
    )
    assert opportunities_export.status_code == 200
    assert "priority_score" in opportunities_export.text
    assert "https://example.com/underlinked" in opportunities_export.text
    assert "https://example.com/high-risk" not in opportunities_export.text
