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


def test_pages_sorting_by_meta_description(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/pages",
        params={"sort_by": "meta_description", "sort_order": "desc", "page_size": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert [item["normalized_url"] for item in payload["items"][:2]] == [
        "https://example.com/e",
        "https://example.com/d",
    ]


def test_pages_sorting_by_h1_length(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    with sqlite_session_factory() as session:
        page = session.query(Page).filter(Page.crawl_job_id == crawl_job_id, Page.normalized_url == "https://example.com/e").one()
        page.h1 = "Echo heading extended"
        session.commit()

    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/pages",
        params={"sort_by": "h1_length", "sort_order": "desc", "page_size": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["normalized_url"] == "https://example.com/e"
    assert payload["items"][0]["h1_length"] == len("Echo heading extended")


def test_pages_filter_title_contains_status_code_and_response_metadata(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/pages",
        params={"title_contains": "ha", "status_code": 200, "page_size": 10},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 2
    assert {item["normalized_url"] for item in payload["items"]} == {
        "https://example.com/a",
        "https://example.com/c",
    }
    assert payload["available_status_codes"] == [200, 301, 404]
    assert payload["has_gsc_integration"] is False


def test_links_sorting_by_anchor_text(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/links",
        params={"sort_by": "anchor_text", "sort_order": "desc", "page_size": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["anchor_text"] == "To C"


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


def test_pages_filter_title_exact(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={"title_exact": "Alpha"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["normalized_url"] == "https://example.com/a"


def test_pages_filter_meta_description_exact(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={"meta_description_exact": "Meta D"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["normalized_url"] == "https://example.com/d"


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


def test_links_filter_broken_internal(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/links", params={"broken_internal": "true", "page_size": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["target_url"] == "https://example.com/b"


def test_links_filter_redirecting_internal(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/links",
        params={"redirecting_internal": "true", "page_size": 10},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["target_url"] == "https://example.com/d"
    assert payload["items"][0]["final_url"] == "https://example.com/final"


def test_links_filter_unresolved_internal(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/links",
        params={"unresolved_internal": "true", "page_size": 10},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["target_url"] == "https://example.com/missing"


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
        "rendered_pages": 0,
        "js_heavy_like_pages": 0,
        "pages_with_render_errors": 0,
        "pages_with_schema": 0,
        "pages_with_x_robots_tag": 0,
        "broken_internal_links": 1,
        "redirecting_internal_links": 1,
        "pages_with_gsc_28d": 0,
        "pages_with_gsc_90d": 0,
        "gsc_opportunities_28d": 0,
        "gsc_opportunities_90d": 0,
    }
    assert payload["progress"] == {
        "visited_pages": 5,
        "queued_urls": 1,
        "discovered_links": 5,
        "internal_links": 4,
        "external_links": 1,
        "errors_count": 1,
    }


def test_jobs_list_sorting_by_total_errors(api_client, sqlite_session_factory) -> None:
    first_job_id = seed_stage21_job(sqlite_session_factory, status=CrawlJobStatus.RUNNING)

    with sqlite_session_factory() as session:
        first_job = session.get(CrawlJob, first_job_id)
        assert first_job is not None

        second_job = CrawlJob(
            site_id=first_job.site_id,
            status=CrawlJobStatus.FINISHED,
            settings_json={"start_url": "https://example.com/second", "max_urls": 100},
            stats_json={},
        )
        session.add(second_job)
        session.flush()

        second_error_page = Page(
            crawl_job_id=second_job.id,
            url="https://example.com/error",
            normalized_url="https://example.com/error",
            final_url="https://example.com/error",
            status_code=500,
            title="Error page",
            meta_description="Server error",
            h1="Error",
            canonical_url=None,
            robots_meta=None,
            content_type="text/html",
            response_time_ms=70,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message="HTTP 500",
        )
        session.add(second_error_page)
        session.commit()

    response = api_client.get("/crawl-jobs", params={"sort_by": "total_errors", "sort_order": "desc"})
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == second_job.id
    assert payload[0]["total_errors"] >= payload[1]["total_errors"]


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


def test_filtered_pages_export_uses_current_filters(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/export/pages.csv",
        params={"has_title": "false", "sort_by": "title", "sort_order": "asc"},
    )
    assert response.status_code == 200
    assert "crawl_job_" in response.headers["content-disposition"]
    assert "_pages_view.csv" in response.headers["content-disposition"]
    body = response.text
    assert "https://example.com/b" in body
    assert "https://example.com/a" not in body


def test_filtered_links_export_uses_current_filters(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage21_job(sqlite_session_factory)
    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/export/links.csv",
        params={"broken_internal": "true"},
    )
    assert response.status_code == 200
    assert "_links_view.csv" in response.headers["content-disposition"]
    body = response.text
    assert "https://example.com/b" in body
    assert "https://external.test/out" not in body


def seed_stage4_filters_job(session_factory) -> int:
    def make_page(crawl_job_id: int, path: str, **overrides) -> Page:
        url = f"https://example.com{path}"
        title = f"Stable title for {path} coverage page"
        meta_description = "This meta description is intentionally long enough for the stage 4 API filter tests."
        payload = {
            "crawl_job_id": crawl_job_id,
            "url": url,
            "normalized_url": url,
            "final_url": url,
            "status_code": 200,
            "title": title,
            "title_length": len(title),
            "meta_description": meta_description,
            "meta_description_length": len(meta_description),
            "h1": f"H1 {path}",
            "h1_count": 1,
            "h2_count": 1,
            "canonical_url": url,
            "robots_meta": "index,follow",
            "content_type": "text/html",
            "word_count": 220,
            "content_text_hash": f"hash-{path.strip('/')}",
            "images_count": 2,
            "images_missing_alt_count": 0,
            "html_size_bytes": 24000,
            "response_time_ms": 25,
            "is_internal": True,
            "depth": 1,
            "fetched_at": None,
            "error_message": None,
        }
        payload.update(overrides)
        return Page(**payload)

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

        pages = {
            "home": make_page(crawl_job.id, "/"),
            "title_short": make_page(crawl_job.id, "/title-short", title="Short title", title_length=11, word_count=90, images_missing_alt_count=1, html_size_bytes=620000),
            "title_long": make_page(
                crawl_job.id,
                "/title-long",
                title="This is a very long title that exceeds sixty characters in the stage four API filter tests",
                title_length=88,
                meta_description="Short meta",
                meta_description_length=10,
                h1_count=2,
                h2_count=0,
                canonical_url="https://example.com/canonical-missing",
                content_text_hash="hash-dup-content",
            ),
            "noindex": make_page(
                crawl_job.id,
                "/noindex",
                meta_description=None,
                meta_description_length=None,
                h1=None,
                h1_count=0,
                h2_count=2,
                canonical_url=None,
                robots_meta="noindex,follow",
                word_count=80,
                images_count=0,
                content_text_hash="hash-noindex",
            ),
            "canonicalized": make_page(
                crawl_job.id,
                "/canonicalized",
                title="Shared title",
                title_length=12,
                canonical_url="https://example.com/redirect-source",
                images_missing_alt_count=1,
                content_text_hash="hash-dup-content",
            ),
            "canonicalized_b": make_page(
                crawl_job.id,
                "/canonicalized-b",
                title="Shared title",
                title_length=12,
                canonical_url="https://example.com/broken-target",
                images_count=0,
                content_text_hash="hash-canonicalized-b",
            ),
            "redirect_source": make_page(
                crawl_job.id,
                "/redirect-source",
                final_url="https://example.com/redirect-final",
                canonical_url="https://example.com/redirect-final",
                content_text_hash="hash-redirect-source",
            ),
            "redirect_final": make_page(
                crawl_job.id,
                "/redirect-final",
                title="Redirect final page title that is long enough",
                title_length=43,
                content_text_hash="hash-redirect-final",
            ),
            "broken_target": make_page(
                crawl_job.id,
                "/broken-target",
                status_code=404,
                error_message="HTTP 404",
                content_text_hash="hash-broken-target",
            ),
            "chain_start": make_page(
                crawl_job.id,
                "/chain-start",
                final_url="https://example.com/chain-mid",
                canonical_url="https://example.com/chain-mid",
                content_text_hash="hash-chain-start",
            ),
            "chain_mid": make_page(
                crawl_job.id,
                "/chain-mid",
                final_url="https://example.com/chain-final",
                canonical_url="https://example.com/chain-final",
                content_text_hash="hash-chain-mid",
            ),
            "chain_final": make_page(
                crawl_job.id,
                "/chain-final",
                canonical_url="https://example.com/chain-final",
                content_text_hash="hash-chain-final",
            ),
        }
        session.add_all(list(pages.values()))
        session.flush()

        session.add_all(
            [
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=pages["home"].id,
                    source_url=pages["home"].url,
                    target_url=pages["noindex"].url,
                    target_normalized_url=pages["noindex"].normalized_url,
                    target_domain="example.com",
                    anchor_text="Noindex target",
                    rel_attr="",
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=pages["home"].id,
                    source_url=pages["home"].url,
                    target_url=pages["canonicalized"].url,
                    target_normalized_url=pages["canonicalized"].normalized_url,
                    target_domain="example.com",
                    anchor_text="Canonicalized target",
                    rel_attr="",
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=pages["home"].id,
                    source_url=pages["home"].url,
                    target_url=pages["redirect_source"].url,
                    target_normalized_url=pages["redirect_source"].normalized_url,
                    target_domain="example.com",
                    anchor_text="Redirect target",
                    rel_attr="",
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job.id,
                    source_page_id=pages["home"].id,
                    source_url=pages["home"].url,
                    target_url=pages["chain_start"].url,
                    target_normalized_url=pages["chain_start"].normalized_url,
                    target_domain="example.com",
                    anchor_text="Chain target",
                    rel_attr="",
                    is_nofollow=False,
                    is_internal=True,
                ),
            ]
        )
        session.commit()
        return crawl_job.id


def test_stage4_pages_filters(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage4_filters_job(sqlite_session_factory)

    checks = [
        ({"title_too_short": "true"}, "https://example.com/title-short"),
        ({"title_too_long": "true"}, "https://example.com/title-long"),
        ({"meta_too_short": "true"}, "https://example.com/title-long"),
        ({"multiple_h1": "true"}, "https://example.com/title-long"),
        ({"missing_h2": "true"}, "https://example.com/title-long"),
        ({"canonical_to_other_url": "true"}, "https://example.com/title-long"),
        ({"canonical_to_non_200": "true"}, "https://example.com/title-long"),
        ({"canonical_to_redirect": "true"}, "https://example.com/canonicalized"),
        ({"noindex_like": "true"}, "https://example.com/noindex"),
        ({"non_indexable_like": "true"}, "https://example.com/noindex"),
        ({"thin_content": "true"}, "https://example.com/noindex"),
        ({"duplicate_content": "true"}, "https://example.com/canonicalized"),
        ({"missing_alt_images": "true"}, "https://example.com/title-short"),
        ({"oversized": "true"}, "https://example.com/title-short"),
    ]

    for params, expected_url in checks:
        response = api_client.get(f"/crawl-jobs/{crawl_job_id}/pages", params={**params, "page_size": 20})
        assert response.status_code == 200
        payload = response.json()
        assert expected_url in {item["normalized_url"] for item in payload["items"]}


def test_stage4_links_filters(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage4_filters_job(sqlite_session_factory)

    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/links", params={"to_noindex_like": "true", "page_size": 20})
    assert response.status_code == 200
    assert response.json()["items"][0]["target_url"] == "https://example.com/noindex"

    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/links", params={"to_canonicalized": "true", "page_size": 20})
    assert response.status_code == 200
    assert response.json()["items"][0]["target_url"] == "https://example.com/canonicalized"

    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/links", params={"redirect_chain": "true", "page_size": 20})
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["target_url"] == "https://example.com/chain-start"
    assert payload["items"][0]["redirect_hops"] == 2


def test_stage4_filtered_exports_use_new_filters(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_stage4_filters_job(sqlite_session_factory)

    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/export/pages.csv",
        params={"duplicate_content": "true", "sort_by": "word_count", "sort_order": "asc"},
    )
    assert response.status_code == 200
    assert "_pages_view.csv" in response.headers["content-disposition"]
    assert "https://example.com/canonicalized" in response.text
    assert "https://example.com/noindex" not in response.text

    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/export/links.csv",
        params={"redirect_chain": "true"},
    )
    assert response.status_code == 200
    assert "_links_view.csv" in response.headers["content-disposition"]
    assert "https://example.com/chain-start" in response.text
