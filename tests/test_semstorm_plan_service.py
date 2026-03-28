from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services import semstorm_plan_service, semstorm_service
from tests.competitive_gap_test_utils import seed_competitive_gap_site
from tests.test_semstorm_service import PersistedSemstormClient


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _seed_promoted_items(session_factory, monkeypatch) -> dict[str, int]:
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
            keywords=["seo audit", "content strategy template"],
            note="Seed backlog",
        )
        promoted = semstorm_service.list_semstorm_promoted_items(session, ids["site_id"])
        session.commit()

    promoted_ids = {item["keyword"]: int(item["id"]) for item in promoted["items"]}
    ids["seo_audit_promoted_id"] = promoted_ids["seo audit"]
    ids["content_strategy_promoted_id"] = promoted_ids["content strategy template"]
    return ids


def test_create_plan_items_is_idempotent_and_skips_missing_ids(sqlite_session_factory, monkeypatch) -> None:
    ids = _seed_promoted_items(sqlite_session_factory, monkeypatch)

    with sqlite_session_factory() as session:
        first = semstorm_plan_service.create_semstorm_plan_items(
            session,
            ids["site_id"],
            promoted_item_ids=[
                ids["seo_audit_promoted_id"],
                ids["content_strategy_promoted_id"],
                9999,
            ],
            target_page_type="new_page",
        )
        second = semstorm_plan_service.create_semstorm_plan_items(
            session,
            ids["site_id"],
            promoted_item_ids=[ids["seo_audit_promoted_id"]],
            target_page_type="new_page",
        )
        plans = semstorm_plan_service.list_semstorm_plan_items(session, ids["site_id"])
        session.commit()

    assert first["created_count"] == 2
    assert first["updated_count"] == 0
    assert first["skipped_count"] == 1
    assert {item["keyword"] for item in first["items"]} == {
        "seo audit",
        "content strategy template",
    }
    assert first["skipped"] == [
        {
            "promoted_item_id": 9999,
            "keyword": None,
            "reason": "promoted_item_not_found",
        }
    ]
    assert all(item["target_page_type"] == "new_page" for item in first["items"])
    assert all(item["state_status"] == "planned" for item in first["items"])
    assert plans["summary"]["total_count"] == 2

    assert second["created_count"] == 0
    assert second["skipped"] == [
        {
            "promoted_item_id": ids["seo_audit_promoted_id"],
            "keyword": "seo audit",
            "reason": "already_exists",
        }
    ]


def test_plan_items_support_detail_update_status_and_filters(sqlite_session_factory, monkeypatch) -> None:
    ids = _seed_promoted_items(sqlite_session_factory, monkeypatch)

    with sqlite_session_factory() as session:
        created = semstorm_plan_service.create_semstorm_plan_items(
            session,
            ids["site_id"],
            promoted_item_ids=[ids["content_strategy_promoted_id"]],
        )
        created_plan_id = int(created["items"][0]["id"])

        updated = semstorm_plan_service.update_semstorm_plan_item(
            session,
            ids["site_id"],
            created_plan_id,
            updates={
                "plan_title": "Cluster support for content strategy",
                "plan_note": "Keep this in planning backlog.",
                "target_page_type": "cluster_support",
                "proposed_slug": "content-strategy-support",
                "proposed_primary_keyword": "content strategy support",
                "proposed_secondary_keywords": ["editorial planning", "content calendar"],
            },
        )
        status_updated = semstorm_plan_service.update_semstorm_plan_item_status(
            session,
            ids["site_id"],
            created_plan_id,
            state_status="in_progress",
        )
        detail = semstorm_plan_service.get_semstorm_plan_item(session, ids["site_id"], created_plan_id)
        filtered = semstorm_plan_service.list_semstorm_plan_items(
            session,
            ids["site_id"],
            state_status="in_progress",
            target_page_type="cluster_support",
            search="cluster",
        )
        session.commit()

    assert updated["plan_title"] == "Cluster support for content strategy"
    assert updated["target_page_type"] == "cluster_support"
    assert updated["proposed_secondary_keywords"] == ["editorial planning", "content calendar"]
    assert status_updated["state_status"] == "in_progress"
    assert detail["plan_note"] == "Keep this in planning backlog."
    assert filtered["summary"]["total_count"] == 1
    assert filtered["summary"]["state_counts"]["in_progress"] == 1
    assert filtered["summary"]["target_page_type_counts"]["cluster_support"] == 1
    assert filtered["items"][0]["id"] == created_plan_id
