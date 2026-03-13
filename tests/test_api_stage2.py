from __future__ import annotations

from app.db.models import CrawlJob, CrawlJobStatus, Link, Page, Site
from app.services import crawl_job_service


def seed_api_job(SessionLocal) -> int:
    with SessionLocal() as session:
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

        home = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/",
            normalized_url="https://example.com/",
            final_url="https://example.com/",
            status_code=200,
            title="Home",
            meta_description="Home desc",
            h1="Home H1",
            canonical_url="https://example.com/",
            robots_meta=None,
            content_type="text/html",
            response_time_ms=10,
            is_internal=True,
            depth=0,
            fetched_at=None,
            error_message=None,
        )
        missing_title = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/missing-title",
            normalized_url="https://example.com/missing-title",
            final_url="https://example.com/missing-title",
            status_code=200,
            title=None,
            meta_description="Meta",
            h1="H1",
            canonical_url=None,
            robots_meta="noindex,follow",
            content_type="text/html",
            response_time_ms=20,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        )
        broken = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/broken",
            normalized_url="https://example.com/broken",
            final_url="https://example.com/broken",
            status_code=404,
            title="Broken",
            meta_description="Broken",
            h1="Broken",
            canonical_url=None,
            robots_meta=None,
            content_type="text/html",
            response_time_ms=40,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message="HTTP 404",
        )
        session.add_all([home, missing_title, broken])
        session.flush()

        link = Link(
            crawl_job_id=crawl_job.id,
            source_page_id=home.id,
            source_url=home.url,
            target_url=broken.url,
            target_normalized_url=broken.normalized_url,
            target_domain="example.com",
            anchor_text="Broken target",
            rel_attr="",
            is_nofollow=False,
            is_internal=True,
        )
        session.add(link)
        session.commit()
        return crawl_job.id


def test_get_audit_endpoint(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_api_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/audit")
    assert response.status_code == 200

    payload = response.json()
    assert payload["crawl_job_id"] == crawl_job_id
    assert payload["summary"]["pages_missing_title"] == 1
    assert payload["summary"]["broken_internal_links"] == 1


def test_get_pages_endpoint_with_missing_title_filter(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_api_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={"missing_title": "true"})
    assert response.status_code == 200

    payload = response.json()
    assert payload["total_items"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["normalized_url"] == "https://example.com/missing-title"


def test_get_links_endpoint_with_is_internal_filter(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_api_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/links", params={"is_internal": "true"})
    assert response.status_code == 200

    payload = response.json()
    assert payload["total_items"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["is_internal"] is True
    assert payload["items"][0]["target_url"] == "https://example.com/broken"


def test_export_csv_endpoint(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_api_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/export/pages.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "canonical_url" in response.text
    assert "https://example.com/missing-title" in response.text


def test_export_audit_csv_endpoint(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_api_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/export/audit.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "issue_type,key,value,url,details" in response.text
    assert "summary,total_pages,3,," in response.text


def test_post_crawl_job_endpoint_smoke(api_client, sqlite_session_factory, monkeypatch) -> None:
    calls: list[int] = []

    def fake_run_crawl_job_subprocess(
        crawl_job_id: int,
        *,
        root_url: str,
        max_urls: int,
        max_depth: int,
        delay: float,
    ) -> None:
        calls.append(crawl_job_id)

    monkeypatch.setattr(crawl_job_service, "run_crawl_job_subprocess", fake_run_crawl_job_subprocess)

    response = api_client.post(
        "/crawl-jobs",
        json={
            "root_url": "https://example.com",
            "max_urls": 20,
            "max_depth": 3,
            "delay": 0.0,
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["id"] > 0
    assert payload["status"] == "pending"
    assert calls == [payload["id"]]
