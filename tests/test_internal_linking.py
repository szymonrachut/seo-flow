from __future__ import annotations

from app.db.models import CrawlJob, CrawlJobStatus, GscProperty, GscUrlMetric, Link, Page, Site
from app.services import internal_linking_service


def seed_internal_linking_job(session_factory) -> dict[str, int]:
    with session_factory() as session:
        site = Site(root_url="https://example.com/", domain="example.com")
        session.add(site)
        session.flush()

        crawl_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            settings_json={
                "start_url": "https://example.com/",
                "max_urls": 100,
                "max_depth": 4,
                "delay": 0.25,
                "request_delay": 0.25,
                "render_mode": "auto",
                "render_timeout_ms": 8000,
                "max_rendered_pages_per_job": 15,
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

        def add_page(path: str, *, title: str, h1: str | None, depth: int, word_count: int = 280) -> Page:
            normalized_url = f"https://example.com{path}"
            page = Page(
                crawl_job_id=crawl_job.id,
                url=normalized_url,
                normalized_url=normalized_url,
                final_url=normalized_url,
                status_code=200,
                title=title,
                title_length=len(title),
                meta_description=f"{title} meta description that is long enough for the tests.",
                meta_description_length=70,
                h1=h1,
                h1_count=0 if h1 is None else 1,
                h2_count=2,
                canonical_url=normalized_url,
                robots_meta="index,follow",
                x_robots_tag=None,
                content_type="text/html",
                word_count=word_count,
                content_text_hash=f"hash-{path.strip('/').replace('/', '-') or 'home'}",
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
                response_time_ms=30,
                is_internal=True,
                depth=depth,
                fetched_at=None,
                error_message=None,
            )
            session.add(page)
            session.flush()
            return page

        root = add_page("/", title="Homepage", h1="Homepage", depth=0, word_count=520)
        blog_1 = add_page("/blog-1", title="Blog 1", h1="Blog 1", depth=1)
        blog_2 = add_page("/blog-2", title="Blog 2", h1="Blog 2", depth=1)
        blog_3 = add_page("/blog-3", title="Blog 3", h1="Blog 3", depth=1)
        blog_4 = add_page("/blog-4", title="Blog 4", h1="Blog 4", depth=1)
        seo_services = add_page("/seo-services", title="SEO Services", h1="SEO Services", depth=1, word_count=360)
        migration = add_page("/migration-guide", title="Site Migration Guide", h1="Migration guide", depth=2, word_count=240)
        case_study = add_page("/case-study", title="SEO Case Study", h1="Case study", depth=2, word_count=340)
        orphan = add_page("/orphan", title="Hidden Resource", h1="Hidden resource", depth=2, word_count=150)

        def add_link(source_page: Page, target_page: Page, anchor_text: str, *, nofollow: bool = False) -> None:
            session.add(
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=source_page.id,
                    source_url=source_page.url,
                    target_url=target_page.url,
                    target_normalized_url=target_page.normalized_url,
                    target_domain="example.com",
                    anchor_text=anchor_text,
                    rel_attr="nofollow" if nofollow else "",
                    is_nofollow=nofollow,
                    is_internal=True,
                )
            )

        for page in [blog_1, blog_2, blog_3, blog_4, seo_services, case_study]:
            add_link(root, page, page.title)

        add_link(blog_1, seo_services, "SEO Services")
        add_link(blog_2, seo_services, "SEO Services")
        add_link(blog_3, seo_services, "SEO Services")
        add_link(blog_4, seo_services, "technical SEO services")

        add_link(blog_1, migration, "migration guide")
        add_link(blog_3, migration, "migration guide", nofollow=True)

        add_link(blog_2, case_study, "organic growth story")
        add_link(blog_4, case_study, "technical SEO example")

        session.add_all(
            [
                GscUrlMetric(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=seo_services.id,
                    url=seo_services.url,
                    normalized_url=seo_services.normalized_url,
                    date_range_label="last_28_days",
                    clicks=18,
                    impressions=500,
                    ctr=0.036,
                    position=8.0,
                ),
                GscUrlMetric(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=migration.id,
                    url=migration.url,
                    normalized_url=migration.normalized_url,
                    date_range_label="last_28_days",
                    clicks=12,
                    impressions=260,
                    ctr=0.046,
                    position=11.2,
                ),
                GscUrlMetric(
                    gsc_property_id=gsc_property.id,
                    crawl_job_id=crawl_job.id,
                    page_id=case_study.id,
                    url=case_study.url,
                    normalized_url=case_study.normalized_url,
                    date_range_label="last_28_days",
                    clicks=8,
                    impressions=140,
                    ctr=0.057,
                    position=7.4,
                ),
            ]
        )

        session.commit()
        return {
            "crawl_job_id": crawl_job.id,
            "root_id": root.id,
            "seo_services_id": seo_services.id,
            "migration_id": migration.id,
            "case_study_id": case_study.id,
            "orphan_id": orphan.id,
        }


def test_internal_linking_service_classifies_stage9_signals(sqlite_session_factory) -> None:
    seed = seed_internal_linking_job(sqlite_session_factory)

    with sqlite_session_factory() as session:
        overview = internal_linking_service.build_internal_linking_overview(
            session,
            seed["crawl_job_id"],
            gsc_date_range="last_28_days",
        )
        rows = internal_linking_service.get_all_internal_linking_issue_rows(
            session,
            seed["crawl_job_id"],
            gsc_date_range="last_28_days",
            sort_by="internal_linking_score",
            sort_order="desc",
        )

    assert overview["orphan_like_pages"] == 1
    assert overview["weakly_linked_important_pages"] == 1
    assert overview["low_anchor_diversity_pages"] == 1
    assert overview["exact_match_anchor_concentration_pages"] == 1
    assert overview["boilerplate_dominated_pages"] == 1
    assert overview["low_link_equity_pages"] == 1

    by_url = {row["url"]: row for row in rows}
    assert "https://example.com/" not in by_url

    seo_services = by_url["https://example.com/seo-services"]
    assert seo_services["low_anchor_diversity"] is True
    assert seo_services["exact_match_anchor_concentration"] is True
    assert seo_services["boilerplate_dominated"] is True
    assert seo_services["boilerplate_like_links"] > seo_services["body_like_links"]
    assert seo_services["exact_match_anchor_ratio"] >= 0.6

    migration = by_url["https://example.com/migration-guide"]
    assert migration["weakly_linked_important"] is True
    assert migration["low_link_equity"] is True
    assert migration["incoming_follow_linking_pages"] == 1
    assert migration["incoming_nofollow_links"] == 1

    orphan = by_url["https://example.com/orphan"]
    assert orphan["orphan_like"] is True
    assert orphan["incoming_follow_links"] == 0


def test_internal_linking_api_and_export_support_filters(api_client, sqlite_session_factory) -> None:
    seed = seed_internal_linking_job(sqlite_session_factory)

    overview_response = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/internal-linking/overview",
        params={"gsc_date_range": "last_28_days"},
    )
    assert overview_response.status_code == 200
    assert overview_response.json()["issue_pages"] >= 3

    issues_response = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/internal-linking/issues",
        params={"gsc_date_range": "last_28_days", "issue_type": "LOW_LINK_EQUITY"},
    )
    assert issues_response.status_code == 200
    issue_urls = {item["url"] for item in issues_response.json()["items"]}
    assert issue_urls == {"https://example.com/migration-guide"}

    pages_response = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/pages",
        params={"url_contains": "migration-guide"},
    )
    assert pages_response.status_code == 200
    assert [item["url"] for item in pages_response.json()["items"]] == ["https://example.com/migration-guide"]

    export_response = api_client.get(
        f"/crawl-jobs/{seed['crawl_job_id']}/export/internal-linking.csv",
        params={"issue_type": "BOILERPLATE_DOMINATED"},
    )
    assert export_response.status_code == 200
    assert "primary_issue_type" in export_response.text
    assert "https://example.com/seo-services" in export_response.text
    assert "https://example.com/migration-guide" not in export_response.text
