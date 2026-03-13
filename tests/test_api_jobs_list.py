from __future__ import annotations

from app.db.models import CrawlJob, CrawlJobStatus, Site


def test_list_crawl_jobs_returns_sorted_rows(api_client, sqlite_session_factory) -> None:
    with sqlite_session_factory() as session:
        site = Site(root_url="https://example.com/", domain="example.com")
        session.add(site)
        session.flush()

        first_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            settings_json={"start_url": "https://example.com/"},
            stats_json={},
        )
        second_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.RUNNING,
            settings_json={"start_url": "https://example.com/blog"},
            stats_json={},
        )
        session.add_all([first_job, second_job])
        session.commit()

    response = api_client.get("/crawl-jobs", params={"sort_by": "id", "sort_order": "desc"})
    assert response.status_code == 200

    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["id"] > payload[1]["id"]
    assert payload[0]["root_url"] == "https://example.com/blog"
    assert payload[0]["status"] == "running"
    assert payload[0]["total_pages"] == 0
    assert payload[0]["total_internal_links"] == 0


def test_cors_preflight_allows_local_frontend(api_client) -> None:
    response = api_client.options(
        "/crawl-jobs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
