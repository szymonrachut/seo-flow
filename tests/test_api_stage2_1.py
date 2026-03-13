from __future__ import annotations

from app.db.models import CrawlJob, CrawlJobStatus, Link, Page, Site


def seed_stage21_job(session_factory, *, status: CrawlJobStatus = CrawlJobStatus.RUNNING) -> int:
    with session_factory() as session:
        site = Site(root_url="https://example.com/", domain="example.com")
        session.add(site)
        session.flush()

        crawl_job = CrawlJob(
            site_id=site.id,
            status=status,
            settings_json={"start_url": "https://example.com/", "max_urls": 100},
            stats_json={},
        )
        session.add(crawl_job)
        session.flush()

        pages = {
            "a": Page(
                crawl_job_id=crawl_job.id,
                url="https://example.com/a",
                normalized_url="https://example.com/a",
                final_url="https://example.com/a",
                status_code=200,
                title="Alpha",
                meta_description="Meta A",
                h1="H1 A",
                canonical_url="https://example.com/a",
                robots_meta="index,follow",
                content_type="text/html",
                response_time_ms=50,
                is_internal=True,
                depth=1,
                fetched_at=None,
                error_message=None,
            ),
            "b": Page(
                crawl_job_id=crawl_job.id,
                url="https://example.com/b",
                normalized_url="https://example.com/b",
                final_url="https://example.com/b",
                status_code=404,
                title=None,
                meta_description="Meta B",
                h1="H1 B",
                canonical_url=None,
                robots_meta=None,
                content_type="text/html",
                response_time_ms=20,
                is_internal=True,
                depth=2,
                fetched_at=None,
                error_message="HTTP 404",
            ),
            "c": Page(
                crawl_job_id=crawl_job.id,
                url="https://example.com/c",
                normalized_url="https://example.com/c",
                final_url="https://example.com/c",
                status_code=200,
                title="Charlie",
                meta_description=None,
                h1=None,
                canonical_url=None,
                robots_meta="noindex,follow",
                content_type="text/html",
                response_time_ms=30,
                is_internal=True,
                depth=3,
                fetched_at=None,
                error_message=None,
            ),
            "d": Page(
                crawl_job_id=crawl_job.id,
                url="https://example.com/d",
                normalized_url="https://example.com/d",
                final_url="https://example.com/final",
                status_code=301,
                title="Delta",
                meta_description="Meta D",
                h1="H1 D",
                canonical_url="https://example.com/d",
                robots_meta=None,
                content_type="text/html",
                response_time_ms=10,
                is_internal=True,
                depth=2,
                fetched_at=None,
                error_message=None,
            ),
            "e": Page(
                crawl_job_id=crawl_job.id,
                url="https://example.com/e",
                normalized_url="https://example.com/e",
                final_url="https://example.com/e",
                status_code=200,
                title="Echo",
                meta_description="Meta E",
                h1="H1 E",
                canonical_url="https://example.com/e",
                robots_meta=None,
                content_type="text/html",
                response_time_ms=40,
                is_internal=True,
                depth=1,
                fetched_at=None,
                error_message=None,
            ),
        }
        session.add_all(list(pages.values()))
        session.flush()

        session.add_all(
            [
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=pages["a"].id,
                    source_url=pages["a"].url,
                    target_url=pages["b"].url,
                    target_normalized_url=pages["b"].normalized_url,
                    target_domain="example.com",
                    anchor_text="Broken target",
                    rel_attr="",
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=pages["a"].id,
                    source_url=pages["a"].url,
                    target_url="https://external.test/out",
                    target_normalized_url="https://external.test/out",
                    target_domain="external.test",
                    anchor_text="External",
                    rel_attr="nofollow",
                    is_nofollow=True,
                    is_internal=False,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=pages["c"].id,
                    source_url=pages["c"].url,
                    target_url=pages["d"].url,
                    target_normalized_url=pages["d"].normalized_url,
                    target_domain="example.com",
                    anchor_text="",
                    rel_attr="nofollow",
                    is_nofollow=True,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=pages["d"].id,
                    source_url=pages["d"].url,
                    target_url="https://example.com/missing",
                    target_normalized_url="https://example.com/missing",
                    target_domain="example.com",
                    anchor_text=None,
                    rel_attr="",
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=pages["e"].id,
                    source_url=pages["e"].url,
                    target_url=pages["c"].url,
                    target_normalized_url=pages["c"].normalized_url,
                    target_domain="example.com",
                    anchor_text="To C",
                    rel_attr="",
                    is_nofollow=False,
                    is_internal=True,
                ),
            ]
        )
        session.commit()
        return crawl_job.id


def test_pages_pagination(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={"page": 2, "page_size": 2, "sort_by": "url"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["page_size"] == 2
    assert payload["total_items"] == 5
    assert payload["total_pages"] == 3
    assert [item["url"] for item in payload["items"]] == ["https://example.com/c", "https://example.com/d"]


def test_links_pagination(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/links",
        params={"page": 1, "page_size": 2, "sort_by": "source_url", "sort_order": "asc"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 5
    assert payload["total_pages"] == 3
    assert len(payload["items"]) == 2


def test_pages_sorting(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/pages",
        params={"sort_by": "response_time_ms", "sort_order": "desc", "page_size": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert [item["response_time_ms"] for item in payload["items"]] == [50, 40, 30, 20, 10]


def test_links_sorting(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/links",
        params={"sort_by": "target_url", "sort_order": "desc", "page_size": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["target_url"] == "https://external.test/out"


def test_pages_filter_has_title(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={"has_title": "false"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["normalized_url"] == "https://example.com/b"


def test_pages_filter_has_meta_description(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={"has_meta_description": "false"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["normalized_url"] == "https://example.com/c"


def test_pages_filter_has_h1(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={"has_h1": "false"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["normalized_url"] == "https://example.com/c"


def test_pages_filter_canonical_missing(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={"canonical_missing": "true", "page_size": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 2
    assert {item["normalized_url"] for item in payload["items"]} == {
        "https://example.com/b",
        "https://example.com/c",
    }


def test_pages_filter_robots_meta_contains(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={"robots_meta_contains": "noindex"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["normalized_url"] == "https://example.com/c"


def test_pages_filter_non_indexable_like(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={"non_indexable_like": "true", "page_size": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 3


def test_links_filters(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/links",
        params={
            "is_internal": "false",
            "is_nofollow": "true",
            "has_anchor": "true",
            "target_domain": "external.test",
            "page_size": 10,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["target_url"] == "https://external.test/out"


def test_job_detail_summary_counts_and_progress(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory, status=CrawlJobStatus.RUNNING)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["summary_counts"] == {
        "total_pages": 5,
        "total_links": 5,
        "total_internal_links": 4,
        "total_external_links": 1,
        "pages_missing_title": 1,
        "pages_missing_meta_description": 1,
        "pages_missing_h1": 1,
        "pages_non_indexable_like": 3,
        "broken_internal_links": 1,
        "redirecting_internal_links": 1,
    }
    assert payload["progress"] == {
        "visited_pages": 5,
        "queued_urls": 1,
        "discovered_links": 5,
        "internal_links": 4,
        "external_links": 1,
        "errors_count": 1,
    }


def test_stop_endpoint_sets_stopped_status(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory, status=CrawlJobStatus.RUNNING)
    response = api_client.post(f"/crawl-jobs/{crawl_job_id}/stop")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "stopped"
    assert payload["finished_at"] is not None
    assert payload["progress"]["queued_urls"] == 0


def test_pages_query_validation_errors(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory, status=CrawlJobStatus.FINISHED)

    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={"page": 0})
    assert response.status_code == 422

    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={"sort_by": "not-allowed"})
    assert response.status_code == 422

    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/pages",
        params={"status_code_min": 500, "status_code_max": 200},
    )
    assert response.status_code == 400
