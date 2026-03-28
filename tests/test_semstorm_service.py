from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models import (
    CrawlJob,
    CrawlJobStatus,
    GscProperty,
    GscTopQuery,
    GscUrlMetric,
    Site,
    SiteSemstormCompetitor,
    SiteSemstormCompetitorQuery,
    SiteSemstormDiscoveryRun,
    SiteSemstormOpportunityState,
    SiteSemstormPromotedItem,
)
from app.services import semstorm_opportunity_state_service, semstorm_service
from tests.competitive_gap_test_utils import FIXED_TIME, seed_competitive_gap_site


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _seed_site(session_factory) -> int:
    with session_factory() as session:
        site = Site(root_url="https://www.example.com", domain="example.com")
        session.add(site)
        session.commit()
        return int(site.id)


def _seed_site_with_active_crawl_without_pages(session_factory) -> dict[str, int]:
    with session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com", created_at=FIXED_TIME)
        session.add(site)
        session.flush()

        crawl_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=FIXED_TIME,
            started_at=FIXED_TIME,
            finished_at=FIXED_TIME,
            settings_json={"start_url": "https://example.com"},
            stats_json={},
        )
        session.add(crawl_job)
        session.commit()
        return {
            "site_id": int(site.id),
            "crawl_job_id": int(crawl_job.id),
        }


def _add_gsc_top_query(
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


class PreviewSemstormClient:
    def __init__(self) -> None:
        self.keywords_calls: list[tuple[str, ...]] = []
        self.basic_stats_calls: list[tuple[str, ...]] = []

    def get_competitors(self, *, domains, result_type="organic", competitors_type="all", max_items=10):
        assert list(domains) == ["example.com"]
        assert result_type == "organic"
        assert competitors_type == "all"
        assert max_items == 2
        return [
            {"competitor": "example.com", "common_keywords": 999, "traffic": 999},
            {"competitor": "www.example.com", "common_keywords": 888, "traffic": 888},
            {"competitor": "competitor-a.com", "common_keywords": 32, "traffic": 120},
            {"competitor": "https://www.competitor-a.com/services", "common_keywords": 40, "traffic": 110},
            {"competitor": "blog.competitor-b.com", "common_keywords": 18, "traffic": 60},
        ]

    def get_keywords_basic_stats(self, *, domains, result_type="organic"):
        self.basic_stats_calls.append(tuple(domains))
        assert result_type == "organic"
        return {
            "competitor-a.com": {
                "keywords": "120",
                "keywords_top": 25,
                "traffic": "480",
                "traffic_potential": "700",
                "search_volume": "3200",
                "search_volume_top": "900",
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
        self.keywords_calls.append(tuple(domains))
        assert result_type == "organic"
        assert max_items == 2
        assert sorting == {"field": "traffic:0", "sort": "desc"}

        domain = domains[0]
        if domain == "competitor-a.com":
            return [
                {
                    "keyword": "seo audit checklist",
                    "position": {"competitor-a.com": 2},
                    "position_c": {"competitor-a.com": 3},
                    "url": {"competitor-a.com": "https://competitor-a.com/seo-audit-checklist"},
                    "traffic": {"competitor-a.com": 91},
                    "traffic_c": {"competitor-a.com": 12},
                    "volume": 1300,
                    "competitors": 8,
                    "cpc": 3.4,
                    "trends": "1,2,11",
                },
                {
                    "keyword": "technical seo audit",
                    "position": {"competitor-a.com": 4},
                    "position_c": {"competitor-a.com": -1},
                    "url": {"competitor-a.com": "https://competitor-a.com/technical-seo-audit"},
                    "traffic": {"competitor-a.com": 45},
                    "traffic_c": {"competitor-a.com": -4},
                    "volume": 900,
                    "competitors": 6,
                    "cpc": 2.1,
                    "trends": "",
                },
            ]
        if domain == "competitor-b.com":
            return [
                {
                    "keyword": "local seo pricing",
                    "position": {"competitor-b.com": 5},
                    "position_c": {"competitor-b.com": 1},
                    "url": {"competitor-b.com": "https://competitor-b.com/local-seo-pricing"},
                    "traffic": {"competitor-b.com": 33},
                    "traffic_c": {"competitor-b.com": 2},
                    "volume": 700,
                    "competitors": 7,
                    "cpc": 4.9,
                    "trends": [3, 4],
                }
            ]
        raise AssertionError(f"Unexpected domains call: {domains!r}")


class PersistedSemstormClient:
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


class FailIfCalledClient:
    def get_competitors(self, **kwargs):
        raise AssertionError("Semstorm client should not be called when integration is disabled.")


class DebugSemstormClient:
    provider_name = "semstorm"
    base_url = "https://api.semstorm.com/api-v3"
    services_token = "token-123"
    timeout_seconds = 60.0
    max_retries = 2
    retry_backoff_seconds = 1.0

    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[dict[str, object]] = []

    def get_competitors(self, *, domains, result_type="organic", competitors_type="all", max_items=10):
        self.calls.append(
            {
                "domains": list(domains),
                "result_type": result_type,
                "competitors_type": competitors_type,
                "max_items": max_items,
            }
        )
        if self.should_fail:
            raise semstorm_service.SemstormIntegrationError(
                "Unauthorized access.",
                code="provider_error",
                status_code=502,
            )
        return [{"competitor": "competitor-a.com", "common_keywords": 12, "traffic": 34}]


class OverflowSemstormClient:
    def get_competitors(self, *, domains, result_type="organic", competitors_type="all", max_items=10):
        assert list(domains) == ["example.com"]
        return [
            {"competitor": "facebook.com", "common_keywords": 151, "traffic": 285549609},
        ]

    def get_keywords_basic_stats(self, *, domains, result_type="organic"):
        return {
            "facebook.com": {
                "keywords": 16588695,
                "keywords_top": 6995488,
                "traffic": 285549609,
                "traffic_potential": 1018240524,
                "search_volume": 3259412690,
                "search_volume_top": 4294967295,
            }
        }

    def get_keywords(self, *, domains, result_type="organic", max_items=10, sorting=None):
        return [
            {
                "keyword": "facebook",
                "position": {"facebook.com": 1},
                "position_c": {"facebook.com": 0},
                "url": {"facebook.com": "https://facebook.com/?locale=pl_PL"},
                "traffic": {"facebook.com": 24897680},
                "traffic_c": {"facebook.com": 7528240},
                "volume": 55600000,
                "competitors": 7,
                "cpc": 0.16,
                "trends": "55600000,45500000,55600000",
            }
        ]


def test_build_semstorm_discovery_preview_normalizes_competitors_and_queries(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    site_id = _seed_site(sqlite_session_factory)
    fake_client = PreviewSemstormClient()
    monkeypatch.setenv("SEMSTORM_ENABLED", "true")

    with sqlite_session_factory() as session:
        payload = semstorm_service.build_semstorm_discovery_preview(
            session,
            site_id,
            max_competitors=2,
            max_keywords_per_competitor=2,
            result_type="organic",
            include_basic_stats=True,
            competitors_type="all",
            client=fake_client,
        )

    assert payload["site_id"] == site_id
    assert payload["source_domain"] == "example.com"
    assert payload["semstorm_enabled"] is True
    assert payload["include_basic_stats"] is True
    assert [item["domain"] for item in payload["competitors"]] == ["competitor-a.com", "competitor-b.com"]

    competitor_a = payload["competitors"][0]
    assert competitor_a["common_keywords"] == 40
    assert competitor_a["traffic"] == 110
    assert competitor_a["queries_count"] == 2
    assert competitor_a["basic_stats"]["traffic_potential"] == 700
    assert competitor_a["top_queries"][0] == {
        "keyword": "seo audit checklist",
        "position": 2,
        "position_change": 3,
        "url": "https://competitor-a.com/seo-audit-checklist",
        "traffic": 91,
        "traffic_change": 12,
        "volume": 1300,
        "competitors": 8,
        "cpc": 3.4,
        "trends": [1, 2, 11],
    }
    assert competitor_a["top_queries"][1]["trends"] == []

    competitor_b = payload["competitors"][1]
    assert competitor_b["common_keywords"] == 18
    assert competitor_b["basic_stats"]["keywords_top"] == 15
    assert competitor_b["top_queries"][0]["trends"] == [3, 4]

    assert fake_client.basic_stats_calls == [("competitor-a.com", "competitor-b.com")]
    assert fake_client.keywords_calls == [("competitor-a.com",), ("competitor-b.com",)]


def test_build_semstorm_discovery_preview_returns_empty_payload_when_disabled(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    site_id = _seed_site(sqlite_session_factory)
    monkeypatch.setenv("SEMSTORM_ENABLED", "false")

    with sqlite_session_factory() as session:
        payload = semstorm_service.build_semstorm_discovery_preview(
            session,
            site_id,
            client=FailIfCalledClient(),
        )

    assert payload == {
        "site_id": site_id,
        "source_domain": "example.com",
        "semstorm_enabled": False,
        "result_type": "organic",
        "competitors_type": "all",
        "include_basic_stats": False,
        "max_competitors": 5,
        "max_keywords_per_competitor": 10,
        "competitors": [],
    }


def test_debug_semstorm_connection_returns_request_details_and_provider_success(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    site_id = _seed_site(sqlite_session_factory)
    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    fake_client = DebugSemstormClient()

    with sqlite_session_factory() as session:
        payload = semstorm_service.debug_semstorm_connection(
            session,
            site_id,
            result_type="organic",
            competitors_type="all",
            client=fake_client,
        )

    assert payload["site_id"] == site_id
    assert payload["source_domain"] == "example.com"
    assert payload["semstorm_enabled"] is True
    assert payload["request"]["auth"] == {
        "mode": "query_param",
        "parameter_name": "services_token",
        "username_required": False,
    }
    assert payload["request"]["endpoint_path"] == "/explorer/explorer-competitors/get-data.json"
    assert payload["request"]["request_url"] == "https://api.semstorm.com/api-v3/explorer/explorer-competitors/get-data.json"
    assert payload["request"]["services_token_configured"] is True
    assert payload["request"]["request_payload_preview"] == {
        "domains": ["example.com"],
        "result_type": "organic",
        "pager": {"items_per_page": 10, "page": 0},
        "competitors_type": "all",
    }
    assert payload["provider_check"]["attempted"] is True
    assert payload["provider_check"]["ok"] is True
    assert payload["provider_check"]["result_count"] == 1
    assert payload["provider_check"]["response_shape"] == "list"
    assert isinstance(payload["provider_check"]["elapsed_ms"], int)
    assert fake_client.calls == [
        {
            "domains": ["example.com"],
            "result_type": "organic",
            "competitors_type": "all",
            "max_items": 1,
        }
    ]


def test_debug_semstorm_connection_captures_provider_error_without_raising(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    site_id = _seed_site(sqlite_session_factory)
    monkeypatch.setenv("SEMSTORM_ENABLED", "true")

    with sqlite_session_factory() as session:
        payload = semstorm_service.debug_semstorm_connection(
            session,
            site_id,
            client=DebugSemstormClient(should_fail=True),
        )

    assert payload["provider_check"] == {
        "attempted": True,
        "ok": False,
        "elapsed_ms": payload["provider_check"]["elapsed_ms"],
        "result_count": None,
        "response_shape": None,
        "error_code": "provider_error",
        "error_message_safe": "Unauthorized access.",
    }
    assert isinstance(payload["provider_check"]["elapsed_ms"], int)


def test_run_semstorm_discovery_persists_run_competitors_and_queries(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    site_id = _seed_site(sqlite_session_factory)
    monkeypatch.setenv("SEMSTORM_ENABLED", "true")

    with sqlite_session_factory() as session:
        payload = semstorm_service.run_semstorm_discovery(
            session,
            site_id,
            max_competitors=2,
            max_keywords_per_competitor=3,
            result_type="organic",
            include_basic_stats=True,
            competitors_type="all",
            client=PersistedSemstormClient(),
        )
        session.commit()

    assert payload["site_id"] == site_id
    assert payload["run_id"] == 1
    assert payload["status"] == "completed"
    assert payload["source_domain"] == "example.com"
    assert payload["summary"]["total_competitors"] == 2
    assert payload["summary"]["total_queries"] == 6
    assert payload["summary"]["unique_keywords"] == 3
    assert [item["domain"] for item in payload["competitors"]] == ["competitor-a.com", "competitor-b.com"]
    assert payload["competitors"][0]["queries_count"] == 3

    with sqlite_session_factory() as session:
        runs = list(session.scalars(select(SiteSemstormDiscoveryRun)))
        competitors = list(
            session.scalars(select(SiteSemstormCompetitor).order_by(SiteSemstormCompetitor.rank.asc()))
        )
        queries = list(session.scalars(select(SiteSemstormCompetitorQuery)))

    assert len(runs) == 1
    assert runs[0].status == "completed"
    assert runs[0].total_competitors == 2
    assert runs[0].total_queries == 6
    assert runs[0].unique_keywords == 3
    assert len(competitors) == 2
    assert [item.domain for item in competitors] == ["competitor-a.com", "competitor-b.com"]
    assert len(queries) == 6


def test_run_semstorm_discovery_clamps_large_metrics_to_postgres_integer_range(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    site_id = _seed_site(sqlite_session_factory)
    monkeypatch.setenv("SEMSTORM_ENABLED", "true")

    with sqlite_session_factory() as session:
        payload = semstorm_service.run_semstorm_discovery(
            session,
            site_id,
            max_competitors=1,
            max_keywords_per_competitor=1,
            include_basic_stats=True,
            client=OverflowSemstormClient(),
        )
        session.commit()

    competitor = payload["competitors"][0]
    assert competitor["basic_stats"]["search_volume"] == 2_147_483_647
    assert competitor["basic_stats"]["search_volume_top"] == 2_147_483_647

    with sqlite_session_factory() as session:
        stored_competitor = session.scalar(select(SiteSemstormCompetitor))
        stored_query = session.scalar(select(SiteSemstormCompetitorQuery))

    assert stored_competitor is not None
    assert stored_competitor.basic_stats_search_volume == 2_147_483_647
    assert stored_competitor.basic_stats_search_volume_top == 2_147_483_647
    assert stored_query is not None
    assert stored_query.volume == 55_600_000


def test_run_semstorm_discovery_marks_failed_run_when_disabled(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    site_id = _seed_site(sqlite_session_factory)
    monkeypatch.setenv("SEMSTORM_ENABLED", "false")

    with sqlite_session_factory() as session:
        with pytest.raises(semstorm_service.SemstormServiceError) as exc_info:
            semstorm_service.run_semstorm_discovery(
                session,
                site_id,
                client=FailIfCalledClient(),
            )
        session.commit()

    assert exc_info.value.code == "semstorm_disabled"
    assert exc_info.value.status_code == 503

    with sqlite_session_factory() as session:
        run = session.scalar(select(SiteSemstormDiscoveryRun))

    assert run is not None
    assert run.run_id == 1
    assert run.status == "failed"
    assert run.error_code == "semstorm_disabled"


def test_get_semstorm_opportunities_enriches_items_with_coverage_and_gsc(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    monkeypatch.setenv("SEMSTORM_ENABLED", "true")
    _add_gsc_top_query(
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

    with sqlite_session_factory() as session:
        semstorm_service.run_semstorm_discovery(
            session,
            site_id,
            max_competitors=2,
            max_keywords_per_competitor=3,
            result_type="organic",
            include_basic_stats=True,
            competitors_type="all",
            client=PersistedSemstormClient(),
        )
        session.commit()

    with sqlite_session_factory() as session:
        payload = semstorm_service.get_semstorm_opportunities(session, site_id)

    assert payload["run_id"] == 1
    assert payload["active_crawl_id"] == ids["crawl_job_id"]
    assert payload["summary"]["total_items"] == 3
    assert payload["summary"]["bucket_counts"] == {
        "quick_win": 1,
        "core_opportunity": 1,
        "watchlist": 1,
    }
    assert payload["summary"]["decision_type_counts"] == {
        "create_new_page": 1,
        "expand_existing_page": 1,
        "monitor_only": 1,
    }
    assert payload["summary"]["coverage_status_counts"] == {
        "missing": 1,
        "weak_coverage": 1,
        "covered": 1,
    }
    assert payload["summary"]["state_counts"] == {
        "new": 3,
        "accepted": 0,
        "dismissed": 0,
        "promoted": 0,
    }

    by_keyword = {item["keyword"]: item for item in payload["items"]}

    assert by_keyword["seo audit"]["coverage_status"] == "covered"
    assert by_keyword["seo audit"]["decision_type"] == "monitor_only"
    assert by_keyword["seo audit"]["bucket"] == "core_opportunity"
    assert by_keyword["seo audit"]["best_match_page"]["page_id"] == ids["audit_page_id"]
    assert "title_exact" in by_keyword["seo audit"]["best_match_page"]["match_signals"]
    assert by_keyword["seo audit"]["gsc_signal_status"] == "present"
    assert by_keyword["seo audit"]["gsc_summary"]["clicks"] == 19
    assert by_keyword["seo audit"]["opportunity_score_v2"] < by_keyword["seo audit"]["opportunity_score_v1"]

    assert by_keyword["content strategy template"]["coverage_status"] == "weak_coverage"
    assert by_keyword["content strategy template"]["decision_type"] == "expand_existing_page"
    assert by_keyword["content strategy template"]["bucket"] == "quick_win"
    assert by_keyword["content strategy template"]["matched_pages_count"] == 1
    assert by_keyword["content strategy template"]["best_match_page"]["page_id"] == ids["content_strategy_page_id"]
    assert by_keyword["content strategy template"]["gsc_signal_status"] == "weak"
    assert by_keyword["content strategy template"]["gsc_summary"]["clicks"] == 11
    assert (
        by_keyword["content strategy template"]["opportunity_score_v2"]
        > by_keyword["content strategy template"]["opportunity_score_v1"]
    )

    assert by_keyword["local seo pricing"]["competitor_count"] == 2
    assert by_keyword["local seo pricing"]["bucket"] == "watchlist"
    assert by_keyword["local seo pricing"]["coverage_status"] == "missing"
    assert by_keyword["local seo pricing"]["decision_type"] == "create_new_page"
    assert by_keyword["local seo pricing"]["matched_pages_count"] == 0
    assert by_keyword["local seo pricing"]["best_match_page"] is None
    assert by_keyword["local seo pricing"]["gsc_signal_status"] == "none"
    assert by_keyword["local seo pricing"]["gsc_summary"] is None
    assert by_keyword["local seo pricing"]["opportunity_score_v2"] > by_keyword["local seo pricing"]["opportunity_score_v1"]


def test_get_semstorm_opportunities_returns_none_gsc_when_active_crawl_has_no_gsc_import(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    monkeypatch.setenv("SEMSTORM_ENABLED", "true")

    with sqlite_session_factory() as session:
        session.execute(delete(GscUrlMetric).where(GscUrlMetric.crawl_job_id == ids["crawl_job_id"]))
        session.execute(delete(GscTopQuery).where(GscTopQuery.crawl_job_id == ids["crawl_job_id"]))
        session.commit()

    with sqlite_session_factory() as session:
        semstorm_service.run_semstorm_discovery(
            session,
            site_id,
            max_competitors=2,
            max_keywords_per_competitor=3,
            include_basic_stats=True,
            client=PersistedSemstormClient(),
        )
        session.commit()

    with sqlite_session_factory() as session:
        payload = semstorm_service.get_semstorm_opportunities(session, site_id)

    assert payload["active_crawl_id"] == ids["crawl_job_id"]
    assert all(item["gsc_signal_status"] == "none" for item in payload["items"])
    assert all(item["gsc_summary"] is None for item in payload["items"])
    assert payload["summary"]["state_counts"]["new"] == 3


def test_get_semstorm_opportunities_handles_site_without_active_crawl(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    site_id = _seed_site(sqlite_session_factory)
    monkeypatch.setenv("SEMSTORM_ENABLED", "true")

    with sqlite_session_factory() as session:
        semstorm_service.run_semstorm_discovery(
            session,
            site_id,
            max_competitors=2,
            max_keywords_per_competitor=3,
            include_basic_stats=True,
            client=PersistedSemstormClient(),
        )
        session.commit()

    with sqlite_session_factory() as session:
        payload = semstorm_service.get_semstorm_opportunities(session, site_id)

    assert payload["active_crawl_id"] is None
    assert payload["summary"]["coverage_status_counts"] == {
        "missing": 3,
        "weak_coverage": 0,
        "covered": 0,
    }
    for item in payload["items"]:
        assert item["coverage_status"] == "missing"
        assert item["matched_pages_count"] == 0
        assert item["best_match_page"] is None
        assert item["gsc_signal_status"] == "none"
        assert item["gsc_summary"] is None


def test_get_semstorm_opportunities_handles_active_crawl_without_pages(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_site_with_active_crawl_without_pages(sqlite_session_factory)
    site_id = ids["site_id"]
    monkeypatch.setenv("SEMSTORM_ENABLED", "true")

    with sqlite_session_factory() as session:
        semstorm_service.run_semstorm_discovery(
            session,
            site_id,
            max_competitors=2,
            max_keywords_per_competitor=3,
            include_basic_stats=True,
            client=PersistedSemstormClient(),
        )
        session.commit()

    with sqlite_session_factory() as session:
        payload = semstorm_service.get_semstorm_opportunities(session, site_id)

    assert payload["active_crawl_id"] == ids["crawl_job_id"]
    assert all(item["coverage_status"] == "missing" for item in payload["items"])
    assert all(item["matched_pages_count"] == 0 for item in payload["items"])
    assert all(item["best_match_page"] is None for item in payload["items"])


def test_get_semstorm_opportunities_raises_when_no_completed_run(sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        with pytest.raises(semstorm_service.SemstormServiceError) as exc_info:
            semstorm_service.get_semstorm_opportunities(session, site_id)

    assert exc_info.value.code == "not_found"
    assert exc_info.value.status_code == 404


def test_get_semstorm_opportunities_maps_persisted_state_and_filters_actionable(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    monkeypatch.setenv("SEMSTORM_ENABLED", "true")

    with sqlite_session_factory() as session:
        semstorm_service.run_semstorm_discovery(
            session,
            site_id,
            max_competitors=2,
            max_keywords_per_competitor=3,
            include_basic_stats=True,
            client=PersistedSemstormClient(),
        )
        semstorm_service.accept_semstorm_opportunities(
            session,
            site_id,
            run_id=1,
            keywords=["seo audit"],
            note="Keep for planning",
        )
        semstorm_service.dismiss_semstorm_opportunities(
            session,
            site_id,
            run_id=1,
            keywords=["local seo pricing"],
            note="Out of scope",
        )
        session.commit()

    with sqlite_session_factory() as session:
        payload = semstorm_service.get_semstorm_opportunities(session, site_id)
        actionable = semstorm_service.get_semstorm_opportunities(session, site_id, only_actionable=True)
        accepted_only = semstorm_service.get_semstorm_opportunities(
            session,
            site_id,
            state_status="accepted",
        )

    assert payload["summary"]["state_counts"] == {
        "new": 1,
        "accepted": 1,
        "dismissed": 1,
        "promoted": 0,
    }
    by_keyword = {item["keyword"]: item for item in payload["items"]}
    assert by_keyword["seo audit"]["state_status"] == "accepted"
    assert by_keyword["seo audit"]["state_note"] == "Keep for planning"
    assert by_keyword["seo audit"]["can_accept"] is False
    assert by_keyword["seo audit"]["can_promote"] is True
    assert by_keyword["local seo pricing"]["state_status"] == "dismissed"
    assert by_keyword["local seo pricing"]["can_dismiss"] is False
    assert {item["keyword"] for item in actionable["items"]} == {
        "seo audit",
        "content strategy template",
    }
    assert [item["keyword"] for item in accepted_only["items"]] == ["seo audit"]


def test_promote_semstorm_opportunities_persists_backlog_and_skips_duplicates(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    site_id = ids["site_id"]
    monkeypatch.setenv("SEMSTORM_ENABLED", "true")

    with sqlite_session_factory() as session:
        semstorm_service.run_semstorm_discovery(
            session,
            site_id,
            max_competitors=2,
            max_keywords_per_competitor=3,
            include_basic_stats=True,
            client=PersistedSemstormClient(),
        )
        first_response = semstorm_service.promote_semstorm_opportunities(
            session,
            site_id,
            run_id=1,
            keywords=["content strategy template", "missing keyword"],
            note="Promote to backlog",
        )
        second_response = semstorm_service.promote_semstorm_opportunities(
            session,
            site_id,
            run_id=1,
            keywords=["content strategy template"],
            note="Promote again",
        )
        promoted_payload = semstorm_service.list_semstorm_promoted_items(session, site_id)
        opportunities_payload = semstorm_service.get_semstorm_opportunities(session, site_id)
        session.commit()

    assert first_response["updated_count"] == 1
    assert first_response["promoted_count"] == 1
    assert first_response["promoted_items"][0]["keyword"] == "content strategy template"
    assert first_response["promoted_items"][0]["source_run_id"] == 1
    assert first_response["skipped"] == [{"keyword": "missing keyword", "reason": "keyword_not_in_run"}]

    assert second_response["updated_count"] == 0
    assert second_response["promoted_count"] == 0
    assert second_response["skipped"] == [
        {"keyword": "content strategy template", "reason": "already_promoted"}
    ]

    assert promoted_payload["summary"]["total_items"] == 1
    assert promoted_payload["summary"]["promotion_status_counts"] == {"active": 1, "archived": 0}
    assert promoted_payload["items"][0]["keyword"] == "content strategy template"
    assert promoted_payload["items"][0]["coverage_status"] == "weak_coverage"

    by_keyword = {item["keyword"]: item for item in opportunities_payload["items"]}
    assert by_keyword["content strategy template"]["state_status"] == "promoted"
    assert by_keyword["content strategy template"]["can_promote"] is False
    assert opportunities_payload["summary"]["state_counts"] == {
        "new": 2,
        "accepted": 0,
        "dismissed": 0,
        "promoted": 1,
    }

    with sqlite_session_factory() as session:
        states = list(session.scalars(select(SiteSemstormOpportunityState)))
        promoted_rows = list(session.scalars(select(SiteSemstormPromotedItem)))

    assert len(states) == 1
    assert states[0].normalized_keyword == "content strategy template"
    assert states[0].state_status == "promoted"
    assert len(promoted_rows) == 1
    assert promoted_rows[0].normalized_keyword == "content strategy template"
