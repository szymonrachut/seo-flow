from __future__ import annotations

from pytest import approx

from app.db.models import CrawlJob, CrawlJobStatus, GscProperty, GscTopQuery, GscUrlMetric, Link, Page, Site
from app.services import cannibalization_service


def seed_cannibalization_job(session_factory) -> dict[str, int]:
    with session_factory() as session:
        site = Site(root_url="https://example.com/", domain="example.com")
        session.add(site)
        session.flush()

        crawl_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            settings_json={"start_url": "https://example.com/"},
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

        def add_page(path: str, *, title: str, depth: int) -> Page:
            normalized_url = f"https://example.com{path}"
            page = Page(
                crawl_job_id=crawl_job.id,
                url=normalized_url,
                normalized_url=normalized_url,
                final_url=normalized_url,
                status_code=200,
                title=title,
                title_length=len(title),
                meta_description=f"{title} meta description for cannibalization tests.",
                meta_description_length=56,
                h1=title,
                h1_count=1,
                h2_count=2,
                canonical_url=normalized_url,
                robots_meta="index,follow",
                x_robots_tag=None,
                content_type="text/html",
                word_count=420,
                content_text_hash=f"hash-{path.strip('/').replace('/', '-') or 'home'}",
                images_count=2,
                images_missing_alt_count=0,
                html_size_bytes=1800,
                was_rendered=False,
                render_attempted=False,
                fetch_mode_used="http",
                js_heavy_like=False,
                render_reason=None,
                render_error_message=None,
                schema_present=False,
                schema_count=0,
                schema_types_json=None,
                response_time_ms=30,
                is_internal=True,
                depth=depth,
                fetched_at=None,
                error_message=None,
            )
            session.add(page)
            session.flush()
            return page

        home = add_page("/", title="Home", depth=0)
        alpha_primary = add_page("/alpha-primary", title="Alpha primary", depth=1)
        alpha_support = add_page("/alpha-support", title="Alpha support", depth=1)
        beta_a = add_page("/beta-a", title="Beta A", depth=1)
        beta_b = add_page("/beta-b", title="Beta B", depth=1)

        for target in [alpha_primary, alpha_support, beta_a, beta_b]:
            session.add(
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=home.id,
                    source_url=home.url,
                    target_url=target.url,
                    target_normalized_url=target.normalized_url,
                    target_domain="example.com",
                    anchor_text=target.title,
                    rel_attr="",
                    is_nofollow=False,
                    is_internal=True,
                )
            )

        session.add_all(
            [
                GscUrlMetric(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=alpha_primary.id,
                    url=alpha_primary.url,
                    normalized_url=alpha_primary.normalized_url,
                    date_range_label="last_28_days",
                    clicks=25,
                    impressions=300,
                    ctr=0.083,
                    position=4.5,
                ),
                GscUrlMetric(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=alpha_support.id,
                    url=alpha_support.url,
                    normalized_url=alpha_support.normalized_url,
                    date_range_label="last_28_days",
                    clicks=2,
                    impressions=30,
                    ctr=0.067,
                    position=7.2,
                ),
                GscUrlMetric(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=beta_a.id,
                    url=beta_a.url,
                    normalized_url=beta_a.normalized_url,
                    date_range_label="last_28_days",
                    clicks=18,
                    impressions=240,
                    ctr=0.075,
                    position=5.0,
                ),
                GscUrlMetric(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=beta_b.id,
                    url=beta_b.url,
                    normalized_url=beta_b.normalized_url,
                    date_range_label="last_28_days",
                    clicks=17,
                    impressions=232,
                    ctr=0.073,
                    position=5.1,
                ),
            ]
        )

        def add_query(page: Page, query: str, clicks: int, impressions: int, position: float) -> None:
            session.add(
                GscTopQuery(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=page.id,
                    url=page.url,
                    normalized_url=page.normalized_url,
                    date_range_label="last_28_days",
                    query=query,
                    clicks=clicks,
                    impressions=impressions,
                    ctr=round(clicks / impressions, 4),
                    position=position,
                )
            )

        add_query(alpha_primary, "alpha query", 10, 100, 3.0)
        add_query(alpha_primary, "alpha guide", 8, 80, 4.0)
        add_query(alpha_primary, "alpha comparison", 6, 60, 5.0)
        add_query(alpha_support, " Alpha Query ", 1, 15, 6.5)
        add_query(alpha_support, "alpha   guide", 1, 12, 7.0)
        add_query(alpha_support, "alpha faq", 0, 8, 9.5)

        add_query(beta_a, "beta service", 6, 120, 5.0)
        add_query(beta_a, "beta pricing", 4, 90, 5.2)
        add_query(beta_a, "beta integration", 2, 40, 4.6)
        add_query(beta_a, "beta migration", 2, 35, 4.8)
        add_query(beta_b, "beta service", 5, 110, 5.1)
        add_query(beta_b, "beta pricing", 4, 80, 5.0)
        add_query(beta_b, "beta checklist", 2, 42, 4.7)
        add_query(beta_b, "beta template", 2, 36, 4.9)

        session.commit()
        return {
            "crawl_job_id": crawl_job.id,
            "alpha_primary_id": alpha_primary.id,
            "alpha_support_id": alpha_support.id,
            "beta_a_id": beta_a.id,
            "beta_b_id": beta_b.id,
        }


def test_cannibalization_service_builds_overlap_clusters(sqlite_session_factory) -> None:
    seed = seed_cannibalization_job(sqlite_session_factory)

    with sqlite_session_factory() as session:
        payload = cannibalization_service.build_cannibalization_report(
            session,
            seed["crawl_job_id"],
            gsc_date_range="last_28_days",
            sort_by="severity",
            sort_order="desc",
        )
        support_details = cannibalization_service.build_cannibalization_page_details(
            session,
            seed["crawl_job_id"],
            seed["alpha_support_id"],
            gsc_date_range="last_28_days",
        )

    assert payload["summary"]["clusters_count"] == 2
    assert payload["summary"]["pages_in_conflicts"] == 4
    assert payload["summary"]["no_clear_primary_clusters"] == 1

    by_recommendation = {item["recommendation_type"]: item for item in payload["items"]}
    merge_candidate = by_recommendation["MERGE_CANDIDATE"]
    split_intent = by_recommendation["SPLIT_INTENT_CANDIDATE"]

    assert merge_candidate["dominant_url"] == "https://example.com/alpha-primary"
    assert merge_candidate["has_clear_primary"] is True
    assert merge_candidate["shared_queries_count"] == 2
    assert merge_candidate["weighted_overlap"] > 0.95

    assert split_intent["dominant_url"] is None
    assert split_intent["has_clear_primary"] is False
    assert split_intent["candidate_urls"][0]["exclusive_query_count"] >= 2

    strongest_overlap = support_details["overlaps"][0]
    assert support_details["strongest_competing_url"] == "https://example.com/alpha-primary"
    assert strongest_overlap["common_queries_count"] == 2
    assert strongest_overlap["weighted_overlap_by_impressions"] == approx(1.0)
    assert strongest_overlap["weighted_overlap_by_clicks"] == approx(1.0)
    assert strongest_overlap["dominant_url"] == "https://example.com/alpha-primary"


def test_cannibalization_api_pages_filter_and_export(api_client, sqlite_session_factory) -> None:
    seed = seed_cannibalization_job(sqlite_session_factory)

    list_response = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/cannibalization",
        params={"recommendation_type": "MERGE_CANDIDATE"},
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["recommendation_type"] == "MERGE_CANDIDATE"

    details_response = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/cannibalization/pages/{seed['beta_a_id']}",
        params={"gsc_date_range": "last_28_days"},
    )
    assert details_response.status_code == 200
    assert details_response.json()["has_cannibalization"] is True
    assert details_response.json()["overlaps"][0]["competing_url"] == "https://example.com/beta-b"

    pages_response = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/pages",
        params={"has_cannibalization": "true"},
    )
    assert pages_response.status_code == 200
    returned_urls = {item["url"] for item in pages_response.json()["items"]}
    assert returned_urls == {
        "https://example.com/alpha-primary",
        "https://example.com/alpha-support",
        "https://example.com/beta-a",
        "https://example.com/beta-b",
    }

    export_response = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/export/cannibalization.csv",
        params={"recommendation_type": "MERGE_CANDIDATE"},
    )
    assert export_response.status_code == 200
    assert "cluster_id" in export_response.text
    assert "MERGE_CANDIDATE" in export_response.text
    assert "SPLIT_INTENT_CANDIDATE" not in export_response.text
