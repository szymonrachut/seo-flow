from __future__ import annotations

import csv
import io
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import (
    GscProperty,
    GscTopQuery,
    SiteCompetitor,
    SiteCompetitorPage,
    SiteCompetitorPageExtraction,
    SiteContentGapCandidate,
    SiteCompetitorSemanticCandidate,
    SiteCompetitorSemanticDecision,
    SiteCompetitorSemanticRun,
    SiteCompetitorSyncRun,
)
from app.integrations.openai.client import OpenAiIntegrationError, _extract_api_error_details
from app.services import (
    content_gap_candidate_service,
    content_gap_item_materialization_service,
    content_gap_review_run_service,
    competitive_gap_semantic_run_service,
    competitive_gap_semantic_service,
    competitive_gap_sync_run_service,
    competitive_gap_sync_service,
    semstorm_brief_service,
    semstorm_service,
)
from app.services.competitive_gap_keys import build_competitive_gap_signature
from app.services.competitive_gap_llm_service import (
    GAP_EXPLANATION_PROMPT_VERSION,
    STRATEGY_NORMALIZATION_PROMPT_VERSION,
    CompetitiveGapExplanationOutput,
)
from app.services.competitive_gap_extraction_service import CompetitorExtractionResult
from app.services.competitive_gap_page_diagnostics import build_fetch_diagnostics_payload
from app.services.competitive_gap_semantic_card_service import build_semantic_card
from app.schemas.competitive_gap import NormalizedCompetitiveGapStrategy
from tests.competitive_gap_test_utils import FIXED_TIME, seed_competitive_gap_site
from tests.test_content_gap_review_run_service import _add_candidate, _seed_site_with_two_crawls


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_strategy_crud_endpoint(api_client, sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    response = api_client.get(f"/sites/{site_id}/competitive-content-gap/strategy")
    assert response.status_code == 200
    payload = response.json()
    assert payload["site_id"] == site_id
    assert payload["normalization_status"] == "ready"

    update_response = api_client.put(
        f"/sites/{site_id}/competitive-content-gap/strategy",
        json={
            "raw_user_input": "Focus on content strategy and audits.",
            "normalized_strategy_json": {
                "schema_version": "competitive_gap_strategy_v1",
                "business_summary": "SEO consultancy focused on audits and content strategy.",
                "target_audiences": ["marketing teams"],
                "primary_goals": ["lead generation"],
                "priority_topics": ["content strategy", "seo audit"],
                "supporting_topics": ["technical seo"],
                "priority_page_types": ["service"],
                "geographic_focus": ["Poland"],
                "constraints": [],
                "differentiation_points": ["consulting-first execution"],
            },
        },
    )
    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert updated_payload["raw_user_input"] == "Focus on content strategy and audits."
    assert updated_payload["normalization_status"] == "ready"
    assert updated_payload["normalized_strategy_json"]["schema_version"] == "competitive_gap_strategy_v1"

    delete_response = api_client.delete(f"/sites/{site_id}/competitive-content-gap/strategy")
    assert delete_response.status_code == 204

    fetch_after_delete = api_client.get(f"/sites/{site_id}/competitive-content-gap/strategy")
    assert fetch_after_delete.status_code == 200
    assert fetch_after_delete.json() is None


def test_competitor_crud_endpoint_blocks_duplicates(api_client, sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    list_response = api_client.get(f"/sites/{site_id}/competitive-content-gap/competitors")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 2

    create_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/competitors",
        json={
            "root_url": "https://competitor-c.com",
            "label": "Competitor C",
            "notes": "Manual competitor",
            "is_active": True,
        },
    )
    assert create_response.status_code == 201
    created_payload = create_response.json()
    competitor_id = created_payload["id"]
    assert created_payload["domain"] == "competitor-c.com"
    assert created_payload["semantic_analysis_mode"] == "not_started"
    assert created_payload["semantic_llm_merged_urls_count"] == 0

    duplicate_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/competitors",
        json={
            "root_url": "https://competitor-c.com/other-path",
            "label": "Duplicate",
            "is_active": True,
        },
    )
    assert duplicate_response.status_code == 400
    assert "already exists" in duplicate_response.json()["detail"].lower()

    update_response = api_client.put(
        f"/sites/{site_id}/competitive-content-gap/competitors/{competitor_id}",
        json={"label": "Competitor C Updated", "is_active": False},
    )
    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert updated_payload["label"] == "Competitor C Updated"
    assert updated_payload["is_active"] is False

    delete_response = api_client.delete(
        f"/sites/{site_id}/competitive-content-gap/competitors/{competitor_id}"
    )
    assert delete_response.status_code == 204


def test_semstorm_discovery_preview_endpoint_returns_preview_payload(api_client, sqlite_session_factory, monkeypatch) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    captured_kwargs: dict[str, object] = {}

    def _fake_preview(session, requested_site_id, **kwargs):
        captured_kwargs["site_id"] = requested_site_id
        captured_kwargs.update(kwargs)
        return {
            "site_id": requested_site_id,
            "source_domain": "example.com",
            "semstorm_enabled": True,
            "result_type": "organic",
            "competitors_type": "all",
            "include_basic_stats": True,
            "max_competitors": 2,
            "max_keywords_per_competitor": 2,
            "competitors": [
                {
                    "domain": "competitor-a.com",
                    "common_keywords": 41,
                    "traffic": 210,
                    "basic_stats": {
                        "keywords": 120,
                        "keywords_top": 22,
                        "traffic": 210,
                        "traffic_potential": 380,
                        "search_volume": 1800,
                        "search_volume_top": 650,
                    },
                    "top_queries": [
                        {
                            "keyword": "seo audit checklist",
                            "position": 2,
                            "position_change": 1,
                            "url": "https://competitor-a.com/seo-audit-checklist",
                            "traffic": 91,
                            "traffic_change": 11,
                            "volume": 1300,
                            "competitors": 8,
                            "cpc": 3.4,
                            "trends": [1, 2, 11],
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(semstorm_service, "build_semstorm_discovery_preview", _fake_preview)

    response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-preview",
        json={
            "max_competitors": 2,
            "max_keywords_per_competitor": 2,
            "result_type": "organic",
            "include_basic_stats": True,
            "competitors_type": "all",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert captured_kwargs == {
        "site_id": site_id,
        "max_competitors": 2,
        "max_keywords_per_competitor": 2,
        "result_type": "organic",
        "include_basic_stats": True,
        "competitors_type": "all",
    }
    assert payload["site_id"] == site_id
    assert payload["source_domain"] == "example.com"
    assert payload["semstorm_enabled"] is True
    assert payload["competitors"][0]["domain"] == "competitor-a.com"
    assert payload["competitors"][0]["top_queries"][0]["trends"] == [1, 2, 11]


def test_semstorm_discovery_preview_endpoint_propagates_service_status_code(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    def _raise_preview_error(session, requested_site_id, **kwargs):
        raise semstorm_service.SemstormServiceError(
            "Semstorm request timed out.",
            code="timeout",
            status_code=504,
        )

    monkeypatch.setattr(semstorm_service, "build_semstorm_discovery_preview", _raise_preview_error)

    response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-preview",
        json={},
    )
    assert response.status_code == 504
    assert response.json() == {"detail": "Semstorm request timed out."}


def test_semstorm_connection_check_endpoint_returns_debug_payload(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    captured_kwargs: dict[str, object] = {}

    def _fake_debug(session, requested_site_id, **kwargs):
        captured_kwargs["site_id"] = requested_site_id
        captured_kwargs.update(kwargs)
        return {
            "site_id": requested_site_id,
            "source_domain": "example.com",
            "semstorm_enabled": True,
            "request": {
                "provider_name": "semstorm",
                "documentation_url": "https://api-v3.semstorm.com/",
                "sdk_readme_url": "https://github.com/semstorm/semstorm-php-sdk",
                "base_url": "https://api.semstorm.com/api-v3",
                "endpoint_path": "/explorer/explorer-competitors/get-data.json",
                "request_url": "https://api.semstorm.com/api-v3/explorer/explorer-competitors/get-data.json",
                "request_method": "POST",
                "content_type": "application/json",
                "timeout_seconds": 60.0,
                "max_retries": 2,
                "retry_backoff_seconds": 1.0,
                "services_token_configured": True,
                "auth": {
                    "mode": "query_param",
                    "parameter_name": "services_token",
                    "username_required": False,
                },
                "request_payload_preview": {
                    "domains": ["example.com"],
                    "result_type": "organic",
                    "pager": {"items_per_page": 10, "page": 0},
                    "competitors_type": "all",
                },
            },
            "provider_check": {
                "attempted": True,
                "ok": False,
                "elapsed_ms": 30123,
                "result_count": None,
                "response_shape": None,
                "error_code": "provider_error",
                "error_message_safe": "Unauthorized access.",
            },
        }

    monkeypatch.setattr(semstorm_service, "debug_semstorm_connection", _fake_debug)

    response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/debug/connection-check",
        json={
            "result_type": "organic",
            "competitors_type": "all",
            "perform_provider_check": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert captured_kwargs == {
        "site_id": site_id,
        "result_type": "organic",
        "competitors_type": "all",
        "perform_provider_check": True,
    }
    assert payload["request"]["auth"]["parameter_name"] == "services_token"
    assert payload["request"]["auth"]["username_required"] is False
    assert payload["provider_check"]["error_message_safe"] == "Unauthorized access."


def _add_semstorm_gsc_top_query(
    session_factory,
    *,
    site_id: int,
    crawl_job_id: int,
    page_id: int,
    url: str,
    query: str,
    clicks: int,
    impressions: int,
    ctr: float,
    position: float,
) -> None:
    with session_factory() as session:
        gsc_property_id = session.scalar(select(GscProperty.id).where(GscProperty.site_id == site_id))
        assert gsc_property_id is not None
        session.add(
            GscTopQuery(
                gsc_property_id=int(gsc_property_id),
                crawl_job_id=crawl_job_id,
                page_id=page_id,
                url=url,
                normalized_url=url,
                date_range_label="last_28_days",
                query=query,
                clicks=clicks,
                impressions=impressions,
                ctr=ctr,
                position=position,
                fetched_at=FIXED_TIME,
                created_at=FIXED_TIME,
            )
        )
        session.commit()


class ApiPersistedSemstormClient:
    def get_competitors(self, *, domains, result_type="organic", competitors_type="all", max_items=10):
        assert list(domains) == ["example.com"]
        assert result_type == "organic"
        assert competitors_type == "all"
        assert max_items == 2
        return [
            {"competitor": "example.com", "common_keywords": 900, "traffic": 900},
            {"competitor": "competitor-a.com", "common_keywords": 40, "traffic": 110},
            {"competitor": "competitor-b.com", "common_keywords": 18, "traffic": 60},
        ]

    def get_keywords_basic_stats(self, *, domains, result_type="organic"):
        assert result_type == "organic"
        return {
            "competitor-a.com": {
                "keywords": 120,
                "keywords_top": 25,
                "traffic": 480,
                "traffic_potential": 700,
                "search_volume": 3200,
                "search_volume_top": 900,
            },
            "competitor-b.com": {
                "keywords": 75,
                "keywords_top": 15,
                "traffic": 220,
                "traffic_potential": 350,
                "search_volume": 1800,
                "search_volume_top": 420,
            },
        }

    def get_keywords(self, *, domains, result_type="organic", max_items=10, sorting=None):
        assert result_type == "organic"
        assert max_items == 3
        assert sorting == {"field": "traffic:0", "sort": "desc"}
        domain = domains[0]
        if domain == "competitor-a.com":
            return [
                {
                    "keyword": "seo audit",
                    "position": {"competitor-a.com": 2},
                    "position_c": {"competitor-a.com": 3},
                    "url": {"competitor-a.com": "https://competitor-a.com/seo-audit"},
                    "traffic": {"competitor-a.com": 91},
                    "traffic_c": {"competitor-a.com": 12},
                    "volume": 1300,
                    "competitors": 8,
                    "cpc": 3.4,
                    "trends": "1,2,11",
                },
                {
                    "keyword": "content strategy template",
                    "position": {"competitor-a.com": 7},
                    "position_c": {"competitor-a.com": 1},
                    "url": {"competitor-a.com": "https://competitor-a.com/content-strategy-template"},
                    "traffic": {"competitor-a.com": 24},
                    "traffic_c": {"competitor-a.com": 4},
                    "volume": 180,
                    "competitors": 4,
                    "cpc": 1.8,
                    "trends": [2, 2, 3],
                },
                {
                    "keyword": "local seo pricing",
                    "position": {"competitor-a.com": 16},
                    "position_c": {"competitor-a.com": -1},
                    "url": {"competitor-a.com": "https://competitor-a.com/local-seo-pricing"},
                    "traffic": {"competitor-a.com": 45},
                    "traffic_c": {"competitor-a.com": -4},
                    "volume": 700,
                    "competitors": 6,
                    "cpc": 4.9,
                    "trends": [],
                },
            ]
        if domain == "competitor-b.com":
            return [
                {
                    "keyword": "seo audit",
                    "position": {"competitor-b.com": 5},
                    "position_c": {"competitor-b.com": 1},
                    "url": {"competitor-b.com": "https://competitor-b.com/seo-audit"},
                    "traffic": {"competitor-b.com": 60},
                    "traffic_c": {"competitor-b.com": 2},
                    "volume": 1250,
                    "competitors": 7,
                    "cpc": 2.6,
                    "trends": [4, 5],
                },
                {
                    "keyword": "content strategy template",
                    "position": {"competitor-b.com": 9},
                    "position_c": {"competitor-b.com": 0},
                    "url": {"competitor-b.com": "https://competitor-b.com/content-strategy-template"},
                    "traffic": {"competitor-b.com": 18},
                    "traffic_c": {"competitor-b.com": 1},
                    "volume": 160,
                    "competitors": 5,
                    "cpc": 1.2,
                    "trends": [1, 3],
                },
                {
                    "keyword": "local seo pricing",
                    "position": {"competitor-b.com": 14},
                    "position_c": {"competitor-b.com": 1},
                    "url": {"competitor-b.com": "https://competitor-b.com/local-seo-pricing"},
                    "traffic": {"competitor-b.com": 33},
                    "traffic_c": {"competitor-b.com": 2},
                    "volume": 700,
                    "competitors": 7,
                    "cpc": 4.9,
                    "trends": [3, 4],
                },
            ]
        raise AssertionError(f"Unexpected domains call: {domains!r}")


def _create_completed_semstorm_brief_via_api(api_client, *, site_id: int) -> int:
    create_run_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs",
        json={
            "max_competitors": 2,
            "max_keywords_per_competitor": 3,
            "include_basic_stats": True,
        },
    )
    assert create_run_response.status_code == 201

    promote_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/promote",
        json={
            "run_id": 1,
            "keywords": ["seo audit"],
        },
    )
    assert promote_response.status_code == 200

    create_plan_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/promoted/actions/create-plan",
        json={
            "promoted_item_ids": [item["id"] for item in promote_response.json()["promoted_items"]],
        },
    )
    assert create_plan_response.status_code == 200
    plan_id = int(create_plan_response.json()["items"][0]["id"])

    create_brief_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/plans/actions/create-brief",
        json={"plan_item_ids": [plan_id]},
    )
    assert create_brief_response.status_code == 200
    brief_id = int(create_brief_response.json()["items"][0]["id"])

    for next_status in ("ready", "in_execution", "completed"):
        transition_response = api_client.post(
            f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/execution-status",
            json={"execution_status": next_status},
        )
        assert transition_response.status_code == 200

    return brief_id


def test_semstorm_discovery_run_endpoints_create_list_detail_and_opportunities(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    fake_client = ApiPersistedSemstormClient()
    _add_semstorm_gsc_top_query(
        sqlite_session_factory,
        site_id=site_id,
        crawl_job_id=ids["crawl_job_id"],
        page_id=ids["audit_page_id"],
        url="https://example.com/seo-audit",
        query="seo audit",
        clicks=19,
        impressions=210,
        ctr=0.09,
        position=4.2,
    )

    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    monkeypatch.setattr(semstorm_service, "SemstormApiClient", lambda: fake_client)

    create_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs",
        json={
            "max_competitors": 2,
            "max_keywords_per_competitor": 3,
            "result_type": "organic",
            "include_basic_stats": True,
            "competitors_type": "all",
        },
    )
    assert create_response.status_code == 201
    create_payload = create_response.json()
    assert create_payload["run_id"] == 1
    assert create_payload["status"] == "completed"
    assert create_payload["source_domain"] == "example.com"
    assert create_payload["params"] == {
        "max_competitors": 2,
        "max_keywords_per_competitor": 3,
        "result_type": "organic",
        "include_basic_stats": True,
        "competitors_type": "all",
    }
    assert create_payload["summary"]["total_competitors"] == 2
    assert create_payload["summary"]["total_queries"] == 6
    assert create_payload["summary"]["unique_keywords"] == 3
    assert [item["domain"] for item in create_payload["competitors"]] == ["competitor-a.com", "competitor-b.com"]

    list_response = api_client.get(f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload) == 1
    assert list_payload[0]["run_id"] == 1
    assert list_payload[0]["summary"]["total_queries"] == 6

    detail_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs/1"
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["run_id"] == 1
    assert detail_payload["competitors"][0]["top_queries"][0]["keyword"] == "seo audit"

    opportunities_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities"
    )
    assert opportunities_response.status_code == 200
    opportunities_payload = opportunities_response.json()
    assert opportunities_payload["run_id"] == 1
    assert opportunities_payload["active_crawl_id"] == ids["crawl_job_id"]
    assert opportunities_payload["summary"]["bucket_counts"] == {
        "quick_win": 1,
        "core_opportunity": 1,
        "watchlist": 1,
    }
    assert opportunities_payload["summary"]["decision_type_counts"] == {
        "create_new_page": 1,
        "expand_existing_page": 1,
        "monitor_only": 1,
    }
    assert opportunities_payload["summary"]["coverage_status_counts"] == {
        "missing": 1,
        "weak_coverage": 1,
        "covered": 1,
    }
    assert opportunities_payload["summary"]["state_counts"] == {
        "new": 3,
        "accepted": 0,
        "dismissed": 0,
        "promoted": 0,
    }

    by_keyword = {item["keyword"]: item for item in opportunities_payload["items"]}
    assert by_keyword["seo audit"]["bucket"] == "core_opportunity"
    assert by_keyword["seo audit"]["coverage_status"] == "covered"
    assert by_keyword["seo audit"]["decision_type"] == "monitor_only"
    assert by_keyword["seo audit"]["gsc_signal_status"] == "present"
    assert by_keyword["seo audit"]["state_status"] == "new"
    assert by_keyword["content strategy template"]["coverage_status"] == "weak_coverage"
    assert by_keyword["content strategy template"]["decision_type"] == "expand_existing_page"
    assert by_keyword["content strategy template"]["gsc_signal_status"] == "weak"
    assert by_keyword["local seo pricing"]["coverage_status"] == "missing"
    assert by_keyword["local seo pricing"]["decision_type"] == "create_new_page"
    assert by_keyword["local seo pricing"]["gsc_signal_status"] == "none"


def test_semstorm_opportunities_endpoint_filters_by_coverage_status_and_decision_type(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    monkeypatch.setattr(semstorm_service, "SemstormApiClient", lambda: ApiPersistedSemstormClient())

    create_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs",
        json={
            "max_competitors": 2,
            "max_keywords_per_competitor": 3,
            "include_basic_stats": True,
        },
    )
    assert create_response.status_code == 201

    missing_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities",
        params={"coverage_status": "missing"},
    )
    assert missing_response.status_code == 200
    missing_items = missing_response.json()["items"]
    assert [item["keyword"] for item in missing_items] == ["local seo pricing"]

    expand_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities",
        params={"decision_type": "expand_existing_page"},
    )
    assert expand_response.status_code == 200
    expand_items = expand_response.json()["items"]
    assert [item["keyword"] for item in expand_items] == ["content strategy template"]


def test_semstorm_opportunity_actions_and_promoted_endpoints_support_bulk_and_mixed_success(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    monkeypatch.setattr(semstorm_service, "SemstormApiClient", lambda: ApiPersistedSemstormClient())

    create_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs",
        json={
            "max_competitors": 2,
            "max_keywords_per_competitor": 3,
            "include_basic_stats": True,
        },
    )
    assert create_response.status_code == 201

    accept_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/accept",
        json={
            "run_id": 1,
            "keywords": ["seo audit", "missing keyword"],
            "note": "Review next sprint",
        },
    )
    assert accept_response.status_code == 200
    accept_payload = accept_response.json()
    assert accept_payload["updated_count"] == 1
    assert accept_payload["updated_keywords"] == ["seo audit"]
    assert accept_payload["skipped"] == [{"keyword": "missing keyword", "reason": "keyword_not_in_run"}]

    dismiss_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/dismiss",
        json={
            "run_id": 1,
            "keywords": ["local seo pricing"],
            "note": "Not a fit",
        },
    )
    assert dismiss_response.status_code == 200
    assert dismiss_response.json()["updated_keywords"] == ["local seo pricing"]

    promote_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/promote",
        json={
            "run_id": 1,
            "keywords": ["seo audit", "local seo pricing"],
            "note": "Backlog seed",
        },
    )
    assert promote_response.status_code == 200
    promote_payload = promote_response.json()
    assert promote_payload["promoted_count"] == 1
    assert promote_payload["promoted_items"][0]["keyword"] == "seo audit"
    assert promote_payload["skipped"] == [
        {"keyword": "local seo pricing", "reason": "dismissed_requires_accept"}
    ]

    duplicate_promote_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/promote",
        json={
            "run_id": 1,
            "keywords": ["seo audit"],
        },
    )
    assert duplicate_promote_response.status_code == 200
    assert duplicate_promote_response.json()["skipped"] == [
        {"keyword": "seo audit", "reason": "already_promoted"}
    ]

    opportunities_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities",
        params={"state_status": "promoted"},
    )
    assert opportunities_response.status_code == 200
    opportunities_payload = opportunities_response.json()
    assert opportunities_payload["summary"]["state_counts"]["promoted"] == 1
    assert [item["keyword"] for item in opportunities_payload["items"]] == ["seo audit"]

    actionable_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities",
        params={"only_actionable": True},
    )
    assert actionable_response.status_code == 200
    assert {item["keyword"] for item in actionable_response.json()["items"]} == {"content strategy template"}

    promoted_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/promoted"
    )
    assert promoted_response.status_code == 200
    promoted_payload = promoted_response.json()
    assert promoted_payload["summary"] == {
        "total_items": 1,
        "promotion_status_counts": {"active": 1, "archived": 0},
    }
    assert promoted_payload["items"][0]["keyword"] == "seo audit"
    assert promoted_payload["items"][0]["source_run_id"] == 1


def test_semstorm_opportunity_action_endpoint_returns_404_without_completed_run(
    api_client,
    sqlite_session_factory,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/accept",
        json={
            "keywords": ["seo audit"],
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "No completed Semstorm discovery run found for this site."


def test_semstorm_plan_endpoints_support_create_list_detail_update_and_filters(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    monkeypatch.setattr(semstorm_service, "SemstormApiClient", lambda: ApiPersistedSemstormClient())

    create_run_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs",
        json={
            "max_competitors": 2,
            "max_keywords_per_competitor": 3,
            "include_basic_stats": True,
        },
    )
    assert create_run_response.status_code == 201

    promote_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/promote",
        json={
            "run_id": 1,
            "keywords": ["seo audit", "content strategy template"],
        },
    )
    assert promote_response.status_code == 200

    promoted_response = api_client.get(f"/sites/{site_id}/competitive-content-gap/semstorm/promoted")
    assert promoted_response.status_code == 200
    promoted_items = promoted_response.json()["items"]
    promoted_ids = {item["keyword"]: int(item["id"]) for item in promoted_items}
    assert promoted_items[0]["has_plan"] is False

    from app.db.models import Site, SiteSemstormPromotedItem

    with sqlite_session_factory() as session:
        foreign_site = Site(root_url="https://other-example.com", domain="other-example.com", created_at=FIXED_TIME)
        session.add(foreign_site)
        session.flush()
        foreign_item = SiteSemstormPromotedItem(
            site_id=foreign_site.id,
            opportunity_key="semstorm:foreign123",
            source_run_id=1,
            keyword="foreign keyword",
            normalized_keyword="foreign keyword",
            bucket="watchlist",
            decision_type="monitor_only",
            opportunity_score_v2=10,
            coverage_status="missing",
            best_match_page_url=None,
            gsc_signal_status="none",
            source_payload_json={},
            promotion_status="active",
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        session.add(foreign_item)
        session.commit()
        foreign_promoted_id = int(foreign_item.id)

    create_plan_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/promoted/actions/create-plan",
        json={
            "promoted_item_ids": [
                promoted_ids["seo audit"],
                foreign_promoted_id,
                9999,
            ],
            "defaults": {
                "target_page_type": "new_page",
            },
        },
    )
    assert create_plan_response.status_code == 200
    create_plan_payload = create_plan_response.json()
    assert create_plan_payload["created_count"] == 1
    assert create_plan_payload["updated_count"] == 0
    assert create_plan_payload["skipped_count"] == 2
    assert create_plan_payload["items"][0]["keyword"] == "seo audit"
    assert {item["reason"] for item in create_plan_payload["skipped"]} == {"promoted_item_not_found"}

    duplicate_plan_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/promoted/actions/create-plan",
        json={
            "promoted_item_ids": [promoted_ids["seo audit"]],
        },
    )
    assert duplicate_plan_response.status_code == 200
    assert duplicate_plan_response.json()["skipped"] == [
        {
            "promoted_item_id": promoted_ids["seo audit"],
            "keyword": "seo audit",
            "reason": "already_exists",
        }
    ]

    promoted_after_plan_response = api_client.get(f"/sites/{site_id}/competitive-content-gap/semstorm/promoted")
    assert promoted_after_plan_response.status_code == 200
    promoted_after_plan = promoted_after_plan_response.json()
    seo_audit_promoted = next(item for item in promoted_after_plan["items"] if item["keyword"] == "seo audit")
    assert seo_audit_promoted["has_plan"] is True
    assert seo_audit_promoted["plan_id"] is not None

    plans_response = api_client.get(f"/sites/{site_id}/competitive-content-gap/semstorm/plans")
    assert plans_response.status_code == 200
    plans_payload = plans_response.json()
    assert plans_payload["summary"]["total_count"] == 1
    assert plans_payload["summary"]["state_counts"]["planned"] == 1
    plan_id = int(plans_payload["items"][0]["id"])

    detail_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/plans/{plan_id}"
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["keyword"] == "seo audit"

    status_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/plans/{plan_id}/status",
        json={"state_status": "in_progress"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["state_status"] == "in_progress"

    update_response = api_client.put(
        f"/sites/{site_id}/competitive-content-gap/semstorm/plans/{plan_id}",
        json={
            "plan_title": "SEO audit working plan",
            "plan_note": "Draft content plan for next sprint.",
            "target_page_type": "cluster_support",
            "proposed_slug": "seo-audit-plan",
            "proposed_primary_keyword": "seo audit plan",
            "proposed_secondary_keywords": ["technical seo audit", "audit checklist"],
        },
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["plan_title"] == "SEO audit working plan"
    assert update_payload["target_page_type"] == "cluster_support"
    assert update_payload["proposed_secondary_keywords"] == [
        "technical seo audit",
        "audit checklist",
    ]

    filtered_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/plans",
        params={
            "state_status": "in_progress",
            "target_page_type": "cluster_support",
            "search": "working",
        },
    )
    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert filtered_payload["summary"]["total_count"] == 1
    assert filtered_payload["summary"]["state_counts"]["in_progress"] == 1
    assert filtered_payload["summary"]["target_page_type_counts"]["cluster_support"] == 1
    assert filtered_payload["items"][0]["id"] == plan_id


def test_semstorm_brief_endpoints_support_create_list_detail_update_and_filters(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    monkeypatch.setattr(semstorm_service, "SemstormApiClient", lambda: ApiPersistedSemstormClient())

    create_run_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs",
        json={
            "max_competitors": 2,
            "max_keywords_per_competitor": 3,
            "include_basic_stats": True,
        },
    )
    assert create_run_response.status_code == 201

    promote_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/promote",
        json={
            "run_id": 1,
            "keywords": ["seo audit", "local seo pricing"],
        },
    )
    assert promote_response.status_code == 200

    create_plan_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/promoted/actions/create-plan",
        json={
            "promoted_item_ids": [item["id"] for item in promote_response.json()["promoted_items"]],
        },
    )
    assert create_plan_response.status_code == 200
    plan_ids = {item["keyword"]: int(item["id"]) for item in create_plan_response.json()["items"]}
    assert all(item["has_brief"] is False for item in create_plan_response.json()["items"])

    from app.db.models import Site, SiteSemstormPlanItem, SiteSemstormPromotedItem

    with sqlite_session_factory() as session:
        foreign_site = Site(root_url="https://foreign.example.com", domain="foreign.example.com", created_at=FIXED_TIME)
        session.add(foreign_site)
        session.flush()
        foreign_promoted_item = SiteSemstormPromotedItem(
            site_id=foreign_site.id,
            opportunity_key="semstorm:foreign-brief",
            source_run_id=1,
            keyword="foreign keyword",
            normalized_keyword="foreign keyword",
            bucket="watchlist",
            decision_type="monitor_only",
            opportunity_score_v2=10,
            coverage_status="missing",
            best_match_page_url=None,
            gsc_signal_status="none",
            source_payload_json={},
            promotion_status="active",
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        session.add(foreign_promoted_item)
        session.flush()
        foreign_plan_item = SiteSemstormPlanItem(
            site_id=foreign_site.id,
            promoted_item_id=foreign_promoted_item.id,
            keyword="foreign keyword",
            normalized_keyword="foreign keyword",
            source_run_id=1,
            state_status="planned",
            decision_type_snapshot="monitor_only",
            bucket_snapshot="watchlist",
            coverage_status_snapshot="missing",
            opportunity_score_v2_snapshot=10,
            best_match_page_url_snapshot=None,
            gsc_signal_status_snapshot="none",
            plan_title="Foreign plan",
            plan_note=None,
            target_page_type="new_page",
            proposed_slug="foreign-keyword",
            proposed_primary_keyword="foreign keyword",
            proposed_secondary_keywords_json=[],
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        session.add(foreign_plan_item)
        session.commit()
        foreign_plan_id = int(foreign_plan_item.id)

    create_brief_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/plans/actions/create-brief",
        json={
            "plan_item_ids": [
                plan_ids["local seo pricing"],
                foreign_plan_id,
                9999,
            ],
        },
    )
    assert create_brief_response.status_code == 200
    create_brief_payload = create_brief_response.json()
    assert create_brief_payload["created_count"] == 1
    assert create_brief_payload["updated_count"] == 0
    assert create_brief_payload["skipped_count"] == 2
    assert create_brief_payload["items"][0]["primary_keyword"] == "local seo pricing"
    assert create_brief_payload["items"][0]["brief_type"] == "new_page"
    assert create_brief_payload["items"][0]["target_url_existing"] is None
    assert {item["reason"] for item in create_brief_payload["skipped"]} == {"wrong_site", "plan_not_found"}

    duplicate_brief_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/plans/actions/create-brief",
        json={
            "plan_item_ids": [plan_ids["local seo pricing"]],
        },
    )
    assert duplicate_brief_response.status_code == 200
    assert duplicate_brief_response.json()["skipped"] == [
        {
            "plan_item_id": plan_ids["local seo pricing"],
            "brief_title": "New page brief: Local SEO Pricing",
            "reason": "already_exists",
        }
    ]

    plans_after_brief_response = api_client.get(f"/sites/{site_id}/competitive-content-gap/semstorm/plans")
    assert plans_after_brief_response.status_code == 200
    plans_after_brief = plans_after_brief_response.json()["items"]
    local_pricing_plan = next(item for item in plans_after_brief if item["keyword"] == "local seo pricing")
    assert local_pricing_plan["has_brief"] is True
    assert local_pricing_plan["brief_id"] is not None
    brief_id = int(local_pricing_plan["brief_id"])

    list_response = api_client.get(f"/sites/{site_id}/competitive-content-gap/semstorm/briefs")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["summary"]["total_count"] == 1
    assert list_payload["summary"]["state_counts"]["draft"] == 1
    assert list_payload["items"][0]["id"] == brief_id

    detail_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}"
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["sections"][0] == "Introduction to Local SEO Pricing"
    assert detail_payload["internal_link_targets"] == ["https://example.com/seo-audit"]

    status_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/status",
        json={"state_status": "ready"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["state_status"] == "ready"

    update_response = api_client.put(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}",
        json={
            "brief_title": "Local SEO pricing execution brief",
            "brief_type": "cluster_support",
            "primary_keyword": "local seo pricing guide",
            "secondary_keywords": ["local seo pricing", "seo pricing guide"],
            "search_intent": "commercial",
            "target_url_existing": "https://example.com/content-strategy",
            "proposed_url_slug": "local-seo-pricing-guide",
            "recommended_page_title": "Local SEO Pricing Guide | Services and Next Steps",
            "recommended_h1": "Local SEO Pricing Guide",
            "content_goal": "Turn the pricing seed into a practical execution packet.",
            "angle_summary": "Use this as a lightweight cluster brief around local SEO pricing.",
            "sections": ["Pricing context", "Packages", "FAQs"],
            "internal_link_targets": ["https://example.com/content-strategy"],
            "source_notes": ["Source run: #1", "Coverage status: missing"],
        },
    )
    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["brief_title"] == "Local SEO pricing execution brief"
    assert update_payload["brief_type"] == "cluster_support"
    assert update_payload["search_intent"] == "commercial"

    filtered_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs",
        params={
            "state_status": "ready",
            "brief_type": "cluster_support",
            "search_intent": "commercial",
            "search": "execution",
        },
    )
    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert filtered_payload["summary"]["total_count"] == 1
    assert filtered_payload["summary"]["state_counts"]["ready"] == 1
    assert filtered_payload["summary"]["brief_type_counts"]["cluster_support"] == 1
    assert filtered_payload["summary"]["intent_counts"]["commercial"] == 1
    assert filtered_payload["items"][0]["id"] == brief_id


def test_semstorm_brief_execution_endpoints_support_transitions_metadata_and_filters(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    monkeypatch.setattr(semstorm_service, "SemstormApiClient", lambda: ApiPersistedSemstormClient())

    create_run_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs",
        json={
            "max_competitors": 2,
            "max_keywords_per_competitor": 3,
            "include_basic_stats": True,
        },
    )
    assert create_run_response.status_code == 201

    promote_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/promote",
        json={
            "run_id": 1,
            "keywords": ["seo audit"],
        },
    )
    assert promote_response.status_code == 200

    create_plan_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/promoted/actions/create-plan",
        json={
            "promoted_item_ids": [item["id"] for item in promote_response.json()["promoted_items"]],
        },
    )
    assert create_plan_response.status_code == 200
    plan_id = int(create_plan_response.json()["items"][0]["id"])

    create_brief_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/plans/actions/create-brief",
        json={"plan_item_ids": [plan_id]},
    )
    assert create_brief_response.status_code == 200
    brief_id = int(create_brief_response.json()["items"][0]["id"])

    execution_metadata_response = api_client.put(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/execution",
        json={
            "assignee": "Alice",
            "execution_note": "Ready for editorial handoff",
        },
    )
    assert execution_metadata_response.status_code == 200
    execution_metadata_payload = execution_metadata_response.json()
    assert execution_metadata_payload["assignee"] == "Alice"
    assert execution_metadata_payload["execution_note"] == "Ready for editorial handoff"
    assert execution_metadata_payload["execution_status"] == "draft"

    ready_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/execution-status",
        json={"execution_status": "ready"},
    )
    assert ready_response.status_code == 200
    assert ready_response.json()["execution_status"] == "ready"
    assert ready_response.json()["ready_at"] is not None

    start_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/execution-status",
        json={"execution_status": "in_execution"},
    )
    assert start_response.status_code == 200
    assert start_response.json()["execution_status"] == "in_execution"
    assert start_response.json()["started_at"] is not None

    complete_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/execution-status",
        json={"execution_status": "completed"},
    )
    assert complete_response.status_code == 200
    complete_payload = complete_response.json()
    assert complete_payload["execution_status"] == "completed"
    assert complete_payload["completed_at"] is not None
    assert complete_payload["decision_type_snapshot"] == "monitor_only"
    assert complete_payload["coverage_status_snapshot"] == "covered"

    execution_list_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/execution",
        params={
            "execution_status": "completed",
            "assignee": "ali",
            "brief_type": "refresh_existing",
            "search": "seo audit",
        },
    )
    assert execution_list_response.status_code == 200
    execution_list_payload = execution_list_response.json()
    assert execution_list_payload["summary"]["total_count"] == 1
    assert execution_list_payload["summary"]["execution_status_counts"]["completed"] == 1
    assert execution_list_payload["summary"]["completed_count"] == 1
    assert execution_list_payload["items"][0]["brief_id"] == brief_id
    assert execution_list_payload["items"][0]["assignee"] == "Alice"


def test_semstorm_brief_execution_status_endpoint_rejects_invalid_transition(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    monkeypatch.setattr(semstorm_service, "SemstormApiClient", lambda: ApiPersistedSemstormClient())

    create_run_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs",
        json={
            "max_competitors": 2,
            "max_keywords_per_competitor": 3,
            "include_basic_stats": True,
        },
    )
    assert create_run_response.status_code == 201

    promote_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/promote",
        json={
            "run_id": 1,
            "keywords": ["seo audit"],
        },
    )
    assert promote_response.status_code == 200

    create_plan_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/promoted/actions/create-plan",
        json={
            "promoted_item_ids": [item["id"] for item in promote_response.json()["promoted_items"]],
        },
    )
    assert create_plan_response.status_code == 200
    plan_id = int(create_plan_response.json()["items"][0]["id"])

    create_brief_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/plans/actions/create-brief",
        json={"plan_item_ids": [plan_id]},
    )
    assert create_brief_response.status_code == 200
    brief_id = int(create_brief_response.json()["items"][0]["id"])

    invalid_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/execution-status",
        json={"execution_status": "completed"},
    )
    assert invalid_response.status_code == 409
    assert "invalid semstorm brief execution transition" in invalid_response.json()["detail"].lower()


def test_semstorm_implemented_endpoints_mark_completed_briefs_and_return_outcome_payload(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    monkeypatch.setattr(semstorm_service, "SemstormApiClient", lambda: ApiPersistedSemstormClient())
    monkeypatch.setattr(semstorm_brief_service, "utcnow", lambda: FIXED_TIME + timedelta(days=5))

    _add_semstorm_gsc_top_query(
        sqlite_session_factory,
        site_id=site_id,
        crawl_job_id=ids["crawl_job_id"],
        page_id=ids["audit_page_id"],
        url="https://example.com/seo-audit",
        query="seo audit",
        clicks=19,
        impressions=210,
        ctr=0.09,
        position=4.2,
    )

    brief_id = _create_completed_semstorm_brief_via_api(api_client, site_id=site_id)

    implemented_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/implementation-status",
        json={
            "implementation_status": "implemented",
            "evaluation_note": "Published and ready for lightweight feedback.",
        },
    )
    assert implemented_response.status_code == 200
    implemented_payload = implemented_response.json()
    assert implemented_payload["implementation_status"] == "implemented"
    assert implemented_payload["implemented_at"] is not None

    monkeypatch.setattr(semstorm_brief_service, "utcnow", lambda: FIXED_TIME + timedelta(days=45))

    list_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/implemented",
        params={
            "implementation_status": "evaluated",
            "outcome_status": "positive_signal",
            "search": "seo audit",
            "window_days": 30,
        },
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["active_crawl_id"] == ids["crawl_job_id"]
    assert list_payload["window_days"] == 30
    assert list_payload["summary"]["total_count"] == 1
    assert list_payload["summary"]["implementation_status_counts"]["evaluated"] == 1
    assert list_payload["summary"]["outcome_status_counts"]["positive_signal"] == 1
    assert list_payload["summary"]["positive_signal_count"] == 1
    item = list_payload["items"][0]
    assert item["brief_id"] == brief_id
    assert item["implementation_status"] == "evaluated"
    assert item["outcome_status"] == "positive_signal"
    assert item["page_present_in_active_crawl"] is True
    assert item["matched_page"]["url"] == "https://example.com/seo-audit"
    assert item["gsc_signal_status"] == "present"
    assert item["gsc_summary"]["clicks"] == 19
    assert item["query_match_count"] >= 1


def test_semstorm_implementation_status_endpoint_rejects_non_completed_briefs_and_missing_brief(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    monkeypatch.setattr(semstorm_service, "SemstormApiClient", lambda: ApiPersistedSemstormClient())
    monkeypatch.setattr(semstorm_brief_service, "utcnow", lambda: FIXED_TIME + timedelta(days=5))

    create_run_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs",
        json={
            "max_competitors": 2,
            "max_keywords_per_competitor": 3,
            "include_basic_stats": True,
        },
    )
    assert create_run_response.status_code == 201

    promote_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/promote",
        json={
            "run_id": 1,
            "keywords": ["local seo pricing"],
        },
    )
    assert promote_response.status_code == 200

    create_plan_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/promoted/actions/create-plan",
        json={
            "promoted_item_ids": [item["id"] for item in promote_response.json()["promoted_items"]],
        },
    )
    assert create_plan_response.status_code == 200
    plan_id = int(create_plan_response.json()["items"][0]["id"])

    create_brief_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/plans/actions/create-brief",
        json={"plan_item_ids": [plan_id]},
    )
    assert create_brief_response.status_code == 200
    brief_id = int(create_brief_response.json()["items"][0]["id"])

    invalid_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/implementation-status",
        json={"implementation_status": "implemented"},
    )
    assert invalid_response.status_code == 409
    assert "only completed semstorm briefs" in invalid_response.json()["detail"].lower()

    missing_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/999999/implementation-status",
        json={"implementation_status": "implemented"},
    )
    assert missing_response.status_code == 404

    for next_status in ("ready", "in_execution", "completed"):
        transition_response = api_client.post(
            f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/execution-status",
            json={"execution_status": next_status},
        )
        assert transition_response.status_code == 200

    implemented_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/implementation-status",
        json={
            "implementation_status": "implemented",
            "implementation_url_override": "https://example.com/local-seo-pricing",
        },
    )
    assert implemented_response.status_code == 200

    too_early_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/implemented",
        params={
            "implementation_status": "too_early",
            "outcome_status": "too_early",
            "window_days": 30,
        },
    )
    assert too_early_response.status_code == 200
    too_early_payload = too_early_response.json()
    assert too_early_payload["summary"]["total_count"] == 1
    assert too_early_payload["summary"]["too_early_count"] == 1
    assert too_early_payload["items"][0]["brief_id"] == brief_id
    assert too_early_payload["items"][0]["page_present_in_active_crawl"] is False
    assert too_early_payload["items"][0]["gsc_signal_status"] == "none"


def test_semstorm_brief_enrichment_endpoints_support_enrich_list_and_apply(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    monkeypatch.setenv("SEMSTORM_BRIEF_ENGINE_MODE", "mock")
    monkeypatch.setenv("SEMSTORM_BRIEF_LLM_ENABLED", "false")
    monkeypatch.setattr(semstorm_service, "SemstormApiClient", lambda: ApiPersistedSemstormClient())

    create_run_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs",
        json={
            "max_competitors": 2,
            "max_keywords_per_competitor": 3,
            "include_basic_stats": True,
        },
    )
    assert create_run_response.status_code == 201

    promote_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/promote",
        json={
            "run_id": 1,
            "keywords": ["local seo pricing"],
        },
    )
    assert promote_response.status_code == 200

    create_plan_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/promoted/actions/create-plan",
        json={
            "promoted_item_ids": [item["id"] for item in promote_response.json()["promoted_items"]],
        },
    )
    assert create_plan_response.status_code == 200
    plan_id = int(create_plan_response.json()["items"][0]["id"])

    create_brief_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/plans/actions/create-brief",
        json={"plan_item_ids": [plan_id]},
    )
    assert create_brief_response.status_code == 200
    brief_id = int(create_brief_response.json()["items"][0]["id"])

    enrich_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/enrich"
    )
    assert enrich_response.status_code == 201
    enrich_payload = enrich_response.json()
    assert enrich_payload["status"] == "completed"
    assert enrich_payload["engine_mode"] == "mock"
    assert enrich_payload["suggestions"]["improved_brief_title"] == "Execution brief: Local SEO Pricing"
    enrichment_run_id = int(enrich_payload["id"])

    list_runs_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/enrichment-runs"
    )
    assert list_runs_response.status_code == 200
    list_runs_payload = list_runs_response.json()
    assert list_runs_payload["summary"] == {
        "total_count": 1,
        "completed_count": 1,
        "failed_count": 0,
        "applied_count": 0,
    }
    assert list_runs_payload["items"][0]["id"] == enrichment_run_id

    apply_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/enrichment-runs/{enrichment_run_id}/apply"
    )
    assert apply_response.status_code == 200
    apply_payload = apply_response.json()
    assert apply_payload["applied"] is True
    assert "brief_title" in apply_payload["applied_fields"]
    assert "recommended_page_title" in apply_payload["applied_fields"]
    assert apply_payload["brief"]["brief_title"] == "Execution brief: Local SEO Pricing"
    assert apply_payload["enrichment_run"]["is_applied"] is True

    second_apply_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/enrichment-runs/{enrichment_run_id}/apply"
    )
    assert second_apply_response.status_code == 200
    assert second_apply_response.json()["applied"] is False
    assert second_apply_response.json()["skipped_reason"] == "already_applied"


def test_semstorm_brief_enrich_endpoint_persists_failed_run_when_llm_mode_is_unavailable(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    monkeypatch.setenv("SEMSTORM_BRIEF_ENGINE_MODE", "llm")
    monkeypatch.setenv("SEMSTORM_BRIEF_LLM_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(semstorm_service, "SemstormApiClient", lambda: ApiPersistedSemstormClient())

    create_run_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/discovery-runs",
        json={
            "max_competitors": 2,
            "max_keywords_per_competitor": 3,
            "include_basic_stats": True,
        },
    )
    assert create_run_response.status_code == 201

    promote_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/opportunities/actions/promote",
        json={
            "run_id": 1,
            "keywords": ["local seo pricing"],
        },
    )
    assert promote_response.status_code == 200

    create_plan_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/promoted/actions/create-plan",
        json={
            "promoted_item_ids": [item["id"] for item in promote_response.json()["promoted_items"]],
        },
    )
    assert create_plan_response.status_code == 200
    plan_id = int(create_plan_response.json()["items"][0]["id"])

    create_brief_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/plans/actions/create-brief",
        json={"plan_item_ids": [plan_id]},
    )
    assert create_brief_response.status_code == 200
    brief_id = int(create_brief_response.json()["items"][0]["id"])

    enrich_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/enrich"
    )
    assert enrich_response.status_code == 503
    assert enrich_response.json() == {
        "detail": "Semstorm brief AI enrichment is disabled in backend config."
    }

    list_runs_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/semstorm/briefs/{brief_id}/enrichment-runs"
    )
    assert list_runs_response.status_code == 200
    list_runs_payload = list_runs_response.json()
    assert list_runs_payload["summary"]["failed_count"] == 1
    assert list_runs_payload["items"][0]["status"] == "failed"
    assert list_runs_payload["items"][0]["error_code"] == "llm_disabled"


def test_competitive_gap_endpoint_filters_and_returns_gap_keys(api_client, sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap",
        params={
            "sort_by": "priority_score",
            "sort_order": "desc",
            "priority_score_min": 30,
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["context"]["active_crawl_id"] == ids["crawl_job_id"]
    assert payload["context"]["data_readiness"]["gap_ready"] is True
    assert payload["context"]["empty_state_reason"] is None
    assert payload["summary"]["counts_by_type"]["NEW_TOPIC"] >= 1
    assert payload["total_items"] >= 3
    assert all(item["gap_key"] for item in payload["items"])
    assert all(item["semantic_cluster_key"] for item in payload["items"])
    assert all(item["canonical_topic_label"] for item in payload["items"])
    assert all(item["own_match_status"] for item in payload["items"])

    type_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap",
        params={"gap_type": "NEW_TOPIC"},
    )
    assert type_response.status_code == 200
    type_payload = type_response.json()
    assert type_payload["total_items"] >= 1
    assert all(item["gap_type"] == "NEW_TOPIC" for item in type_payload["items"])

    competitor_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap",
        params={"competitor_id": ids["competitor_a_id"], "sort_by": "topic_label", "sort_order": "asc"},
    )
    assert competitor_response.status_code == 200
    competitor_payload = competitor_response.json()
    assert competitor_payload["total_items"] >= 1
    assert all(ids["competitor_a_id"] in item["competitor_ids"] for item in competitor_payload["items"])

    topic_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap",
        params={"topic": "local seo"},
    )
    assert topic_response.status_code == 200
    topic_payload = topic_response.json()
    assert topic_payload["total_items"] >= 1
    assert all("local seo" in item["topic_label"].lower() or "local-seo" in item["topic_key"] for item in topic_payload["items"])

    own_match_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap",
        params={"own_match_status": "no_meaningful_match", "sort_by": "business_value_score", "sort_order": "desc"},
    )
    assert own_match_response.status_code == 200
    own_match_payload = own_match_response.json()
    assert own_match_payload["total_items"] >= 1
    assert all(item["own_match_status"] == "no_meaningful_match" for item in own_match_payload["items"])
    own_match_scores = [int(item["business_value_score"]) for item in own_match_payload["items"]]
    assert own_match_scores == sorted(own_match_scores, reverse=True)


def test_competitive_gap_csv_export_reuses_filtered_payload(api_client, sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    gap_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap",
        params={
            "gap_type": "NEW_TOPIC",
            "topic": "local seo",
            "own_match_status": "no_meaningful_match",
            "sort_by": "priority_score",
            "sort_order": "desc",
        },
    )
    assert gap_response.status_code == 200
    gap_payload = gap_response.json()

    response = api_client.get(
        f"/sites/{site_id}/export/competitive-content-gap.csv",
        params={
            "gap_type": "NEW_TOPIC",
            "topic": "local seo",
            "own_match_status": "no_meaningful_match",
            "sort_by": "priority_score",
            "sort_order": "desc",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "competitive_content_gap_view.csv" in response.headers["content-disposition"]

    content = response.text.lstrip("\ufeff")
    assert "gap_key" in content
    assert "semantic_cluster_key" in content
    assert "canonical_topic_label" in content
    assert "priority_score" in content
    assert "Local SEO" in content
    assert "EXPAND_EXISTING_TOPIC" not in content

    csv_rows = list(csv.DictReader(io.StringIO(content)))
    csv_gap_keys = [row["gap_key"] for row in csv_rows]
    api_gap_keys = [row["gap_key"] for row in gap_payload["items"]]
    assert csv_gap_keys == api_gap_keys


def test_competitive_gap_endpoint_prefers_reviewed_items_for_active_snapshot(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    monkeypatch.setenv("CONTENT_GAP_READ_MODEL_MODE", "hybrid")

    with sqlite_session_factory() as session:
        content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            site_id,
            basis_crawl_job_id=ids["crawl_job_id"],
        )
        run_payload = content_gap_review_run_service.queue_review_run(
            session,
            site_id=site_id,
            basis_crawl_job_id=ids["crawl_job_id"],
        )
        candidates = session.scalars(
            select(SiteContentGapCandidate)
            .where(
                SiteContentGapCandidate.site_id == site_id,
                SiteContentGapCandidate.basis_crawl_job_id == ids["crawl_job_id"],
                SiteContentGapCandidate.current.is_(True),
                SiteContentGapCandidate.status == "active",
            )
            .order_by(SiteContentGapCandidate.id.asc())
        ).all()
        content_gap_item_materialization_service.materialize_review_items(
            session,
            site_id=site_id,
            review_run_id=run_payload["id"],
            decisions=[
                content_gap_item_materialization_service.SanitizedContentGapDecision(
                    source_candidate_id=int(candidate.id),
                    decision_action="keep",
                    decision_reason_text=f"Keep {candidate.original_topic_label}.",
                    fit_score=84.0,
                    confidence=0.82,
                    reviewed_phrase=candidate.original_phrase,
                    reviewed_topic_label=candidate.original_topic_label,
                    reviewed_normalized_topic_key=candidate.normalized_topic_key,
                    reviewed_gap_type=candidate.gap_type,
                )
                for candidate in candidates
            ],
        )
        content_gap_review_run_service._complete_review_run_in_session(
            session,
            site_id=site_id,
            run_id=run_payload["run_id"],
            completed_batch_count=run_payload["batch_count"],
        )
        session.commit()

    response = api_client.get(f"/sites/{site_id}/competitive-content-gap")
    assert response.status_code == 200
    payload = response.json()
    assert payload["context"]["data_source_mode"] == "reviewed"
    assert payload["context"]["basis_crawl_job_id"] == ids["crawl_job_id"]
    assert payload["items"]
    assert all(item["decision_action"] == "keep" for item in payload["items"])


def test_content_gap_review_runs_endpoint_lists_recent_runs(api_client, sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    with sqlite_session_factory() as session:
        content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            site_id,
            basis_crawl_job_id=ids["crawl_job_id"],
        )
        first_run = content_gap_review_run_service.queue_review_run(
            session,
            site_id=site_id,
            basis_crawl_job_id=ids["crawl_job_id"],
        )
        content_gap_review_run_service._fail_review_run_in_session(
            session,
            site_id=site_id,
            run_id=first_run["run_id"],
            error_code="llm_error",
            error_message_safe="First review run failed.",
        )

        second_run = content_gap_review_run_service.queue_review_run(
            session,
            site_id=site_id,
            basis_crawl_job_id=ids["crawl_job_id"],
        )
        content_gap_review_run_service._complete_review_run_in_session(
            session,
            site_id=site_id,
            run_id=second_run["run_id"],
            completed_batch_count=second_run["batch_count"],
        )
        session.commit()

    response = api_client.get(f"/sites/{site_id}/competitive-content-gap/review-runs", params={"limit": 5})
    assert response.status_code == 200
    payload = response.json()

    assert len(payload) >= 2
    assert payload[0]["run_id"] == second_run["run_id"]
    assert payload[0]["status"] == "completed"
    assert payload[1]["run_id"] == first_run["run_id"]
    assert payload[1]["status"] == "failed"


def test_content_gap_review_run_retry_endpoint_queues_retry_for_current_snapshot(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    with sqlite_session_factory() as session:
        content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            site_id,
            basis_crawl_job_id=ids["crawl_job_id"],
        )
        failed_run = content_gap_review_run_service.queue_review_run(
            session,
            site_id=site_id,
            basis_crawl_job_id=ids["crawl_job_id"],
        )
        content_gap_review_run_service._fail_review_run_in_session(
            session,
            site_id=site_id,
            run_id=failed_run["run_id"],
            error_code="llm_error",
            error_message_safe="Failed review run.",
        )
        session.commit()

    executed: list[tuple[int, int]] = []

    def fake_execute_review_run_task(site_id_arg: int, run_id_arg: int, *, lease_owner: str = "content_gap_review_llm") -> None:
        executed.append((site_id_arg, run_id_arg))

    monkeypatch.setattr(
        "app.api.routes.site_competitive_gap.content_gap_review_llm_service.execute_review_run_task",
        fake_execute_review_run_task,
    )

    response = api_client.post(f"/sites/{site_id}/competitive-content-gap/review-runs/{failed_run['run_id']}/retry")
    assert response.status_code == 202
    payload = response.json()

    assert payload["status"] == "queued"
    assert payload["retry_of_run_id"] == failed_run["id"]
    assert payload["basis_crawl_job_id"] == ids["crawl_job_id"]
    assert executed == [(site_id, payload["run_id"])]


def test_content_gap_review_run_retry_endpoint_blocks_completed_and_outdated_runs(
    api_client,
    sqlite_session_factory,
) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    site_id = ids["site_id"]

    with sqlite_session_factory() as session:
        _add_candidate(
            session,
            site_id=site_id,
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="candidate-a",
            candidate_input_hash="hash-a",
            topic_key="local-seo",
            topic_label="Local SEO",
        )
        _add_candidate(
            session,
            site_id=site_id,
            basis_crawl_job_id=ids["crawl_b_id"],
            candidate_key="candidate-b",
            candidate_input_hash="hash-b",
            topic_key="seo-audit",
            topic_label="SEO Audit",
        )
        session.commit()

        completed_run = content_gap_review_run_service.queue_review_run(
            session,
            site_id=site_id,
            basis_crawl_job_id=ids["crawl_b_id"],
        )
        content_gap_review_run_service._complete_review_run_in_session(
            session,
            site_id=site_id,
            run_id=completed_run["run_id"],
            completed_batch_count=completed_run["batch_count"],
        )

        failed_old_snapshot_run = content_gap_review_run_service.queue_review_run(
            session,
            site_id=site_id,
            basis_crawl_job_id=ids["crawl_a_id"],
        )
        content_gap_review_run_service._fail_review_run_in_session(
            session,
            site_id=site_id,
            run_id=failed_old_snapshot_run["run_id"],
            error_code="llm_error",
            error_message_safe="Outdated snapshot run failed.",
        )
        session.commit()

    completed_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/review-runs/{completed_run['run_id']}/retry"
    )
    assert completed_response.status_code == 409
    assert "failed, stale, or cancelled" in completed_response.json()["detail"]

    outdated_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/review-runs/{failed_old_snapshot_run['run_id']}/retry"
    )
    assert outdated_response.status_code == 409
    assert "current active crawl snapshot" in outdated_response.json()["detail"].lower()


def test_strategy_normalization_uses_llm_when_enabled(api_client, sqlite_session_factory, monkeypatch) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("OPENAI_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_parse(
        self,
        *,
        model,
        system_prompt,
        user_prompt,
        response_format,
        max_completion_tokens,
        reasoning_effort=None,
        verbosity="low",
    ):
        assert model == "gpt-5-mini"
        assert "Polish" in system_prompt
        assert "Output language: pl" in user_prompt
        assert "Prompt version" in user_prompt
        assert response_format is NormalizedCompetitiveGapStrategy
        assert max_completion_tokens == 900
        assert reasoning_effort == "minimal"
        assert verbosity == "low"
        return NormalizedCompetitiveGapStrategy(
            business_summary="SEO consultancy focused on local growth.",
            target_audiences=["local businesses"],
            primary_goals=["lead generation", "local visibility"],
            priority_topics=["local seo", "seo audit"],
            supporting_topics=["google business profile"],
            priority_page_types=["service", "faq"],
            geographic_focus=["Warsaw"],
            constraints=["manual competitors only"],
            differentiation_points=["hands-on consulting"],
        )

    monkeypatch.setattr(
        "app.integrations.openai.client.OpenAiLlmClient.parse_chat_completion",
        fake_parse,
    )

    response = api_client.put(
        f"/sites/{site_id}/competitive-content-gap/strategy",
        json={"raw_user_input": "We want more local SEO leads and SEO audit demand in Warsaw."},
        headers={"X-UI-Language": "pl"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["normalization_status"] == "ready"
    assert payload["llm_provider"] == "openai"
    assert payload["llm_model"] == "gpt-5-mini"
    assert payload["prompt_version"] == STRATEGY_NORMALIZATION_PROMPT_VERSION
    assert payload["normalized_at"] is not None
    assert payload["last_normalization_attempt_at"] is not None
    assert payload["normalization_fallback_used"] is False
    assert payload["normalization_debug_code"] is None
    assert payload["normalization_debug_message"] == "Strategy normalized successfully."
    assert payload["normalized_strategy_json"]["priority_topics"] == ["local seo", "seo audit"]


def test_strategy_normalization_retries_with_higher_token_limit_after_length_limit(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("OPENAI_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    observed_limits: list[int] = []

    def fake_parse(
        self,
        *,
        model,
        system_prompt,
        user_prompt,
        response_format,
        max_completion_tokens,
        reasoning_effort=None,
        verbosity="low",
    ):
        observed_limits.append(max_completion_tokens)
        if max_completion_tokens == 900:
            raise OpenAiIntegrationError(
                "OpenAI response hit a length limit.",
                code="length_limit",
            )
        return NormalizedCompetitiveGapStrategy(
            business_summary="SEO consultancy focused on local growth.",
            target_audiences=["local businesses"],
            primary_goals=["lead generation"],
            priority_topics=["local seo"],
            supporting_topics=["google business profile"],
            priority_page_types=["service"],
            geographic_focus=["Warsaw"],
            constraints=[],
            differentiation_points=["hands-on consulting"],
        )

    monkeypatch.setattr(
        "app.integrations.openai.client.OpenAiLlmClient.parse_chat_completion",
        fake_parse,
    )

    response = api_client.put(
        f"/sites/{site_id}/competitive-content-gap/strategy",
        json={"raw_user_input": "We want more local SEO leads in Warsaw."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["normalization_status"] == "ready"
    assert observed_limits == [900, 1600]


def test_strategy_normalization_falls_back_cleanly_when_llm_disabled(api_client, sqlite_session_factory, monkeypatch) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("OPENAI_LLM_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = api_client.put(
        f"/sites/{site_id}/competitive-content-gap/strategy",
        json={"raw_user_input": "Need stronger local SEO and content strategy demand."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["normalization_status"] == "not_processed"
    assert payload["normalized_strategy_json"] is None
    assert payload["llm_provider"] is None
    assert payload["llm_model"] is None
    assert payload["last_normalization_attempt_at"] is not None
    assert payload["normalization_fallback_used"] is True
    assert payload["normalization_debug_code"] == "llm_disabled"
    assert "disabled" in payload["normalization_debug_message"].lower()


def test_strategy_normalization_exposes_provider_debug_when_llm_request_fails(api_client, sqlite_session_factory, monkeypatch) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("OPENAI_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_parse(
        self,
        *,
        model,
        system_prompt,
        user_prompt,
        response_format,
        max_completion_tokens,
        reasoning_effort=None,
        verbosity="low",
    ):
        raise OpenAiIntegrationError(
            "OpenAI request timed out.",
            code="timeout",
        )

    monkeypatch.setattr(
        "app.integrations.openai.client.OpenAiLlmClient.parse_chat_completion",
        fake_parse,
    )

    response = api_client.put(
        f"/sites/{site_id}/competitive-content-gap/strategy",
        json={"raw_user_input": "Need stronger local SEO and content strategy demand."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["normalization_status"] == "failed"
    assert payload["normalization_fallback_used"] is True
    assert payload["normalization_debug_code"] == "timeout"
    assert "timed out" in payload["normalization_debug_message"].lower()


def test_competitor_page_review_endpoint_exposes_accepted_and_rejected_records(
    api_client,
    sqlite_session_factory,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    competitor_id = ids["competitor_a_id"]

    with sqlite_session_factory() as session:
        rejected_page = session.scalars(
            select(SiteCompetitorPage)
            .where(SiteCompetitorPage.competitor_id == competitor_id)
            .order_by(SiteCompetitorPage.id.asc())
        ).first()
        assert rejected_page is not None
        extractions = session.scalars(
            select(SiteCompetitorPageExtraction)
            .where(SiteCompetitorPageExtraction.competitor_id == competitor_id)
            .order_by(SiteCompetitorPageExtraction.id.asc())
        ).all()
        for extraction in extractions:
            if extraction.competitor_page_id == rejected_page.id:
                continue
            extraction.semantic_card_json = build_semantic_card(
                primary_topic=extraction.topic_label or "Topic",
                topic_labels=[extraction.topic_label or "Topic"],
                core_problem=extraction.topic_label or "Topic",
                dominant_intent=extraction.search_intent or "commercial",
                secondary_intents=[],
                page_role=extraction.page_role or "money_page",
                content_format=extraction.content_format or "service_page",
                target_audience=None,
                entities=[],
                geo_scope=None,
                supporting_subtopics=[],
                what_this_page_is_about=extraction.topic_label or "Topic",
                what_this_page_is_not_about="Other topics.",
                commerciality="high",
                evidence_snippets=[],
                confidence=float(extraction.confidence or 0.8),
            )
            extraction.semantic_version = extraction.semantic_card_json["semantic_version"]
        rejected_page.semantic_eligible = False
        rejected_page.semantic_exclusion_reason = "non_indexable"
        rejected_page.fetch_diagnostics_json = {
            **build_fetch_diagnostics_payload(
                robots_meta="noindex,follow",
                schema_types=["Service"],
            ),
            "dominant_topic_strength": 0.22,
            "title_h1_alignment_score": 0.18,
            "meta_support_score": 0.14,
            "body_conflict_score": 0.73,
            "boilerplate_contamination_score": 0.61,
            "weak_evidence_flag": True,
            "weak_evidence_reason": "non_indexable",
        }
        rejected_page_id = rejected_page.id
        session.commit()

    response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/competitors/{competitor_id}/page-review",
        params={"review_status": "all", "page": 1, "page_size": 10},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["review_status"] == "all"
    assert payload["summary"]["accepted_pages"] == 2
    assert payload["summary"]["rejected_pages"] == 1
    assert payload["summary"]["current_extractions_count"] == 2
    assert payload["summary"]["counts_by_reason"]["accepted_with_extraction"] == 2
    assert payload["summary"]["counts_by_reason"]["non_indexable"] == 1

    rejected_record = next(item for item in payload["items"] if item["id"] == rejected_page_id)
    assert rejected_record["review_status"] == "rejected"
    assert rejected_record["review_reason_code"] == "non_indexable"
    assert rejected_record["has_current_extraction"] is False
    assert "Rejected before extraction" in rejected_record["review_reason_detail"]
    assert "robots_meta=noindex,follow" in rejected_record["review_reason_detail"]
    assert rejected_record["diagnostics"]["weak_evidence_flag"] is True

    rejected_only_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/competitors/{competitor_id}/page-review",
        params={"review_status": "rejected", "page": 1, "page_size": 10},
    )
    assert rejected_only_response.status_code == 200
    rejected_only_payload = rejected_only_response.json()
    assert rejected_only_payload["review_status"] == "rejected"
    assert rejected_only_payload["total_items"] == 1
    assert rejected_only_payload["items"][0]["id"] == rejected_page_id


def test_openai_client_extracts_safe_api_error_details() -> None:
    class DummyApiStatusError(Exception):
        body = {
            "error": {
                "code": "unsupported_value",
                "message": "Unsupported value: 'temperature' does not support 0 with this model.",
            }
        }

    code, message = _extract_api_error_details(DummyApiStatusError())
    assert code == "unsupported_value"
    assert "temperature" in message


def test_competitor_sync_endpoint_persists_pages_extractions_and_unblocks_gap(api_client, sqlite_session_factory, monkeypatch) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    create_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/competitors",
        json={
            "root_url": "https://competitor-sync.com",
            "label": "Competitor Sync",
            "is_active": True,
        },
    )
    assert create_response.status_code == 201
    competitor_id = create_response.json()["id"]

    html_map = {
        "https://competitor-sync.com/": competitive_gap_sync_service.FetchedCompetitorDocument(
            requested_url="https://competitor-sync.com/",
            final_url="https://competitor-sync.com/",
            normalized_url="https://competitor-sync.com/",
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
                body=(
                    """
                    <html><body>
                      <h1>Competitor Sync</h1>
                      <p>SEO consultancy homepage covering technical SEO, content strategy, local SEO, audits,
                      topical authority planning, internal linking, and recurring advisory work for in-house
                      teams in healthcare, SaaS, e-commerce, and multi-location service businesses.</p>
                      <p>We build service pages, hub pages, FAQs, and supporting articles that map to discovery,
                      evaluation, and conversion intent while improving information architecture and search visibility.</p>
                      <a href="/local-seo">Local SEO</a>
                      <a href="/faq/seo-audit">SEO Audit FAQ</a>
                    </body></html>
                    """
                ).encode("utf-8"),
            fetched_at=competitive_gap_sync_service.utcnow(),
            response_time_ms=120,
        ),
        "https://competitor-sync.com/local-seo": competitive_gap_sync_service.FetchedCompetitorDocument(
            requested_url="https://competitor-sync.com/local-seo",
            final_url="https://competitor-sync.com/local-seo",
            normalized_url="https://competitor-sync.com/local-seo",
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
                body=(
                    """
                    <html><head><title>Local SEO</title></head><body>
                      <h1>Local SEO</h1>
                      <p>Local SEO services for growing businesses include Google Business Profile optimization,
                      location page strategy, review acquisition, citation cleanup, internal linking, local content
                      planning, and conversion-focused service page updates.</p>
                      <p>We help brands improve map pack visibility, strengthen local trust signals, align landing
                      pages with city-level demand, and build supporting FAQ content that answers pricing, process,
                      implementation, and proof questions.</p>
                    </body></html>
                    """
                ).encode("utf-8"),
            fetched_at=competitive_gap_sync_service.utcnow(),
            response_time_ms=120,
        ),
        "https://competitor-sync.com/faq/seo-audit": competitive_gap_sync_service.FetchedCompetitorDocument(
            requested_url="https://competitor-sync.com/faq/seo-audit",
            final_url="https://competitor-sync.com/faq/seo-audit",
            normalized_url="https://competitor-sync.com/faq/seo-audit",
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
                body=(
                    """
                    <html><head><title>SEO Audit FAQ</title></head><body>
                      <h1>SEO Audit FAQ</h1>
                      <p>Answers about SEO audit process and deliverables explain timelines, scope, crawling depth,
                      technical validation, content review, internal linking analysis, stakeholder alignment, and
                      implementation planning for teams that need prioritized recommendations.</p>
                      <p>The FAQ covers pricing expectations, common blockers, handoff formats, and the difference
                      between a lightweight review and a full technical, content, and information architecture audit.</p>
                    </body></html>
                    """
                ).encode("utf-8"),
            fetched_at=competitive_gap_sync_service.utcnow(),
            response_time_ms=120,
        ),
    }

    monkeypatch.setattr(
        "app.services.competitive_gap_sync_service._fetch_competitor_document",
        lambda url: html_map.get(url),
    )
    monkeypatch.setattr(
        "app.services.competitive_gap_sync_service.SessionLocal",
        sqlite_session_factory,
    )
    monkeypatch.setattr(
        "app.services.competitive_gap_sync_run_service.SessionLocal",
        sqlite_session_factory,
    )
    monkeypatch.setattr(
        "app.services.competitive_gap_semantic_arbiter_service.SessionLocal",
        sqlite_session_factory,
    )
    monkeypatch.setattr(
        "app.services.competitive_gap_semantic_run_service.SessionLocal",
        sqlite_session_factory,
    )

    def _build_extraction_result(
        *,
        topic_label: str,
        topic_key: str,
        search_intent: str,
        content_format: str,
        page_role: str,
        evidence_snippets: list[str],
        confidence: float,
    ) -> CompetitorExtractionResult:
        return CompetitorExtractionResult(
            llm_provider="openai",
            llm_model="gpt-5-mini",
            prompt_version="competitive-gap-competitor-extraction-v2",
            schema_version="competitive_gap_competitor_extraction_v2",
            topic_label=topic_label,
            topic_key=topic_key,
            search_intent=search_intent,
            content_format=content_format,
            page_role=page_role,
            evidence_snippets_json=evidence_snippets,
            confidence=confidence,
            semantic_card_json=build_semantic_card(
                primary_topic=topic_label,
                topic_labels=[topic_label],
                core_problem=topic_label,
                dominant_intent=search_intent,
                secondary_intents=[],
                page_role=page_role,
                content_format=content_format,
                target_audience=None,
                entities=[],
                geo_scope=None,
                supporting_subtopics=[],
                what_this_page_is_about=evidence_snippets[0],
                what_this_page_is_not_about="Not another topic.",
                commerciality="high" if search_intent == "commercial" else "low",
                evidence_snippets=evidence_snippets,
                confidence=confidence,
            ),
        )

    def fake_extract(page):
        if page.normalized_url.endswith("/local-seo"):
            return _build_extraction_result(
                topic_label="Local SEO",
                topic_key="local-seo",
                search_intent="commercial",
                content_format="service_page",
                page_role="money_page",
                evidence_snippets=["Local SEO services for growing businesses."],
                confidence=0.86,
            )
        return _build_extraction_result(
            topic_label="SEO Audit",
            topic_key="seo-audit",
            search_intent="informational",
            content_format="faq",
            page_role="supporting_page",
            evidence_snippets=["Answers about SEO audit process and deliverables."],
            confidence=0.8,
        )

    monkeypatch.setattr(
        "app.services.competitive_gap_sync_service.competitive_gap_extraction_service.extract_competitor_page",
        fake_extract,
    )

    sync_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/competitors/{competitor_id}/sync",
    )
    assert sync_response.status_code == 202
    assert sync_response.json()["last_sync_status"] == "queued"
    assert sync_response.json()["last_sync_stage"] == "queued"
    assert sync_response.json()["last_sync_processed_urls"] == 0
    assert sync_response.json()["last_sync_progress_percent"] == 0
    assert sync_response.json()["last_sync_error_code"] is None
    assert sync_response.json()["last_sync_summary"]["visited_urls_count"] == 0

    competitors_response = api_client.get(f"/sites/{site_id}/competitive-content-gap/competitors")
    assert competitors_response.status_code == 200
    synced_competitor = next(item for item in competitors_response.json() if item["id"] == competitor_id)
    assert synced_competitor["last_sync_status"] == "done"
    assert synced_competitor["last_sync_stage"] == "done"
    assert synced_competitor["pages_count"] >= 2
    assert synced_competitor["extracted_pages_count"] >= 2
    assert synced_competitor["last_sync_started_at"] is not None
    assert synced_competitor["last_sync_finished_at"] is not None
    assert synced_competitor["last_sync_error"] is None
    assert synced_competitor["last_sync_error_code"] is None
    assert synced_competitor["last_sync_processed_urls"] >= 2
    assert synced_competitor["last_sync_url_limit"] == competitive_gap_sync_service.COMPETITOR_SYNC_MAX_URLS
    assert synced_competitor["last_sync_total_extractable_pages"] >= 2
    assert synced_competitor["last_sync_processed_extraction_pages"] >= 2
    assert synced_competitor["last_sync_progress_percent"] == 100
    assert synced_competitor["last_sync_summary"]["visited_urls_count"] >= 2
    assert synced_competitor["last_sync_summary"]["stored_pages_count"] >= 2
    assert synced_competitor["last_sync_summary"]["extracted_pages_count"] >= 2
    assert synced_competitor["semantic_status"] == "not_started"
    assert synced_competitor["last_semantic_run_started_at"] is None
    assert synced_competitor["last_semantic_run_finished_at"] is None
    assert synced_competitor["semantic_candidates_count"] >= 1
    assert synced_competitor["semantic_resolved_count"] == 0
    assert synced_competitor["semantic_analysis_mode"] == "not_started"
    assert synced_competitor["semantic_llm_merged_urls_count"] == 0
    assert synced_competitor["semantic_prompt_version"] is None

    gap_response = api_client.get(f"/sites/{site_id}/competitive-content-gap")
    assert gap_response.status_code == 200
    gap_payload = gap_response.json()
    assert gap_payload["total_items"] >= 1
    assert any(item["canonical_topic_label"] == "Local SEO" for item in gap_payload["items"])
    assert any(item["semantic_cluster_key"].startswith("sg:") for item in gap_payload["items"])

    with sqlite_session_factory() as session:
        competitor_pages = session.scalars(
            select(SiteCompetitorPage)
            .where(SiteCompetitorPage.competitor_id == competitor_id)
            .order_by(SiteCompetitorPage.id.asc())
        ).all()
        semantic_candidates = session.scalars(
            select(SiteCompetitorSemanticCandidate)
            .where(SiteCompetitorSemanticCandidate.competitor_id == competitor_id)
            .order_by(SiteCompetitorSemanticCandidate.id.asc())
        ).all()
        assert competitor_pages
        assert semantic_candidates
        assert any(page.semantic_eligible for page in competitor_pages)
        assert all(candidate.current for candidate in semantic_candidates)
        semantic_runs = session.scalars(
            select(SiteCompetitorSemanticRun)
            .where(SiteCompetitorSemanticRun.competitor_id == competitor_id)
            .order_by(SiteCompetitorSemanticRun.id.asc())
        ).all()
        semantic_decisions = session.scalars(
            select(SiteCompetitorSemanticDecision)
            .where(SiteCompetitorSemanticDecision.site_id == site_id)
            .order_by(SiteCompetitorSemanticDecision.id.asc())
        ).all()
        assert semantic_runs == []
        assert semantic_decisions == []


def test_competitor_sync_reset_endpoint_clears_runtime_state_without_removing_saved_data(
    api_client,
    sqlite_session_factory,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    competitor_id = ids["competitor_a_id"]

    reset_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/competitors/{competitor_id}/reset-sync",
    )
    assert reset_response.status_code == 200
    payload = reset_response.json()
    assert payload["id"] == competitor_id
    assert payload["last_sync_status"] == "idle"
    assert payload["last_sync_stage"] == "idle"
    assert payload["last_sync_started_at"] is None
    assert payload["last_sync_finished_at"] is None
    assert payload["last_sync_error_code"] is None
    assert payload["last_sync_error"] is None
    assert payload["last_sync_processed_urls"] == 0
    assert payload["last_sync_processed_extraction_pages"] == 0
    assert payload["last_sync_total_extractable_pages"] == 0
    assert payload["last_sync_progress_percent"] == 0
    assert payload["last_sync_summary"]["visited_urls_count"] == 0
    assert payload["pages_count"] >= 1
    assert payload["extracted_pages_count"] >= 1


def test_manual_semantic_rerun_endpoint_queues_runs_and_exposes_status_fields(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    with sqlite_session_factory() as session:
        for competitor_id in [ids["competitor_a_id"], ids["competitor_b_id"]]:
            pages = session.scalars(
                select(SiteCompetitorPage)
                .where(SiteCompetitorPage.competitor_id == competitor_id)
                .order_by(SiteCompetitorPage.id.asc())
            ).all()
            for page in pages:
                page.status_code = 200
                page.visible_text = (
                    (page.visible_text or page.title or page.h1 or "seo topic") + " "
                ) * 12
        session.commit()

    monkeypatch.setattr(
        "app.services.competitive_gap_semantic_arbiter_service.SessionLocal",
        sqlite_session_factory,
    )
    monkeypatch.setattr(
        "app.services.competitive_gap_semantic_run_service.SessionLocal",
        sqlite_session_factory,
    )
    monkeypatch.setenv("OPENAI_LLM_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/semantic/re-run",
        json={"mode": "full", "active_crawl_id": ids["crawl_job_id"]},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["mode"] == "full"
    assert payload["queued_count"] >= 1
    assert payload["queued_runs"]

    competitors_response = api_client.get(f"/sites/{site_id}/competitive-content-gap/competitors")
    assert competitors_response.status_code == 200
    competitors_payload = competitors_response.json()
    assert any(item["semantic_status"] in {"ready", "partial"} for item in competitors_payload)
    assert all(item["semantic_analysis_mode"] in {"not_started", "local_only", "llm_only", "mixed"} for item in competitors_payload)
    assert all("semantic_candidates_count" in item for item in competitors_payload)
    assert all("semantic_llm_merged_urls_count" in item for item in competitors_payload)
    assert all("semantic_prompt_version" in item for item in competitors_payload)

    with sqlite_session_factory() as session:
        semantic_runs = session.scalars(
            select(SiteCompetitorSemanticRun)
            .where(SiteCompetitorSemanticRun.site_id == site_id)
            .order_by(SiteCompetitorSemanticRun.id.asc())
        ).all()
        semantic_candidates = session.scalars(
            select(SiteCompetitorSemanticCandidate)
            .where(SiteCompetitorSemanticCandidate.site_id == site_id)
            .order_by(SiteCompetitorSemanticCandidate.id.asc())
        ).all()
        assert semantic_runs
        assert semantic_candidates
        assert all(run.status == "completed" for run in semantic_runs)

    get_settings.cache_clear()


def test_competitors_endpoint_prefers_last_displayable_semantic_run_after_empty_stale_retry(
    api_client,
    sqlite_session_factory,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    with sqlite_session_factory() as session:
        for competitor_id in [ids["competitor_a_id"], ids["competitor_b_id"]]:
            pages = session.scalars(
                select(SiteCompetitorPage)
                .where(SiteCompetitorPage.competitor_id == competitor_id)
                .order_by(SiteCompetitorPage.id.asc())
            ).all()
            for page in pages:
                page.status_code = 200
                page.visible_text = ((page.visible_text or page.title or page.h1 or "seo topic") + " ") * 12
            competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
                session,
                site_id,
                competitor_id,
                page_ids=[page.id for page in pages],
            )

        candidate_ids = session.scalars(
            select(SiteCompetitorSemanticCandidate.id)
            .where(
                SiteCompetitorSemanticCandidate.competitor_id == ids["competitor_a_id"],
                SiteCompetitorSemanticCandidate.current.is_(True),
            )
            .order_by(SiteCompetitorSemanticCandidate.id.asc())
        ).all()
        assert candidate_ids

        session.add(
            SiteCompetitorSemanticRun(
                site_id=site_id,
                competitor_id=ids["competitor_a_id"],
                run_id=1,
                status="completed",
                stage="completed",
                trigger_source="manual_full",
                mode="full",
                active_crawl_id=ids["crawl_job_id"],
                started_at=competitive_gap_sync_service.utcnow() - timedelta(minutes=10),
                finished_at=competitive_gap_sync_service.utcnow() - timedelta(minutes=8),
                last_heartbeat_at=competitive_gap_sync_service.utcnow() - timedelta(minutes=8),
                lease_expires_at=competitive_gap_sync_service.utcnow() - timedelta(minutes=8),
                llm_provider="openai",
                llm_model="gpt-5.4-mini",
                prompt_version="competitive-gap-semantic-arbiter-v1",
                source_candidate_ids_json=list(candidate_ids),
                summary_json={
                    "semantic_candidates_count": len(candidate_ids),
                    "semantic_llm_jobs_count": 3,
                    "semantic_resolved_count": len(candidate_ids),
                    "semantic_cache_hits": 5,
                    "semantic_fallback_count": 0,
                    "merge_pairs_count": 4,
                    "own_match_pairs_count": 6,
                },
            )
        )
        session.add(
            SiteCompetitorSemanticRun(
                site_id=site_id,
                competitor_id=ids["competitor_a_id"],
                run_id=2,
                status="stale",
                stage="stale",
                trigger_source="manual_full",
                mode="full",
                active_crawl_id=ids["crawl_job_id"],
                started_at=None,
                finished_at=competitive_gap_sync_service.utcnow() - timedelta(minutes=1),
                last_heartbeat_at=competitive_gap_sync_service.utcnow() - timedelta(minutes=1),
                lease_expires_at=competitive_gap_sync_service.utcnow() - timedelta(minutes=1),
                error_code=competitive_gap_semantic_run_service.STALE_RUN_ERROR_CODE,
                error_message_safe=competitive_gap_semantic_run_service.STALE_RUN_ERROR_MESSAGE,
                llm_provider="openai",
                llm_model="gpt-5.4-mini",
                prompt_version="competitive-gap-semantic-arbiter-v1",
                source_candidate_ids_json=list(candidate_ids),
                summary_json=competitive_gap_semantic_run_service.build_empty_semantic_summary_payload(),
            )
        )
        session.commit()

    response = api_client.get(f"/sites/{site_id}/competitive-content-gap/competitors")
    assert response.status_code == 200
    payload = next(item for item in response.json() if item["id"] == ids["competitor_a_id"])
    assert payload["semantic_status"] == "stale"
    assert payload["last_semantic_error"] == competitive_gap_semantic_run_service.STALE_RUN_ERROR_MESSAGE
    assert payload["last_semantic_run_started_at"] is not None
    assert payload["last_semantic_run_finished_at"] is not None
    assert payload["semantic_llm_jobs_count"] == 3
    assert payload["semantic_resolved_count"] == payload["semantic_candidates_count"]
    assert payload["semantic_progress_percent"] == 100
    assert payload["semantic_cache_hits"] == 5
    assert payload["semantic_fallback_count"] == 0
    assert payload["semantic_analysis_mode"] == "llm_only"
    assert payload["semantic_model"] == "gpt-5.4-mini"
    assert payload["semantic_prompt_version"] == "competitive-gap-semantic-arbiter-v1"


def test_competitors_endpoint_reports_incremental_semantic_progress_against_total_current_candidates(
    api_client,
    sqlite_session_factory,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    with sqlite_session_factory() as session:
        pages = session.scalars(
            select(SiteCompetitorPage)
            .where(SiteCompetitorPage.competitor_id == ids["competitor_a_id"])
            .order_by(SiteCompetitorPage.id.asc())
        ).all()
        for page in pages:
            page.status_code = 200
            page.visible_text = ((page.visible_text or page.title or page.h1 or "seo topic") + " ") * 12
        competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
            session,
            site_id,
            ids["competitor_a_id"],
            page_ids=[page.id for page in pages],
        )
        candidate_ids = session.scalars(
            select(SiteCompetitorSemanticCandidate.id)
            .where(
                SiteCompetitorSemanticCandidate.competitor_id == ids["competitor_a_id"],
                SiteCompetitorSemanticCandidate.current.is_(True),
            )
            .order_by(SiteCompetitorSemanticCandidate.id.asc())
        ).all()
        assert len(candidate_ids) == 3

        session.add(
            SiteCompetitorSemanticRun(
                site_id=site_id,
                competitor_id=ids["competitor_a_id"],
                run_id=1,
                status="completed",
                stage="completed",
                trigger_source="manual_incremental",
                mode="incremental",
                active_crawl_id=ids["crawl_job_id"],
                started_at=competitive_gap_sync_service.utcnow() - timedelta(minutes=5),
                finished_at=competitive_gap_sync_service.utcnow() - timedelta(minutes=4),
                last_heartbeat_at=competitive_gap_sync_service.utcnow() - timedelta(minutes=4),
                lease_expires_at=competitive_gap_sync_service.utcnow() - timedelta(minutes=4),
                llm_provider="openai",
                llm_model="gpt-5.4-mini",
                prompt_version="competitive-gap-semantic-arbiter-v1",
                source_candidate_ids_json=list(candidate_ids[:2]),
                summary_json={
                    "semantic_candidates_count": 2,
                    "semantic_llm_jobs_count": 1,
                    "semantic_resolved_count": 1,
                    "semantic_cache_hits": 6,
                    "semantic_fallback_count": 0,
                    "merge_pairs_count": 2,
                    "own_match_pairs_count": 2,
                },
            )
        )
        session.commit()

    response = api_client.get(f"/sites/{site_id}/competitive-content-gap/competitors")
    assert response.status_code == 200
    payload = next(item for item in response.json() if item["id"] == ids["competitor_a_id"])
    assert payload["semantic_candidates_count"] == 3
    assert payload["semantic_resolved_count"] == 1
    assert payload["semantic_progress_percent"] == 67


def test_competitor_sync_endpoint_returns_conflict_when_competitor_already_running(
    api_client,
    sqlite_session_factory,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    competitor_id = ids["competitor_a_id"]

    with sqlite_session_factory() as session:
        competitor = session.get(SiteCompetitor, competitor_id)
        assert competitor is not None
        competitor.last_sync_run_id = 1
        competitor.last_sync_status = "running"
        competitor.last_sync_stage = "crawling"
        session.add(
            SiteCompetitorSyncRun(
                site_id=site_id,
                competitor_id=competitor_id,
                run_id=1,
                status="running",
                stage="crawling",
                trigger_source="manual_single",
                started_at=competitive_gap_sync_service.utcnow(),
                last_heartbeat_at=competitive_gap_sync_service.utcnow(),
                lease_expires_at=competitive_gap_sync_service.utcnow()
                + timedelta(seconds=competitive_gap_sync_run_service.DEFAULT_SYNC_LEASE_SECONDS),
                summary_json=competitive_gap_sync_service.site_competitor_service.build_empty_sync_summary_payload(),
                processed_urls=0,
                url_limit=competitive_gap_sync_service.COMPETITOR_SYNC_MAX_URLS,
                processed_extraction_pages=0,
                total_extractable_pages=0,
            )
        )
        session.commit()

    response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/competitors/{competitor_id}/sync",
    )
    assert response.status_code == 409
    assert "already queued or running" in response.json()["detail"].lower()


def test_competitor_sync_runs_endpoint_lists_recent_runs(api_client, sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    competitor_id = ids["competitor_a_id"]

    with sqlite_session_factory() as session:
        session.add_all(
            [
                SiteCompetitorSyncRun(
                    site_id=site_id,
                    competitor_id=competitor_id,
                    run_id=1,
                    status="done",
                    stage="done",
                    trigger_source="manual_single",
                    started_at=competitive_gap_sync_service.utcnow(),
                    finished_at=competitive_gap_sync_service.utcnow(),
                    last_heartbeat_at=competitive_gap_sync_service.utcnow(),
                    lease_expires_at=competitive_gap_sync_service.utcnow(),
                    summary_json=competitive_gap_sync_service.site_competitor_service.build_empty_sync_summary_payload(),
                    processed_urls=8,
                    url_limit=competitive_gap_sync_service.COMPETITOR_SYNC_MAX_URLS,
                    processed_extraction_pages=3,
                    total_extractable_pages=3,
                ),
                SiteCompetitorSyncRun(
                    site_id=site_id,
                    competitor_id=competitor_id,
                    run_id=2,
                    status="failed",
                    stage="failed",
                    trigger_source="retry",
                    started_at=competitive_gap_sync_service.utcnow(),
                    finished_at=competitive_gap_sync_service.utcnow(),
                    last_heartbeat_at=competitive_gap_sync_service.utcnow(),
                    lease_expires_at=competitive_gap_sync_service.utcnow(),
                    error_code="timeout",
                    error_message_safe="OpenAI request timed out.",
                    summary_json=competitive_gap_sync_service.site_competitor_service.build_empty_sync_summary_payload(),
                    retry_of_run_id=1,
                    processed_urls=4,
                    url_limit=competitive_gap_sync_service.COMPETITOR_SYNC_MAX_URLS,
                    processed_extraction_pages=1,
                    total_extractable_pages=2,
                ),
            ]
        )
        session.commit()

    response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/competitors/{competitor_id}/sync-runs",
        params={"limit": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert [item["run_id"] for item in payload] == [2, 1]
    assert payload[0]["status"] == "failed"
    assert payload[0]["retry_of_run_id"] == 1


def test_retry_competitor_sync_endpoint_queues_new_retry_run(api_client, sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    competitor_id = ids["competitor_a_id"]

    with sqlite_session_factory() as session:
        competitor = session.get(SiteCompetitor, competitor_id)
        assert competitor is not None
        competitor.last_sync_run_id = 3
        competitor.last_sync_status = "failed"
        competitor.last_sync_stage = "failed"
        session.add(
            SiteCompetitorSyncRun(
                site_id=site_id,
                competitor_id=competitor_id,
                run_id=3,
                status="failed",
                stage="failed",
                trigger_source="manual_single",
                started_at=competitive_gap_sync_service.utcnow(),
                finished_at=competitive_gap_sync_service.utcnow(),
                last_heartbeat_at=competitive_gap_sync_service.utcnow(),
                lease_expires_at=competitive_gap_sync_service.utcnow(),
                error_code="timeout",
                error_message_safe="OpenAI request timed out.",
                summary_json=competitive_gap_sync_service.site_competitor_service.build_empty_sync_summary_payload(),
                processed_urls=4,
                url_limit=competitive_gap_sync_service.COMPETITOR_SYNC_MAX_URLS,
                processed_extraction_pages=1,
                total_extractable_pages=2,
            )
        )
        session.commit()

    from app.services import competitive_gap_sync_run_service as run_service_module
    from app.services import competitive_gap_sync_service as sync_service_module

    original_session_local = run_service_module.SessionLocal
    original_sync_session_local = sync_service_module.SessionLocal
    run_service_module.SessionLocal = sqlite_session_factory
    sync_service_module.SessionLocal = sqlite_session_factory
    response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/competitors/{competitor_id}/retry-sync",
    )
    try:
        assert response.status_code == 202
        payload = response.json()
        assert payload["last_sync_status"] == "queued"
        assert payload["last_sync_run_id"] == 4

        runs_response = api_client.get(
            f"/sites/{site_id}/competitive-content-gap/competitors/{competitor_id}/sync-runs",
            params={"limit": 5},
        )
        assert runs_response.status_code == 200
        runs = runs_response.json()
        assert runs[0]["run_id"] == 4
        assert runs[0]["trigger_source"] == "retry"
        assert runs[0]["retry_of_run_id"] == 3
    finally:
        run_service_module.SessionLocal = original_session_local
        sync_service_module.SessionLocal = original_sync_session_local


def test_list_competitors_reconciles_stale_running_run_after_restart(api_client, sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    competitor_id = ids["competitor_a_id"]

    with sqlite_session_factory() as session:
        competitor = session.get(SiteCompetitor, competitor_id)
        assert competitor is not None
        competitor.last_sync_run_id = 5
        competitor.last_sync_status = "running"
        competitor.last_sync_stage = "extracting"
        session.add(
            SiteCompetitorSyncRun(
                site_id=site_id,
                competitor_id=competitor_id,
                run_id=5,
                status="running",
                stage="extracting",
                trigger_source="manual_single",
                started_at=competitive_gap_sync_service.utcnow(),
                last_heartbeat_at=competitive_gap_sync_service.utcnow(),
                lease_expires_at=competitive_gap_sync_service.utcnow() - timedelta(seconds=1),
                summary_json=competitive_gap_sync_service.site_competitor_service.build_empty_sync_summary_payload(),
                processed_urls=6,
                url_limit=competitive_gap_sync_service.COMPETITOR_SYNC_MAX_URLS,
                processed_extraction_pages=2,
                total_extractable_pages=4,
            )
        )
        session.commit()

    response = api_client.get(f"/sites/{site_id}/competitive-content-gap/competitors")
    assert response.status_code == 200
    payload = next(item for item in response.json() if item["id"] == competitor_id)
    assert payload["last_sync_status"] == "failed"
    assert payload["last_sync_error_code"] == competitive_gap_sync_run_service.STALE_RUN_ERROR_CODE

    runs_response = api_client.get(
        f"/sites/{site_id}/competitive-content-gap/competitors/{competitor_id}/sync-runs",
        params={"limit": 5},
    )
    runs = runs_response.json()
    assert runs[0]["run_id"] == 5
    assert runs[0]["status"] == "stale"


def test_competitive_gap_explanation_endpoint_uses_llm_when_available(api_client, sqlite_session_factory, monkeypatch) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("OPENAI_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_parse(
        self,
        *,
        model,
        system_prompt,
        user_prompt,
        response_format,
        max_completion_tokens,
        reasoning_effort=None,
        verbosity="low",
    ):
        assert model == "gpt-5-mini"
        assert "Polish" in system_prompt
        assert "Output language: pl" in user_prompt
        assert response_format is CompetitiveGapExplanationOutput
        assert max_completion_tokens == 700
        assert reasoning_effort == "minimal"
        return CompetitiveGapExplanationOutput(
            explanation="Competitors repeatedly cover this topic while the site has no matching page.",
            bullets=[
                "Two competitors already address the topic.",
                "The current site has no matching coverage.",
            ],
        )

    monkeypatch.setattr(
        "app.integrations.openai.client.OpenAiLlmClient.parse_chat_completion",
        fake_parse,
    )

    gap_response = api_client.get(f"/sites/{site_id}/competitive-content-gap")
    assert gap_response.status_code == 200
    gap_payload = gap_response.json()
    target_row = next(item for item in gap_payload["items"] if item["gap_type"] == "NEW_TOPIC")
    gap_signature = build_competitive_gap_signature(target_row)

    explanation_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/explanation",
        json={
            "gap_key": target_row["gap_key"],
            "active_crawl_id": ids["crawl_job_id"],
            "gap_signature": gap_signature,
        },
        headers={"X-UI-Language": "pl"},
    )
    assert explanation_response.status_code == 200
    payload = explanation_response.json()
    assert payload["used_llm"] is True
    assert payload["fallback_used"] is False
    assert payload["prompt_version"] == GAP_EXPLANATION_PROMPT_VERSION
    assert payload["gap_signature"] == gap_signature


def test_competitive_gap_explanation_fallback_does_not_change_gap_payload(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]

    monkeypatch.setenv("OPENAI_LLM_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    before_response = api_client.get(f"/sites/{site_id}/competitive-content-gap")
    assert before_response.status_code == 200
    before_payload = before_response.json()
    target_row = next(item for item in before_payload["items"] if item["gap_type"] == "EXPAND_EXISTING_TOPIC")

    explanation_response = api_client.post(
        f"/sites/{site_id}/competitive-content-gap/explanation",
        json={
            "gap_key": target_row["gap_key"],
            "active_crawl_id": ids["crawl_job_id"],
        },
    )
    assert explanation_response.status_code == 200
    explanation_payload = explanation_response.json()
    assert explanation_payload["used_llm"] is False
    assert explanation_payload["fallback_used"] is True
    assert explanation_payload["explanation"]
    assert explanation_payload["bullets"]

    after_response = api_client.get(f"/sites/{site_id}/competitive-content-gap")
    assert after_response.status_code == 200
    assert after_response.json() == before_payload
