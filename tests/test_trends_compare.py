from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.models import CrawlJob, CrawlJobStatus, GscProperty, GscTopQuery, GscUrlMetric, Link, Page, Site
from app.services import export_service, trends_service


def _make_page(
    crawl_job_id: int,
    url: str,
    *,
    title: str = "Default page title",
    meta_description: str = "Default meta description that is comfortably above the configured thresholds.",
    h1: str | None = "Default heading",
    h1_count: int = 1,
    h2_count: int = 1,
    canonical_url: str | None = None,
    robots_meta: str | None = "index,follow",
    word_count: int = 260,
    images_missing_alt_count: int = 0,
    schema_count: int = 1,
    html_size_bytes: int = 2200,
    was_rendered: bool = False,
    js_heavy_like: bool = False,
    response_time_ms: int = 120,
    depth: int = 1,
) -> Page:
    canonical = canonical_url or url
    return Page(
        crawl_job_id=crawl_job_id,
        url=url,
        normalized_url=url,
        final_url=url,
        status_code=200,
        title=title,
        title_length=len(title),
        meta_description=meta_description,
        meta_description_length=len(meta_description),
        h1=h1,
        h1_count=h1_count,
        h2_count=h2_count,
        canonical_url=canonical,
        robots_meta=robots_meta,
        x_robots_tag=None,
        content_type="text/html",
        word_count=word_count,
        content_text_hash=f"hash-{url.rsplit('/', 1)[-1] or 'root'}-{crawl_job_id}",
        images_count=3,
        images_missing_alt_count=images_missing_alt_count,
        html_size_bytes=html_size_bytes,
        was_rendered=was_rendered,
        render_attempted=was_rendered,
        fetch_mode_used="playwright" if was_rendered else "http",
        js_heavy_like=js_heavy_like,
        render_reason="heuristic" if was_rendered else None,
        render_error_message=None,
        schema_present=schema_count > 0,
        schema_count=schema_count,
        schema_types_json=["Article"] if schema_count > 0 else None,
        response_time_ms=response_time_ms,
        is_internal=True,
        depth=depth,
        fetched_at=None,
        error_message=None,
    )


def _add_link(session, *, crawl_job_id: int, source_page: Page, target_page: Page, anchor_text: str) -> None:
    session.add(
        Link(
            crawl_job_id=crawl_job_id,
            source_page_id=source_page.id,
            source_url=source_page.url,
            target_url=target_page.url,
            target_normalized_url=target_page.normalized_url,
            target_domain="example.com",
            anchor_text=anchor_text,
            rel_attr=None,
            is_nofollow=False,
            is_internal=True,
        )
    )


def _add_metric(
    session,
    *,
    gsc_property_id: int,
    crawl_job_id: int,
    page: Page,
    date_range_label: str,
    clicks: int,
    impressions: int,
    ctr: float,
    position: float | None,
) -> None:
    session.add(
        GscUrlMetric(
            gsc_property_id=gsc_property_id,
            crawl_job_id=crawl_job_id,
            page_id=page.id,
            url=page.url,
            normalized_url=page.normalized_url,
            date_range_label=date_range_label,
            clicks=clicks,
            impressions=impressions,
            ctr=ctr,
            position=position,
        )
    )


def _add_top_queries(
    session,
    *,
    gsc_property_id: int,
    crawl_job_id: int,
    page: Page,
    date_range_label: str,
    count: int,
    clicks_start: int = 1,
) -> None:
    for index in range(count):
        session.add(
            GscTopQuery(
                gsc_property_id=gsc_property_id,
                crawl_job_id=crawl_job_id,
                page_id=page.id,
                url=page.url,
                normalized_url=page.normalized_url,
                date_range_label=date_range_label,
                query=f"{page.normalized_url.rsplit('/', 1)[-1] or 'root'}-{date_range_label}-query-{index + 1}",
                clicks=clicks_start + index,
                impressions=80 + index * 10,
                ctr=0.05,
                position=8.0 + index,
            )
        )


def seed_trends_jobs(session_factory) -> dict[str, int]:
    with session_factory() as session:
        now = datetime.now(timezone.utc)
        site = Site(root_url="https://example.com/", domain="example.com")
        other_site = Site(root_url="https://other.example/", domain="other.example")
        session.add_all([site, other_site])
        session.flush()

        baseline_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=now - timedelta(days=7),
            started_at=now - timedelta(days=7, minutes=-1),
            finished_at=now - timedelta(days=7, minutes=-3),
            settings_json={"start_url": "https://example.com/", "render_mode": "auto"},
            stats_json={},
        )
        target_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=now,
            started_at=now - timedelta(minutes=6),
            finished_at=now - timedelta(minutes=2),
            settings_json={"start_url": "https://example.com/", "render_mode": "auto"},
            stats_json={},
        )
        foreign_job = CrawlJob(
            site_id=other_site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=now - timedelta(days=1),
            settings_json={"start_url": "https://other.example/", "render_mode": "auto"},
            stats_json={},
        )
        session.add_all([baseline_job, target_job, foreign_job])
        session.flush()

        gsc_property = GscProperty(site_id=site.id, property_uri="sc-domain:example.com", permission_level="siteOwner")
        session.add(gsc_property)
        session.flush()

        baseline_root = _make_page(baseline_job.id, "https://example.com/", depth=0)
        baseline_improved = _make_page(
            baseline_job.id,
            "https://example.com/improved",
            robots_meta="noindex,follow",
            word_count=110,
            images_missing_alt_count=2,
            schema_count=0,
            response_time_ms=520,
        )
        baseline_worsened = _make_page(
            baseline_job.id,
            "https://example.com/worsened",
            word_count=330,
            images_missing_alt_count=0,
            schema_count=1,
            response_time_ms=120,
        )
        baseline_stable = _make_page(baseline_job.id, "https://example.com/stable", word_count=210, response_time_ms=140)
        baseline_missing = _make_page(
            baseline_job.id,
            "https://example.com/missing",
            word_count=180,
            images_missing_alt_count=1,
            schema_count=0,
            response_time_ms=180,
        )
        session.add_all([baseline_root, baseline_improved, baseline_worsened, baseline_stable, baseline_missing])
        session.flush()

        target_root = _make_page(target_job.id, "https://example.com/", depth=0)
        target_improved = _make_page(
            target_job.id,
            "https://example.com/improved",
            robots_meta="index,follow",
            word_count=240,
            images_missing_alt_count=0,
            schema_count=2,
            response_time_ms=160,
        )
        target_worsened = _make_page(
            target_job.id,
            "https://example.com/worsened",
            canonical_url="https://example.com/",
            word_count=170,
            images_missing_alt_count=2,
            schema_count=0,
            response_time_ms=410,
        )
        target_stable = _make_page(target_job.id, "https://example.com/stable", word_count=212, response_time_ms=145)
        target_new = _make_page(
            target_job.id,
            "https://example.com/new",
            title="Brand new page",
            word_count=230,
            schema_count=1,
            response_time_ms=210,
        )
        session.add_all([target_root, target_improved, target_worsened, target_stable, target_new])
        session.flush()

        other_page = _make_page(foreign_job.id, "https://other.example/page", depth=0)
        session.add(other_page)
        session.flush()

        _add_link(session, crawl_job_id=baseline_job.id, source_page=baseline_root, target_page=baseline_improved, anchor_text="Improved")
        _add_link(session, crawl_job_id=baseline_job.id, source_page=baseline_root, target_page=baseline_worsened, anchor_text="Worsened")
        _add_link(session, crawl_job_id=baseline_job.id, source_page=baseline_stable, target_page=baseline_worsened, anchor_text="Worsened support")
        _add_link(session, crawl_job_id=baseline_job.id, source_page=baseline_missing, target_page=baseline_worsened, anchor_text="Worsened support 2")
        _add_link(session, crawl_job_id=baseline_job.id, source_page=baseline_root, target_page=baseline_stable, anchor_text="Stable")
        _add_link(session, crawl_job_id=baseline_job.id, source_page=baseline_root, target_page=baseline_missing, anchor_text="Missing")

        _add_link(session, crawl_job_id=target_job.id, source_page=target_root, target_page=target_improved, anchor_text="Improved")
        _add_link(session, crawl_job_id=target_job.id, source_page=target_stable, target_page=target_improved, anchor_text="Improved support")
        _add_link(session, crawl_job_id=target_job.id, source_page=target_new, target_page=target_improved, anchor_text="Improved support 2")
        _add_link(session, crawl_job_id=target_job.id, source_page=target_root, target_page=target_worsened, anchor_text="Worsened")
        _add_link(session, crawl_job_id=target_job.id, source_page=target_root, target_page=target_stable, anchor_text="Stable")
        _add_link(session, crawl_job_id=target_job.id, source_page=target_root, target_page=target_new, anchor_text="New")

        for page, clicks, impressions, ctr, position in [
            (baseline_root, 5, 60, 0.0833, 5.5),
            (baseline_improved, 8, 100, 0.08, 14.0),
            (baseline_worsened, 18, 200, 0.09, 6.0),
            (baseline_stable, 9, 110, 0.0818, 7.2),
            (baseline_missing, 6, 90, 0.0667, 12.0),
        ]:
            _add_metric(
                session,
                gsc_property_id=gsc_property.id,
                crawl_job_id=baseline_job.id,
                page=page,
                date_range_label="last_28_days",
                clicks=clicks,
                impressions=impressions,
                ctr=ctr,
                position=position,
            )

        for page, clicks, impressions, ctr, position, query_count in [
            (target_improved, 40, 500, 0.08, 6.0, 4),
            (target_worsened, 5, 120, 0.0417, 9.0, 1),
            (target_stable, 10, 103, 0.0971, 7.1, 1),
            (target_new, 7, 160, 0.0438, 11.0, 2),
        ]:
            _add_metric(
                session,
                gsc_property_id=gsc_property.id,
                crawl_job_id=target_job.id,
                page=page,
                date_range_label="last_28_days",
                clicks=clicks,
                impressions=impressions,
                ctr=ctr,
                position=position,
            )
            _add_top_queries(
                session,
                gsc_property_id=gsc_property.id,
                crawl_job_id=target_job.id,
                page=page,
                date_range_label="last_28_days",
                count=query_count,
            )

        for page, clicks, impressions, ctr, position, query_count in [
            (target_root, 15, 180, 0.0833, 5.0, 2),
            (target_improved, 30, 300, 0.1, 10.0, 2),
            (target_worsened, 20, 250, 0.08, 4.5, 3),
            (target_stable, 10, 100, 0.1, 7.0, 1),
        ]:
            _add_metric(
                session,
                gsc_property_id=gsc_property.id,
                crawl_job_id=target_job.id,
                page=page,
                date_range_label="last_90_days",
                clicks=clicks,
                impressions=impressions,
                ctr=ctr,
                position=position,
            )
            _add_top_queries(
                session,
                gsc_property_id=gsc_property.id,
                crawl_job_id=target_job.id,
                page=page,
                date_range_label="last_90_days",
                count=query_count,
                clicks_start=2,
            )

        session.commit()
        return {
            "site_id": site.id,
            "baseline_job_id": baseline_job.id,
            "target_job_id": target_job.id,
            "foreign_job_id": foreign_job.id,
        }


def test_trends_service_builds_crawl_compare_and_rationales(sqlite_session_factory) -> None:
    seed = seed_trends_jobs(sqlite_session_factory)

    with sqlite_session_factory() as session:
        payload = trends_service.build_crawl_compare(
            session,
            seed["target_job_id"],
            baseline_job_id=seed["baseline_job_id"],
            gsc_date_range="last_28_days",
            sort_by="url",
            sort_order="asc",
            page_size=100,
        )

    assert payload["summary"]["shared_urls"] == 4
    assert payload["summary"]["new_urls"] == 1
    assert payload["summary"]["missing_urls"] == 1
    by_url = {item["url"]: item for item in payload["items"]}

    improved = by_url["https://example.com/improved"]
    worsened = by_url["https://example.com/worsened"]
    missing = by_url["https://example.com/missing"]
    new_page = by_url["https://example.com/new"]

    assert improved["change_type"] == "improved"
    assert improved["issues_resolved_count"] >= 1
    assert improved["delta_incoming_internal_links"] == 2
    assert "resolved" in improved["change_rationale"]
    assert "gained 2 internal links" in improved["change_rationale"]

    assert worsened["change_type"] == "worsened"
    assert worsened["issues_added_count"] >= 1
    assert worsened["delta_incoming_internal_links"] == -2
    assert "added canonical issue" in worsened["change_rationale"]

    assert missing["change_type"] == "missing"
    assert missing["missing_in_target"] is True
    assert new_page["change_type"] == "new"
    assert new_page["new_in_target"] is True


def test_trends_service_blocks_cross_site_crawl_compare(sqlite_session_factory) -> None:
    seed = seed_trends_jobs(sqlite_session_factory)

    with sqlite_session_factory() as session:
        try:
            trends_service.build_crawl_compare(
                session,
                seed["target_job_id"],
                baseline_job_id=seed["foreign_job_id"],
            )
        except trends_service.TrendsServiceError as exc:
            assert "same site" in str(exc)
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected same-site validation error.")


def test_gsc_compare_service_builds_summary_and_handles_missing_ranges(sqlite_session_factory) -> None:
    seed = seed_trends_jobs(sqlite_session_factory)

    with sqlite_session_factory() as session:
        payload = trends_service.build_gsc_compare(
            session,
            seed["target_job_id"],
            baseline_gsc_range="last_90_days",
            target_gsc_range="last_28_days",
            sort_by="url",
            sort_order="asc",
            page_size=100,
        )

    assert payload["summary"]["baseline_gsc_range"] == "last_90_days"
    assert payload["summary"]["target_gsc_range"] == "last_28_days"
    assert payload["summary"]["improved_urls"] >= 1
    assert payload["summary"]["worsened_urls"] >= 1
    assert payload["summary"]["flat_urls"] >= 1

    by_url = {item["url"]: item for item in payload["items"]}
    assert by_url["https://example.com/improved"]["overall_trend"] == "improved"
    assert by_url["https://example.com/worsened"]["overall_trend"] == "worsened"
    assert by_url["https://example.com/stable"]["overall_trend"] == "flat"
    assert by_url["https://example.com/new"]["has_baseline_data"] is False
    assert by_url["https://example.com/"]["has_target_data"] is False
    assert "clicks up" in by_url["https://example.com/improved"]["rationale"]


def test_trends_api_endpoints_support_filters_sorting_and_exports(api_client, sqlite_session_factory) -> None:
    seed = seed_trends_jobs(sqlite_session_factory)

    overview_response = api_client.get(f"/crawl-jobs/{seed['target_job_id']}/trends/overview")
    assert overview_response.status_code == 200
    overview_payload = overview_response.json()
    assert overview_payload["default_baseline_job_id"] == seed["baseline_job_id"]
    assert overview_payload["baseline_candidates"][0]["id"] == seed["baseline_job_id"]

    crawl_response = api_client.get(
        f"/crawl-jobs/{seed['target_job_id']}/trends/crawl",
        params={
            "baseline_job_id": seed["baseline_job_id"],
            "change_type": "improved",
            "sort_by": "delta_priority_score",
            "sort_order": "desc",
        },
    )
    assert crawl_response.status_code == 200
    crawl_payload = crawl_response.json()
    assert crawl_payload["items"][0]["url"] == "https://example.com/improved"
    assert all(item["change_type"] == "improved" for item in crawl_payload["items"])

    invalid_response = api_client.get(
        f"/crawl-jobs/{seed['target_job_id']}/trends/crawl",
        params={"baseline_job_id": seed["foreign_job_id"]},
    )
    assert invalid_response.status_code == 400
    assert "same site" in invalid_response.json()["detail"]

    gsc_response = api_client.get(
        f"/crawl-jobs/{seed['target_job_id']}/trends/gsc",
        params={"trend": "worsened", "sort_by": "delta_clicks", "sort_order": "asc"},
    )
    assert gsc_response.status_code == 200
    gsc_payload = gsc_response.json()
    assert {item["overall_trend"] for item in gsc_payload["items"]} == {"worsened"}
    assert gsc_payload["items"][0]["delta_clicks"] <= 0

    crawl_export = api_client.get(
        f"/crawl-jobs/{seed['target_job_id']}/export/crawl-compare.csv",
        params={"baseline_job_id": seed["baseline_job_id"], "change_type": "worsened"},
    )
    assert crawl_export.status_code == 200
    assert "change_type" in crawl_export.text
    assert "https://example.com/worsened" in crawl_export.text
    assert "https://example.com/improved" not in crawl_export.text

    gsc_export = api_client.get(
        f"/crawl-jobs/{seed['target_job_id']}/export/gsc-compare.csv",
        params={"trend": "improved"},
    )
    assert gsc_export.status_code == 200
    assert "overall_trend" in gsc_export.text
    assert "https://example.com/improved" in gsc_export.text


def test_trends_export_service_reuses_compare_filters(sqlite_session_factory) -> None:
    seed = seed_trends_jobs(sqlite_session_factory)

    with sqlite_session_factory() as session:
        crawl_csv = export_service.build_crawl_compare_csv(
            session,
            seed["target_job_id"],
            baseline_job_id=seed["baseline_job_id"],
            change_type="new",
        )
        gsc_csv = export_service.build_gsc_compare_csv(
            session,
            seed["target_job_id"],
            trend="flat",
        )

    crawl_plain = crawl_csv.lstrip("\ufeff")
    gsc_plain = gsc_csv.lstrip("\ufeff")

    assert crawl_plain.startswith("url,normalized_url,change_type,change_rationale")
    assert "https://example.com/new" in crawl_plain
    assert "https://example.com/improved" not in crawl_plain

    assert gsc_plain.startswith("page_id,url,normalized_url,has_baseline_data,has_target_data")
    assert "https://example.com/stable" in gsc_plain
    assert "https://example.com/worsened" not in gsc_plain
