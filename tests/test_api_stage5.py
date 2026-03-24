from __future__ import annotations

from app.db.models import CrawlJob, CrawlJobStatus, Page, Site


def seed_stage5_job(session_factory) -> int:
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

        def make_page(path: str, **overrides) -> Page:
            url = f"https://example.com{path}"
            payload = {
                "crawl_job_id": crawl_job.id,
                "url": url,
                "normalized_url": url,
                "final_url": url,
                "status_code": 200,
                "title": f"Title for {path}",
                "title_length": 20,
                "meta_description": f"Meta description for {path}",
                "meta_description_length": 30,
                "h1": f"H1 {path}",
                "h1_count": 1,
                "h2_count": 1,
                "canonical_url": url,
                "robots_meta": "index,follow",
                "x_robots_tag": None,
                "content_type": "text/html; charset=utf-8",
                "word_count": 220,
                "content_text_hash": f"hash-{path.strip('/') or 'home'}",
                "images_count": 2,
                "images_missing_alt_count": 0,
                "html_size_bytes": 32000,
                "was_rendered": False,
                "render_attempted": False,
                "fetch_mode_used": "http",
                "js_heavy_like": False,
                "render_reason": None,
                "render_error_message": None,
                "schema_present": False,
                "schema_count": 0,
                "schema_types_json": None,
                "response_time_ms": 25,
                "is_internal": True,
                "depth": 1,
                "fetched_at": None,
                "error_message": None,
            }
            payload.update(overrides)
            return Page(**payload)

        session.add_all(
            [
                make_page(
                    "/rendered",
                    was_rendered=True,
                    render_attempted=True,
                    fetch_mode_used="playwright",
                    js_heavy_like=True,
                    render_reason="shell_html_missing_core(chars=120,missing_core=3,scripts=6)",
                    x_robots_tag="noindex",
                    schema_present=True,
                    schema_count=2,
                    schema_types_json=["Article", "BreadcrumbList"],
                ),
                make_page(
                    "/render-error",
                    render_attempted=True,
                    js_heavy_like=True,
                    render_reason="low_text_many_scripts(words=1,scripts=6,links=0)",
                    render_error_message="Navigation timeout",
                ),
                make_page(
                    "/product",
                    schema_present=True,
                    schema_count=1,
                    schema_types_json=["Product"],
                ),
                make_page(
                    "/x-robots",
                    x_robots_tag="nofollow",
                ),
                make_page("/plain"),
            ]
        )
        session.commit()
        return crawl_job.id


def test_pages_filters_cover_stage5_signals(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage5_job(sqlite_session_factory)

    checks = [
        ({"was_rendered": "true"}, "https://example.com/rendered"),
        ({"js_heavy_like": "true"}, "https://example.com/render-error"),
        ({"schema_present": "true"}, "https://example.com/product"),
        ({"schema_type": "Product"}, "https://example.com/product"),
        ({"has_render_error": "true"}, "https://example.com/render-error"),
        ({"has_x_robots_tag": "true"}, "https://example.com/x-robots"),
    ]

    for params, expected_url in checks:
        response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={**params, "page_size": 20})
        assert response.status_code == 200
        urls = {item["normalized_url"] for item in response.json()["items"]}
        assert expected_url in urls


def test_audit_endpoint_exposes_render_and_schema_sections(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage5_job(sqlite_session_factory)

    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/audit")
    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"]["rendered_pages"] == 1
    assert payload["summary"]["js_heavy_like_pages"] == 2
    assert payload["summary"]["pages_with_render_errors"] == 1
    assert payload["summary"]["pages_with_schema"] == 2
    assert payload["summary"]["pages_missing_schema"] == 3
    assert payload["summary"]["pages_with_x_robots_tag"] == 2
    assert payload["summary"]["pages_with_schema_types_summary"] == 3
    assert payload["rendered_pages"][0]["normalized_url"] == "https://example.com/rendered"
    assert payload["pages_with_render_errors"][0]["render_error_message"] == "Navigation timeout"
    assert payload["pages_with_schema_types_summary"][0]["value"] in {"Article", "BreadcrumbList", "Product"}


def test_stage5_pages_export_contains_render_and_schema_columns(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage5_job(sqlite_session_factory)

    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/export/pages.csv",
        params={"was_rendered": "true", "sort_by": "schema_count", "sort_order": "desc"},
    )
    assert response.status_code == 200
    assert "_pages_view.csv" in response.headers["content-disposition"]
    assert "was_rendered" in response.text
    assert "render_error_message" in response.text
    assert "schema_types" in response.text
    assert "https://example.com/rendered" in response.text
    assert "https://example.com/plain" not in response.text
