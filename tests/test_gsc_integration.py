from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api.routes import gsc as gsc_routes
from app.integrations.gsc import auth as gsc_auth
from app.db.models import CrawlJob, CrawlJobStatus, GscProperty, Page, Site
from app.integrations.gsc.auth import GscAuthError
from app.integrations.gsc.client import GscApiError
from app.services import gsc_service


class FakeSearchConsoleApiClient:
    def list_sites(self) -> list[dict[str, str]]:
        return [
            {
                "siteUrl": "sc-domain:example.com",
                "permissionLevel": "siteOwner",
            }
        ]

    def query_search_analytics(self, property_uri: str, request: dict[str, object]) -> list[dict[str, object]]:
        dimensions = request.get("dimensions")
        if dimensions == ["page"]:
            return [
                {
                    "keys": ["https://example.com/a"],
                    "clicks": 12,
                    "impressions": 340,
                    "ctr": 0.0353,
                    "position": 8.4,
                },
                {
                    "keys": ["https://example.com/b"],
                    "clicks": 0,
                    "impressions": 12,
                    "ctr": 0.0,
                    "position": 16.2,
                },
            ]

        filters = request.get("dimensionFilterGroups") or []
        expression = filters[0]["filters"][0]["expression"]  # type: ignore[index]
        if expression == "https://example.com/b":
            raise GscApiError("rate limit on /b")

        return [
            {
                "keys": ["seo alpha"],
                "clicks": 10,
                "impressions": 120,
                "ctr": 0.0833,
                "position": 6.1,
            },
            {
                "keys": ["alpha guide"],
                "clicks": 2,
                "impressions": 80,
                "ctr": 0.025,
                "position": 9.4,
            },
        ]


class RawVariantTopQueriesClient(FakeSearchConsoleApiClient):
    def query_search_analytics(self, property_uri: str, request: dict[str, object]) -> list[dict[str, object]]:
        dimensions = request.get("dimensions")
        if dimensions == ["page"]:
            return super().query_search_analytics(property_uri, request)

        filters = request.get("dimensionFilterGroups") or []
        expression = filters[0]["filters"][0]["expression"]  # type: ignore[index]
        if expression == "https://example.com/a/":
            return [
                {
                    "keys": ["seo alpha"],
                    "clicks": 10,
                    "impressions": 120,
                    "ctr": 0.0833,
                    "position": 6.1,
                }
            ]

        return []


class RedirectTargetTopQueriesClient(FakeSearchConsoleApiClient):
    def query_search_analytics(self, property_uri: str, request: dict[str, object]) -> list[dict[str, object]]:
        dimensions = request.get("dimensions")
        if dimensions == ["page"]:
            return [
                {
                    "keys": ["https://example.com/"],
                    "clicks": 15,
                    "impressions": 200,
                    "ctr": 0.075,
                    "position": 4.2,
                }
            ]

        filters = request.get("dimensionFilterGroups") or []
        expression = filters[0]["filters"][0]["expression"]  # type: ignore[index]
        if expression == "https://example.com/":
            return [
                {
                    "keys": ["brand query"],
                    "clicks": 15,
                    "impressions": 200,
                    "ctr": 0.075,
                    "position": 4.2,
                }
            ]
        return []


class ExplodingTopQueriesClient(FakeSearchConsoleApiClient):
    def query_search_analytics(self, property_uri: str, request: dict[str, object]) -> list[dict[str, object]]:
        dimensions = request.get("dimensions")
        if dimensions == ["page"]:
            return [
                {
                    "keys": ["https://example.com/a"],
                    "clicks": 12,
                    "impressions": 340,
                    "ctr": 0.0353,
                    "position": 8.4,
                },
                {
                    "keys": ["https://example.com/b"],
                    "clicks": 8,
                    "impressions": 120,
                    "ctr": 0.0667,
                    "position": 11.2,
                },
            ]

        filters = request.get("dimensionFilterGroups") or []
        expression = filters[0]["filters"][0]["expression"]  # type: ignore[index]
        if expression == "https://example.com/b":
            raise RuntimeError("boom during top queries import")

        return [
            {
                "keys": ["seo alpha"],
                "clicks": 10,
                "impressions": 120,
                "ctr": 0.0833,
                "position": 6.1,
            }
        ]


class MultiPropertySearchConsoleApiClient(FakeSearchConsoleApiClient):
    def list_sites(self) -> list[dict[str, str]]:
        return [
            {
                "siteUrl": "https://example.com/",
                "permissionLevel": "siteRestrictedUser",
            },
            {
                "siteUrl": "sc-domain:example.com",
                "permissionLevel": "siteOwner",
            },
        ]


def seed_gsc_job(session_factory) -> tuple[int, int]:
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

        gsc_property = GscProperty(
            site_id=site.id,
            property_uri="sc-domain:example.com",
            permission_level="siteOwner",
        )
        session.add(gsc_property)
        session.flush()

        page_a = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/a",
            normalized_url="https://example.com/a",
            final_url="https://example.com/a",
            status_code=200,
            title=None,
            title_length=None,
            meta_description="Alpha meta",
            meta_description_length=50,
            h1="Alpha",
            h1_count=1,
            h2_count=0,
            canonical_url="https://example.com/a",
            robots_meta="index,follow",
            x_robots_tag=None,
            content_type="text/html",
            word_count=120,
            content_text_hash="hash-a",
            images_count=2,
            images_missing_alt_count=1,
            html_size_bytes=1024,
            was_rendered=False,
            render_attempted=False,
            fetch_mode_used="http",
            js_heavy_like=False,
            render_reason=None,
            render_error_message=None,
            schema_present=True,
            schema_count=1,
            schema_types_json=["Article"],
            response_time_ms=30,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        )
        page_b = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/b",
            normalized_url="https://example.com/b",
            final_url="https://example.com/b",
            status_code=200,
            title="Bravo",
            title_length=35,
            meta_description="Bravo meta description",
            meta_description_length=90,
            h1="Bravo",
            h1_count=1,
            h2_count=1,
            canonical_url="https://example.com/b",
            robots_meta="index,follow",
            x_robots_tag=None,
            content_type="text/html",
            word_count=250,
            content_text_hash="hash-b",
            images_count=2,
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
            response_time_ms=22,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        )
        session.add_all([page_a, page_b])
        session.commit()
        return crawl_job.id, page_a.id


def test_gsc_import_persists_metrics_and_top_queries_with_partial_errors(sqlite_session_factory) -> None:
    crawl_job_id, page_id = seed_gsc_job(sqlite_session_factory)

    with sqlite_session_factory() as session:
        result = gsc_service.import_gsc_for_job(
            session,
            crawl_job_id,
            date_ranges=["last_28_days"],
            client=FakeSearchConsoleApiClient(),
        )
        session.commit()

        assert result["ranges"][0]["imported_url_metrics"] == 2
        assert result["ranges"][0]["imported_top_queries"] == 2
        assert result["ranges"][0]["pages_with_top_queries"] == 1
        assert result["ranges"][0]["failed_pages"] == 1
        assert "https://example.com/b" in result["ranges"][0]["errors"][0]

        rows, total_items, page_context = gsc_service.list_top_queries(
            session,
            crawl_job_id,
            page_id=page_id,
            date_range_label="last_28_days",
            sort_by="impressions",
            sort_order="desc",
        )
        assert total_items == 2
        assert rows[0]["query"] == "seo alpha"
        assert page_context is not None
        assert page_context["clicks_28d"] == 12
        assert page_context["has_technical_issue"] is True


def test_pages_endpoint_supports_gsc_filters_sorting_and_exports(api_client, sqlite_session_factory) -> None:
    crawl_job_id, _ = seed_gsc_job(sqlite_session_factory)
    with sqlite_session_factory() as session:
        gsc_service.import_gsc_for_job(
            session,
            crawl_job_id,
            date_ranges=["last_28_days"],
            client=FakeSearchConsoleApiClient(),
        )
        session.commit()

    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/pages",
        params={
            "gsc_date_range": "last_28_days",
            "has_technical_issue": "true",
            "gsc_impressions_min": 1,
            "sort_by": "gsc_clicks",
            "sort_order": "desc",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["url"] == "https://example.com/a"
    assert payload["items"][0]["clicks_28d"] == 12
    assert payload["items"][0]["top_queries_count_28d"] == 2
    assert payload["has_gsc_integration"] is True
    assert payload["available_status_codes"] == [200]

    export_response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/export/pages.csv",
        params={
            "gsc_date_range": "last_28_days",
            "has_technical_issue": "true",
            "gsc_impressions_min": 1,
        },
    )
    assert export_response.status_code == 200
    assert "clicks_28d" in export_response.text
    assert "top_queries_count_28d" in export_response.text
    assert "https://example.com/a" in export_response.text
    assert "https://example.com/b" not in export_response.text


def test_gsc_import_tries_raw_and_normalized_url_variants_for_top_queries(sqlite_session_factory) -> None:
    crawl_job_id, page_id = seed_gsc_job(sqlite_session_factory)

    with sqlite_session_factory() as session:
        page = session.get(Page, page_id)
        assert page is not None
        page.url = "https://example.com/a/"
        page.final_url = "https://example.com/a/"
        page.normalized_url = "https://example.com/a"
        session.commit()

    with sqlite_session_factory() as session:
        result = gsc_service.import_gsc_for_job(
            session,
            crawl_job_id,
            date_ranges=["last_28_days"],
            top_queries_limit=1,
            client=RawVariantTopQueriesClient(),
        )
        session.commit()

        assert result["ranges"][0]["imported_top_queries"] == 1

        rows, total_items, _ = gsc_service.list_top_queries(
            session,
            crawl_job_id,
            page_id=page_id,
            date_range_label="last_28_days",
        )
        assert total_items == 1
        assert rows[0]["query"] == "seo alpha"


def test_gsc_import_skips_distinct_final_url_candidates_for_top_queries(sqlite_session_factory) -> None:
    crawl_job_id, page_id = seed_gsc_job(sqlite_session_factory)

    with sqlite_session_factory() as session:
        root_page = session.get(Page, page_id)
        redirecting_page = session.scalar(
            select(Page).where(Page.crawl_job_id == crawl_job_id, Page.id != page_id).order_by(Page.id.asc())
        )
        assert root_page is not None
        assert redirecting_page is not None
        redirecting_page_id = redirecting_page.id

        root_page.url = "https://example.com/"
        root_page.normalized_url = "https://example.com/"
        root_page.final_url = "https://example.com/"

        redirecting_page.url = "https://example.com/legacy/"
        redirecting_page.normalized_url = "https://example.com/legacy"
        redirecting_page.final_url = "https://example.com/"
        session.commit()

    with sqlite_session_factory() as session:
        result = gsc_service.import_gsc_for_job(
            session,
            crawl_job_id,
            date_ranges=["last_28_days"],
            top_queries_limit=5,
            client=RedirectTargetTopQueriesClient(),
        )
        session.commit()

        assert result["ranges"][0]["imported_top_queries"] == 1
        assert result["ranges"][0]["pages_with_top_queries"] == 1

        root_rows, root_total_items, _ = gsc_service.list_top_queries(
            session,
            crawl_job_id,
            page_id=page_id,
            date_range_label="last_28_days",
        )
        assert root_total_items == 1
        assert root_rows[0]["query"] == "brand query"

        redirect_rows, redirect_total_items, _ = gsc_service.list_top_queries(
            session,
            crawl_job_id,
            page_id=redirecting_page_id,
            date_range_label="last_28_days",
        )
        assert redirect_total_items == 0
        assert redirect_rows == []


def test_gsc_import_commits_completed_stages_before_unexpected_failure(sqlite_session_factory) -> None:
    crawl_job_id, page_id = seed_gsc_job(sqlite_session_factory)

    with sqlite_session_factory() as session:
        with pytest.raises(RuntimeError, match="boom during top queries import"):
            gsc_service.import_gsc_for_job(
                session,
                crawl_job_id,
                date_ranges=["last_28_days"],
                top_queries_limit=5,
                client=ExplodingTopQueriesClient(),
            )

    with sqlite_session_factory() as session:
        summary = gsc_service.build_gsc_summary(session, crawl_job_id)
        active_range = next(item for item in summary["ranges"] if item["date_range_label"] == "last_28_days")
        assert active_range["imported_pages"] == 2

        rows, total_items, page_context = gsc_service.list_top_queries(
            session,
            crawl_job_id,
            page_id=page_id,
            date_range_label="last_28_days",
        )
        assert total_items == 1
        assert rows[0]["query"] == "seo alpha"
        assert page_context is not None
        assert page_context["top_queries_count_28d"] == 1


def test_site_gsc_api_routes_cover_site_level_summary_property_import_and_oauth(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    crawl_job_id, _ = seed_gsc_job(sqlite_session_factory)
    with sqlite_session_factory() as session:
        crawl_job = session.get(CrawlJob, crawl_job_id)
        assert crawl_job is not None
        site_id = crawl_job.site_id

    monkeypatch.setattr(gsc_service, "SearchConsoleApiClient", FakeSearchConsoleApiClient)
    monkeypatch.setattr(gsc_service, "GscTokenStore", lambda: SimpleNamespace(has_token=lambda: True))

    summary_response = api_client.get(f"/sites/{site_id}/gsc/summary", params={"active_crawl_id": crawl_job_id})
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["site_id"] == site_id
    assert summary_payload["selected_property_uri"] == "sc-domain:example.com"
    assert summary_payload["active_crawl"]["id"] == crawl_job_id
    assert summary_payload["active_crawl_has_gsc_data"] is False

    properties_response = api_client.get(f"/sites/{site_id}/gsc/properties")
    assert properties_response.status_code == 200
    assert properties_response.json()[0]["is_selected"] is True

    captured_redirect: dict[str, str] = {}

    def fake_build_authorization_url(*, redirect_url: str) -> str:
        captured_redirect["redirect_url"] = redirect_url
        return "https://accounts.google.com/o/oauth2/auth"

    monkeypatch.setattr(gsc_routes, "build_authorization_url", fake_build_authorization_url)

    start_response = api_client.get(
        f"/sites/{site_id}/gsc/oauth/start",
        params={"active_crawl_id": crawl_job_id},
        follow_redirects=False,
    )
    assert start_response.status_code == 307
    assert start_response.headers["location"] == "https://accounts.google.com/o/oauth2/auth"
    assert captured_redirect["redirect_url"].endswith(f"/sites/{site_id}/gsc?active_crawl_id={crawl_job_id}")

    monkeypatch.setattr(
        gsc_routes,
        "exchange_code_for_credentials",
        lambda state, code: SimpleNamespace(
            redirect_url=f"http://127.0.0.1:5173/sites/{site_id}/gsc?active_crawl_id={crawl_job_id}"
        ),
    )
    callback_response = api_client.get("/gsc/oauth/callback", params={"state": "state", "code": "code"}, follow_redirects=False)
    assert callback_response.status_code == 303
    assert callback_response.headers["location"].endswith(
        f"/sites/{site_id}/gsc?active_crawl_id={crawl_job_id}&oauth=success"
    )

    import_response = api_client.post(
        f"/sites/{site_id}/gsc/import",
        params={"active_crawl_id": crawl_job_id},
        json={"date_ranges": ["last_28_days"]},
    )
    assert import_response.status_code == 200
    assert import_response.json()["crawl_job_id"] == crawl_job_id
    assert import_response.json()["ranges"][0]["imported_url_metrics"] == 2

    refreshed_summary_response = api_client.get(f"/sites/{site_id}/gsc/summary", params={"active_crawl_id": crawl_job_id})
    assert refreshed_summary_response.status_code == 200
    refreshed_summary = refreshed_summary_response.json()
    assert refreshed_summary["active_crawl_has_gsc_data"] is True
    assert refreshed_summary["ranges"][0]["last_imported_at"] is not None


def test_gsc_api_routes_cover_oauth_and_top_queries_export(api_client, sqlite_session_factory, monkeypatch) -> None:
    crawl_job_id, page_id = seed_gsc_job(sqlite_session_factory)
    with sqlite_session_factory() as session:
        gsc_service.import_gsc_for_job(
            session,
            crawl_job_id,
            date_ranges=["last_28_days"],
            client=FakeSearchConsoleApiClient(),
        )
        session.commit()

    monkeypatch.setattr(gsc_routes, "build_authorization_url", lambda redirect_url: "https://accounts.google.com/o/oauth2/auth")
    start_response = api_client.get(f"/crawl-jobs/{crawl_job_id}/gsc/oauth/start", follow_redirects=False)
    assert start_response.status_code == 307
    assert start_response.headers["location"] == "https://accounts.google.com/o/oauth2/auth"

    monkeypatch.setattr(
        gsc_routes,
        "exchange_code_for_credentials",
        lambda state, code: SimpleNamespace(redirect_url=f"http://127.0.0.1:5173/jobs/{crawl_job_id}/gsc"),
    )
    callback_response = api_client.get("/gsc/oauth/callback", params={"state": "state", "code": "code"}, follow_redirects=False)
    assert callback_response.status_code == 303
    assert callback_response.headers["location"].endswith(f"/jobs/{crawl_job_id}/gsc?oauth=success")

    top_queries_response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/pages/{page_id}/gsc/top-queries",
        params={
            "date_range_label": "last_28_days",
            "sort_by": "impressions",
            "sort_order": "desc",
            "query_excludes": "guide",
        },
    )
    assert top_queries_response.status_code == 200
    assert top_queries_response.json()["page_context"]["id"] == page_id
    assert "title" in top_queries_response.json()["page_context"]
    assert top_queries_response.json()["items"][0]["query"] == "seo alpha"
    assert len(top_queries_response.json()["items"]) == 1

    export_response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/export/gsc-top-queries.csv",
        params={"page_id": page_id, "date_range_label": "last_28_days", "query_excludes": "guide"},
    )
    assert export_response.status_code == 200
    assert "seo alpha" in export_response.text
    assert "alpha guide" not in export_response.text


def test_job_level_property_selection_updates_site_level_gsc_configuration(api_client, sqlite_session_factory, monkeypatch) -> None:
    crawl_job_id, _ = seed_gsc_job(sqlite_session_factory)
    with sqlite_session_factory() as session:
        crawl_job = session.get(CrawlJob, crawl_job_id)
        assert crawl_job is not None
        site_id = crawl_job.site_id

    monkeypatch.setattr(gsc_service, "SearchConsoleApiClient", MultiPropertySearchConsoleApiClient)
    monkeypatch.setattr(gsc_service, "GscTokenStore", lambda: SimpleNamespace(has_token=lambda: True))

    select_response = api_client.put(
        f"/crawl-jobs/{crawl_job_id}/gsc/property",
        json={"property_uri": "https://example.com/"},
    )
    assert select_response.status_code == 200
    assert select_response.json()["site_id"] == site_id
    assert select_response.json()["property_uri"] == "https://example.com/"

    site_summary_response = api_client.get(f"/sites/{site_id}/gsc/summary", params={"active_crawl_id": crawl_job_id})
    assert site_summary_response.status_code == 200
    assert site_summary_response.json()["selected_property_uri"] == "https://example.com/"

    job_summary_response = api_client.get(f"/crawl-jobs/{crawl_job_id}/gsc/summary")
    assert job_summary_response.status_code == 200
    assert job_summary_response.json()["selected_property_uri"] == "https://example.com/"


def test_gsc_oauth_start_accepts_explicit_local_frontend_redirect(api_client, sqlite_session_factory, monkeypatch) -> None:
    crawl_job_id, _ = seed_gsc_job(sqlite_session_factory)

    captured: dict[str, str] = {}

    def fake_build_authorization_url(*, redirect_url: str) -> str:
        captured["redirect_url"] = redirect_url
        return "https://accounts.google.com/o/oauth2/auth"

    monkeypatch.setattr(gsc_routes, "build_authorization_url", fake_build_authorization_url)

    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/gsc/oauth/start",
        params={"frontend_redirect_url": f"http://localhost:5173/jobs/{crawl_job_id}/gsc"},
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "https://accounts.google.com/o/oauth2/auth"
    assert captured["redirect_url"] == f"http://localhost:5173/jobs/{crawl_job_id}/gsc"


def test_gsc_oauth_start_rejects_non_local_frontend_redirect(api_client, sqlite_session_factory) -> None:
    crawl_job_id, _ = seed_gsc_job(sqlite_session_factory)

    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/gsc/oauth/start",
        params={"frontend_redirect_url": f"https://example.com/jobs/{crawl_job_id}/gsc"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "frontend_redirect_url must match an allowed local frontend origin."


def test_gsc_oauth_callback_returns_readable_error_instead_of_500(api_client, monkeypatch) -> None:
    monkeypatch.setattr(gsc_routes, "exchange_code_for_credentials", lambda state, code: (_ for _ in ()).throw(RuntimeError("boom")))

    response = api_client.get("/gsc/oauth/callback", params={"state": "state", "code": "code"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Unexpected Google OAuth callback failure. Check backend logs and restart the GSC flow."


def test_gsc_oauth_callback_returns_400_for_auth_errors(api_client, monkeypatch) -> None:
    monkeypatch.setattr(
        gsc_routes,
        "exchange_code_for_credentials",
        lambda state, code: (_ for _ in ()).throw(GscAuthError("OAuth state is missing or expired.")),
    )

    response = api_client.get("/gsc/oauth/callback", params={"state": "state", "code": "code"})

    assert response.status_code == 400
    assert response.json()["detail"] == "OAuth state is missing or expired."


def test_google_oauth_error_description_includes_invalid_grant_context() -> None:
    class FakeResponse:
        text = '{"error":"invalid_grant","error_description":"Bad Request"}'

        @staticmethod
        def json() -> dict[str, str]:
            return {"error": "invalid_grant", "error_description": "Bad Request"}

    exc = RuntimeError("oauth failed")
    exc.response = FakeResponse()  # type: ignore[attr-defined]

    detail = gsc_auth._describe_google_oauth_exception(exc)

    assert "invalid_grant: Bad Request" in detail
    assert "reused or expired authorization code" in detail


def test_pkce_code_verifier_is_persisted_and_reused(tmp_path, monkeypatch) -> None:
    class FakeCredentials:
        def to_json(self) -> str:
            return '{"token": "test-token"}'

    class FakeFlow:
        def __init__(
            self,
            *,
            state: str | None = None,
            code_verifier: str | None = None,
            autogenerate_code_verifier: bool = True,
        ) -> None:
            self.state = state
            self.code_verifier = code_verifier
            self.autogenerate_code_verifier = autogenerate_code_verifier
            self.redirect_uri: str | None = None
            self.credentials = FakeCredentials()

        @classmethod
        def from_client_secrets_file(
            cls,
            path: str,
            scopes: list[str],
            state: str | None = None,
            code_verifier: str | None = None,
            autogenerate_code_verifier: bool = True,
        ) -> "FakeFlow":
            return cls(
                state=state,
                code_verifier=code_verifier,
                autogenerate_code_verifier=autogenerate_code_verifier,
            )

        def authorization_url(self, **kwargs: object) -> tuple[str, str]:
            self.code_verifier = "pkce-verifier"
            return "https://accounts.google.com/o/oauth2/auth", "state-123"

        def fetch_token(self, **kwargs: object) -> dict[str, str]:
            assert kwargs["code"] == "test-code"
            assert self.code_verifier == "pkce-verifier"
            return {"access_token": "test-token"}

    monkeypatch.setattr(gsc_auth, "Flow", FakeFlow)
    monkeypatch.setattr(gsc_auth, "ensure_client_secrets_file", lambda: Path(tmp_path / "credentials.json"))

    state_store = gsc_auth.GscOAuthStateStore(path=str(tmp_path / "oauth_state.json"))
    token_store = gsc_auth.GscTokenStore(path=str(tmp_path / "token.json"))

    authorization_url = gsc_auth.build_authorization_url(
        redirect_url="http://127.0.0.1:5173/jobs/8/gsc",
        state_store=state_store,
    )
    assert authorization_url == "https://accounts.google.com/o/oauth2/auth"

    state_payload = gsc_auth.exchange_code_for_credentials(
        state="state-123",
        code="test-code",
        state_store=state_store,
        token_store=token_store,
    )

    assert state_payload.redirect_url == "http://127.0.0.1:5173/jobs/8/gsc"
    assert token_store.path.exists()
