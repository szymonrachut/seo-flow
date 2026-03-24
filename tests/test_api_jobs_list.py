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


def test_cors_preflight_allows_vite_fallback_port(api_client) -> None:
    response = api_client.options(
        "/crawl-jobs",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5174"


def test_list_crawl_jobs_filters_by_status(api_client, sqlite_session_factory) -> None:
    with sqlite_session_factory() as session:
        site = Site(root_url="https://example.com/", domain="example.com")
        session.add(site)
        session.flush()

        session.add_all(
            [
                CrawlJob(
                    site_id=site.id,
                    status=CrawlJobStatus.FINISHED,
                    settings_json={"start_url": "https://example.com/"},
                    stats_json={},
                ),
                CrawlJob(
                    site_id=site.id,
                    status=CrawlJobStatus.RUNNING,
                    settings_json={"start_url": "https://example.com/blog"},
                    stats_json={},
                ),
            ]
        )
        session.commit()

    response = api_client.get("/crawl-jobs", params={"status_filter": "running"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["status"] == "running"


def test_list_crawl_jobs_searches_by_root_url(api_client, sqlite_session_factory) -> None:
    with sqlite_session_factory() as session:
        site = Site(root_url="https://example.com/", domain="example.com")
        session.add(site)
        session.flush()

        session.add_all(
            [
                CrawlJob(
                    site_id=site.id,
                    status=CrawlJobStatus.FINISHED,
                    settings_json={"start_url": "https://example.com/"},
                    stats_json={},
                ),
                CrawlJob(
                    site_id=site.id,
                    status=CrawlJobStatus.RUNNING,
                    settings_json={"start_url": "https://example.com/blog"},
                    stats_json={},
                ),
            ]
        )
        session.commit()

    response = api_client.get("/crawl-jobs", params={"search": "blog"})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["root_url"] == "https://example.com/blog"
