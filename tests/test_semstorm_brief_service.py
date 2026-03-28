from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models import GscProperty, GscTopQuery, Page
from app.services import semstorm_brief_service, semstorm_plan_service, semstorm_service
from tests.competitive_gap_test_utils import FIXED_TIME, seed_competitive_gap_site
from tests.test_semstorm_service import PersistedSemstormClient


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _seed_plan_items(session_factory, monkeypatch) -> dict[str, int]:
    ids = seed_competitive_gap_site(session_factory)
    monkeypatch.setenv("SEMSTORM_ENABLED", "true")

    with session_factory() as session:
        semstorm_service.run_semstorm_discovery(
            session,
            ids["site_id"],
            max_competitors=2,
            max_keywords_per_competitor=3,
            include_basic_stats=True,
            client=PersistedSemstormClient(),
        )
        semstorm_service.promote_semstorm_opportunities(
            session,
            ids["site_id"],
            run_id=1,
            keywords=["seo audit", "local seo pricing"],
            note="Promote for brief planning",
        )
        promoted = semstorm_service.list_semstorm_promoted_items(session, ids["site_id"])
        promoted_ids = {item["keyword"]: int(item["id"]) for item in promoted["items"]}
        created = semstorm_plan_service.create_semstorm_plan_items(
            session,
            ids["site_id"],
            promoted_item_ids=[
                promoted_ids["seo audit"],
                promoted_ids["local seo pricing"],
            ],
        )
        session.commit()

    plan_ids = {item["keyword"]: int(item["id"]) for item in created["items"]}
    ids["seo_audit_plan_id"] = plan_ids["seo audit"]
    ids["local_seo_pricing_plan_id"] = plan_ids["local seo pricing"]
    return ids


def _seed_brief_items(session_factory, monkeypatch) -> dict[str, int]:
    ids = _seed_plan_items(session_factory, monkeypatch)
    with session_factory() as session:
        created = semstorm_brief_service.create_semstorm_brief_items(
            session,
            ids["site_id"],
            plan_item_ids=[ids["seo_audit_plan_id"], ids["local_seo_pricing_plan_id"]],
        )
        session.commit()

    brief_ids = {item["primary_keyword"]: int(item["id"]) for item in created["items"]}
    ids["seo_audit_brief_id"] = brief_ids["seo audit"]
    ids["local_seo_pricing_brief_id"] = brief_ids["local seo pricing"]
    return ids


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


def test_create_brief_items_builds_scaffold_and_is_idempotent(sqlite_session_factory, monkeypatch) -> None:
    ids = _seed_plan_items(sqlite_session_factory, monkeypatch)

    with sqlite_session_factory() as session:
        first = semstorm_brief_service.create_semstorm_brief_items(
            session,
            ids["site_id"],
            plan_item_ids=[
                ids["seo_audit_plan_id"],
                ids["local_seo_pricing_plan_id"],
                9999,
            ],
        )
        second = semstorm_brief_service.create_semstorm_brief_items(
            session,
            ids["site_id"],
            plan_item_ids=[ids["seo_audit_plan_id"]],
        )
        plans = semstorm_plan_service.list_semstorm_plan_items(session, ids["site_id"])
        session.commit()

    assert first["created_count"] == 2
    assert first["updated_count"] == 0
    assert first["skipped_count"] == 1
    assert first["skipped"] == [
        {
            "plan_item_id": 9999,
            "brief_title": None,
            "reason": "plan_not_found",
        }
    ]

    by_keyword = {item["primary_keyword"]: item for item in first["items"]}

    seo_audit = by_keyword["seo audit"]
    assert seo_audit["brief_type"] == "refresh_existing"
    assert seo_audit["target_url_existing"] == "https://example.com/seo-audit"
    assert seo_audit["recommended_page_title"] == "SEO Audit | SEO Audit"
    assert seo_audit["recommended_h1"] == "SEO Audit"
    assert seo_audit["sections"][0] == "What needs updating"
    assert seo_audit["internal_link_targets"][0] == "https://example.com/seo-audit"
    assert any("Coverage status: covered" in note for note in seo_audit["source_notes"])

    local_pricing = by_keyword["local seo pricing"]
    assert local_pricing["brief_type"] == "new_page"
    assert local_pricing["target_url_existing"] is None
    assert local_pricing["proposed_url_slug"] == "local-seo-pricing"
    assert local_pricing["search_intent"] == "transactional"
    assert local_pricing["recommended_page_title"] == "Local SEO Pricing | Pricing and Options"
    assert local_pricing["sections"][0] == "Introduction to Local SEO Pricing"
    assert any("Coverage status: missing" in note for note in local_pricing["source_notes"])

    assert second["created_count"] == 0
    assert second["skipped_count"] == 1
    assert second["skipped"][0]["reason"] == "already_exists"

    plans_by_id = {int(item["id"]): item for item in plans["items"]}
    assert plans_by_id[ids["seo_audit_plan_id"]]["has_brief"] is True
    assert plans_by_id[ids["seo_audit_plan_id"]]["brief_id"] is not None


def test_brief_items_support_detail_update_status_and_filters(sqlite_session_factory, monkeypatch) -> None:
    ids = _seed_plan_items(sqlite_session_factory, monkeypatch)

    with sqlite_session_factory() as session:
        created = semstorm_brief_service.create_semstorm_brief_items(
            session,
            ids["site_id"],
            plan_item_ids=[ids["local_seo_pricing_plan_id"]],
        )
        brief_id = int(created["items"][0]["id"])

        updated = semstorm_brief_service.update_semstorm_brief_item(
            session,
            ids["site_id"],
            brief_id,
            updates={
                "brief_title": "Pricing brief for local SEO",
                "brief_type": "cluster_support",
                "primary_keyword": "local seo pricing guide",
                "secondary_keywords": ["local seo pricing", "seo pricing guide"],
                "search_intent": "commercial",
                "target_url_existing": "https://example.com/content-strategy",
                "proposed_url_slug": "local-seo-pricing-guide",
                "recommended_page_title": "Local SEO Pricing Guide | Services and Next Steps",
                "recommended_h1": "Local SEO Pricing Guide",
                "content_goal": "Give the sales team a practical pricing page scaffold.",
                "angle_summary": "Support the main local SEO service page with a pricing-focused cluster brief.",
                "sections": ["Pricing context", "Packages", "FAQs"],
                "internal_link_targets": [
                    "https://example.com/content-strategy",
                    "https://example.com/seo-audit",
                ],
                "source_notes": ["Source run: #1", "Coverage status: missing"],
            },
        )
        status_updated = semstorm_brief_service.update_semstorm_brief_item_status(
            session,
            ids["site_id"],
            brief_id,
            state_status="ready",
        )
        detail = semstorm_brief_service.get_semstorm_brief_item(session, ids["site_id"], brief_id)
        filtered = semstorm_brief_service.list_semstorm_brief_items(
            session,
            ids["site_id"],
            state_status="ready",
            brief_type="cluster_support",
            search_intent="commercial",
            search="pricing brief",
        )
        session.commit()

    assert updated["brief_title"] == "Pricing brief for local SEO"
    assert updated["brief_type"] == "cluster_support"
    assert updated["primary_keyword"] == "local seo pricing guide"
    assert updated["secondary_keywords"] == ["local seo pricing", "seo pricing guide"]
    assert updated["sections"] == ["Pricing context", "Packages", "FAQs"]
    assert status_updated["state_status"] == "ready"
    assert status_updated["execution_status"] == "ready"
    assert status_updated["ready_at"] is not None
    assert detail["target_url_existing"] == "https://example.com/content-strategy"
    assert detail["internal_link_targets"] == [
        "https://example.com/content-strategy",
        "https://example.com/seo-audit",
    ]
    assert filtered["summary"]["total_count"] == 1
    assert filtered["summary"]["state_counts"]["ready"] == 1
    assert filtered["summary"]["brief_type_counts"]["cluster_support"] == 1
    assert filtered["summary"]["intent_counts"]["commercial"] == 1
    assert filtered["items"][0]["id"] == brief_id


def test_brief_execution_transitions_and_execution_read_model(sqlite_session_factory, monkeypatch) -> None:
    ids = _seed_plan_items(sqlite_session_factory, monkeypatch)

    with sqlite_session_factory() as session:
        created = semstorm_brief_service.create_semstorm_brief_items(
            session,
            ids["site_id"],
            plan_item_ids=[ids["seo_audit_plan_id"], ids["local_seo_pricing_plan_id"]],
        )
        brief_ids = {item["primary_keyword"]: int(item["id"]) for item in created["items"]}

        draft_detail = semstorm_brief_service.get_semstorm_brief_item(session, ids["site_id"], brief_ids["seo audit"])
        assert draft_detail["execution_status"] == "draft"
        assert draft_detail["ready_at"] is None

        ready_brief = semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            ids["site_id"],
            brief_ids["seo audit"],
            execution_status="ready",
        )
        assigned_brief = semstorm_brief_service.update_semstorm_brief_execution(
            session,
            ids["site_id"],
            brief_ids["seo audit"],
            updates={
                "assignee": "Alice",
                "execution_note": "Ready for next sprint handoff",
            },
        )
        started_brief = semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            ids["site_id"],
            brief_ids["seo audit"],
            execution_status="in_execution",
        )
        rolled_back_brief = semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            ids["site_id"],
            brief_ids["seo audit"],
            execution_status="ready",
        )
        completed_brief = semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            ids["site_id"],
            brief_ids["seo audit"],
            execution_status="in_execution",
        )
        completed_brief = semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            ids["site_id"],
            brief_ids["seo audit"],
            execution_status="completed",
        )
        archived_brief = semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            ids["site_id"],
            brief_ids["local seo pricing"],
            execution_status="archived",
        )
        execution_payload = semstorm_brief_service.list_semstorm_execution_items(
            session,
            ids["site_id"],
            execution_status="completed",
            assignee="ali",
            brief_type="refresh_existing",
            search="seo audit",
        )
        session.commit()

    assert ready_brief["execution_status"] == "ready"
    assert ready_brief["ready_at"] is not None
    assert assigned_brief["assignee"] == "Alice"
    assert assigned_brief["execution_note"] == "Ready for next sprint handoff"
    assert started_brief["execution_status"] == "in_execution"
    assert started_brief["started_at"] is not None
    assert rolled_back_brief["execution_status"] == "ready"
    assert rolled_back_brief["started_at"] is not None
    assert completed_brief["execution_status"] == "completed"
    assert completed_brief["completed_at"] is not None
    assert archived_brief["execution_status"] == "archived"
    assert archived_brief["archived_at"] is not None

    assert execution_payload["summary"]["total_count"] == 1
    assert execution_payload["summary"]["execution_status_counts"]["completed"] == 1
    assert execution_payload["summary"]["ready_count"] == 0
    assert execution_payload["summary"]["completed_count"] == 1
    item = execution_payload["items"][0]
    assert item["brief_id"] == brief_ids["seo audit"]
    assert item["assignee"] == "Alice"
    assert item["decision_type_snapshot"] == "monitor_only"
    assert item["coverage_status_snapshot"] == "covered"
    assert item["opportunity_score_v2_snapshot"] >= 0


def test_brief_execution_blocks_invalid_transition(sqlite_session_factory, monkeypatch) -> None:
    ids = _seed_plan_items(sqlite_session_factory, monkeypatch)

    with sqlite_session_factory() as session:
        created = semstorm_brief_service.create_semstorm_brief_items(
            session,
            ids["site_id"],
            plan_item_ids=[ids["seo_audit_plan_id"]],
        )
        brief_id = int(created["items"][0]["id"])

        with pytest.raises(semstorm_brief_service.SemstormBriefServiceError) as exc_info:
            semstorm_brief_service.update_semstorm_brief_execution_status(
                session,
                ids["site_id"],
                brief_id,
                execution_status="completed",
            )

    assert exc_info.value.code == "invalid_execution_transition"
    assert exc_info.value.status_code == 409


def test_implemented_read_model_marks_completed_brief_and_evaluates_outcome(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_brief_items(sqlite_session_factory, monkeypatch)
    _add_semstorm_gsc_top_query(
        sqlite_session_factory,
        site_id=ids["site_id"],
        crawl_job_id=ids["crawl_job_id"],
        page_id=ids["audit_page_id"],
        url="https://example.com/seo-audit",
        query="seo audit",
        clicks=19,
        impressions=210,
        ctr=0.09,
        position=4.2,
    )

    monkeypatch.setattr(semstorm_brief_service, "utcnow", lambda: FIXED_TIME + timedelta(days=5))

    with sqlite_session_factory() as session:
        semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            ids["site_id"],
            ids["seo_audit_brief_id"],
            execution_status="ready",
        )
        semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            ids["site_id"],
            ids["seo_audit_brief_id"],
            execution_status="in_execution",
        )
        completed = semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            ids["site_id"],
            ids["seo_audit_brief_id"],
            execution_status="completed",
        )
        assert completed["execution_status"] == "completed"

        implemented = semstorm_brief_service.update_semstorm_brief_implementation_status(
            session,
            ids["site_id"],
            ids["seo_audit_brief_id"],
            implementation_status="implemented",
            evaluation_note="Shipped in the March content sprint.",
        )
        monkeypatch.setattr(semstorm_brief_service, "utcnow", lambda: FIXED_TIME + timedelta(days=40))
        payload = semstorm_brief_service.list_semstorm_implemented_items(
            session,
            ids["site_id"],
            implementation_status="evaluated",
            outcome_status="positive_signal",
            search="seo audit",
            window_days=30,
        )
        detail = semstorm_brief_service.get_semstorm_brief_item(
            session,
            ids["site_id"],
            ids["seo_audit_brief_id"],
        )
        session.commit()

    assert implemented["implementation_status"] == "implemented"
    assert implemented["implemented_at"] is not None
    assert payload["summary"]["total_count"] == 1
    assert payload["summary"]["implementation_status_counts"]["evaluated"] == 1
    assert payload["summary"]["outcome_status_counts"]["positive_signal"] == 1
    item = payload["items"][0]
    assert item["brief_id"] == ids["seo_audit_brief_id"]
    assert item["implementation_status"] == "evaluated"
    assert item["outcome_status"] == "positive_signal"
    assert item["page_present_in_active_crawl"] is True
    assert item["matched_page"]["url"] == "https://example.com/seo-audit"
    assert item["gsc_signal_status"] == "present"
    assert item["gsc_summary"]["clicks"] == 19
    assert item["query_match_count"] >= 1
    assert any("Evaluation note:" in note for note in item["notes"])
    assert detail["implementation_status"] == "evaluated"
    assert detail["last_outcome_checked_at"] is not None


def test_implemented_read_model_handles_too_early_and_missing_signal_context(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_brief_items(sqlite_session_factory, monkeypatch)

    monkeypatch.setattr(semstorm_brief_service, "utcnow", lambda: FIXED_TIME + timedelta(days=5))

    with sqlite_session_factory() as session:
        semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            ids["site_id"],
            ids["local_seo_pricing_brief_id"],
            execution_status="ready",
        )
        semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            ids["site_id"],
            ids["local_seo_pricing_brief_id"],
            execution_status="in_execution",
        )
        semstorm_brief_service.update_semstorm_brief_execution_status(
            session,
            ids["site_id"],
            ids["local_seo_pricing_brief_id"],
            execution_status="completed",
        )
        semstorm_brief_service.update_semstorm_brief_implementation_status(
            session,
            ids["site_id"],
            ids["local_seo_pricing_brief_id"],
            implementation_status="implemented",
            implementation_url_override="https://example.com/local-seo-pricing",
        )
        too_early_payload = semstorm_brief_service.list_semstorm_implemented_items(
            session,
            ids["site_id"],
            implementation_status="too_early",
            outcome_status="too_early",
            window_days=30,
        )
        session.commit()

    assert too_early_payload["summary"]["total_count"] == 1
    too_early_item = too_early_payload["items"][0]
    assert too_early_item["implementation_status"] == "too_early"
    assert too_early_item["outcome_status"] == "too_early"
    assert too_early_item["page_present_in_active_crawl"] is False
    assert too_early_item["gsc_signal_status"] == "none"

    monkeypatch.setattr(semstorm_brief_service, "utcnow", lambda: FIXED_TIME + timedelta(days=45))

    with sqlite_session_factory() as session:
        session.execute(delete(GscTopQuery))
        session.execute(delete(Page).where(Page.crawl_job_id == ids["crawl_job_id"]))
        session.commit()

    with sqlite_session_factory() as session:
        no_signal_payload = semstorm_brief_service.list_semstorm_implemented_items(
            session,
            ids["site_id"],
            implementation_status="evaluated",
            outcome_status="no_signal",
            window_days=30,
        )
        session.commit()

    assert no_signal_payload["summary"]["total_count"] == 1
    assert no_signal_payload["summary"]["implementation_status_counts"]["evaluated"] == 1
    assert no_signal_payload["summary"]["outcome_status_counts"]["no_signal"] == 1
    no_signal_item = no_signal_payload["items"][0]
    assert no_signal_item["page_present_in_active_crawl"] is False
    assert no_signal_item["gsc_signal_status"] == "none"
    assert any("No matching page is currently present" in note for note in no_signal_item["notes"])
