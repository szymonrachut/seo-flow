from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import CrawlJob, CrawlJobStatus, Site
from app.services import crawl_job_service


def test_create_crawl_jobs_reuse_same_site(api_client, sqlite_session_factory, monkeypatch) -> None:
    calls: list[int] = []

    def fake_run_crawl_job_subprocess(
        crawl_job_id: int,
        *,
        root_url: str,
        max_urls: int,
        max_depth: int,
        delay: float,
        render_mode: str,
        render_timeout_ms: int,
        max_rendered_pages_per_job: int,
    ) -> None:
        calls.append(crawl_job_id)

    monkeypatch.setattr(crawl_job_service, "run_crawl_job_subprocess", fake_run_crawl_job_subprocess)

    first_response = api_client.post(
        "/crawl-jobs",
        json={
            "root_url": "https://example.com",
            "max_urls": 20,
            "max_depth": 2,
            "delay": 0.0,
        },
    )
    second_response = api_client.post(
        "/crawl-jobs",
        json={
            "root_url": "https://example.com/blog",
            "max_urls": 20,
            "max_depth": 2,
            "delay": 0.0,
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    first_payload = first_response.json()
    second_payload = second_response.json()
    assert first_payload["site_id"] == second_payload["site_id"]
    assert calls == [first_payload["id"], second_payload["id"]]

    with sqlite_session_factory() as session:
        sites = session.scalars(select(Site)).all()
        assert len(sites) == 1
        crawl_jobs = session.scalars(select(CrawlJob).where(CrawlJob.site_id == first_payload["site_id"])).all()
        assert len(crawl_jobs) == 2


def test_site_detail_resolves_active_and_baseline_context(api_client, sqlite_session_factory) -> None:
    base_time = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)

    with sqlite_session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com")
        session.add(site)
        session.flush()

        crawl_jobs = [
            CrawlJob(
                site_id=site.id,
                status=CrawlJobStatus.FINISHED,
                created_at=base_time + timedelta(minutes=offset),
                settings_json={"start_url": f"https://example.com/run-{offset}"},
                stats_json={},
            )
            for offset in (0, 10, 20)
        ]
        session.add_all(crawl_jobs)
        session.commit()
        site_id = site.id
        oldest_job_id = crawl_jobs[0].id
        newest_job_id = crawl_jobs[-1].id
        previous_job_id = crawl_jobs[-2].id

    response = api_client.get(f"/sites/{site_id}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["id"] == site_id
    assert payload["active_crawl_id"] == newest_job_id
    assert payload["baseline_crawl_id"] == previous_job_id
    assert payload["active_crawl"]["id"] == newest_job_id
    assert payload["baseline_crawl"]["id"] == previous_job_id
    assert [item["id"] for item in payload["crawl_history"]] == [newest_job_id, previous_job_id, oldest_job_id]
    assert payload["summary"]["total_crawls"] == 3


def test_site_routes_list_crawls_and_create_new_crawl(api_client, sqlite_session_factory, monkeypatch) -> None:
    calls: list[int] = []

    def fake_run_crawl_job_subprocess(
        crawl_job_id: int,
        *,
        root_url: str,
        max_urls: int,
        max_depth: int,
        delay: float,
        render_mode: str,
        render_timeout_ms: int,
        max_rendered_pages_per_job: int,
    ) -> None:
        calls.append(crawl_job_id)

    monkeypatch.setattr(crawl_job_service, "run_crawl_job_subprocess", fake_run_crawl_job_subprocess)

    with sqlite_session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com")
        session.add(site)
        session.flush()
        crawl_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            settings_json={"start_url": "https://example.com"},
            stats_json={},
        )
        session.add(crawl_job)
        session.commit()
        site_id = site.id

    list_response = api_client.get(f"/sites/{site_id}/crawls")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload) == 1
    assert list_payload[0]["site_id"] == site_id

    create_response = api_client.post(
        f"/sites/{site_id}/crawls",
        json={
            "root_url": "https://example.com/docs",
            "max_urls": 30,
            "max_depth": 3,
            "delay": 0.0,
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["site_id"] == site_id
    assert calls == [create_payload["id"]]

    refreshed_list = api_client.get(f"/sites/{site_id}/crawls")
    assert refreshed_list.status_code == 200
    refreshed_payload = refreshed_list.json()
    assert len(refreshed_payload) == 2
    assert refreshed_payload[0]["id"] == create_payload["id"]


def test_list_sites_returns_latest_crawl_summary(api_client, sqlite_session_factory) -> None:
    with sqlite_session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com")
        session.add(site)
        session.flush()
        session.add(
            CrawlJob(
                site_id=site.id,
                status=CrawlJobStatus.RUNNING,
                settings_json={"start_url": "https://example.com"},
                stats_json={},
            )
        )
        session.commit()

    response = api_client.get("/sites")
    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["domain"] == "example.com"
    assert payload[0]["summary"]["total_crawls"] == 1
    assert payload[0]["latest_crawl"]["status"] == "running"
