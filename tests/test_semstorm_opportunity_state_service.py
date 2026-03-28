from __future__ import annotations

from sqlalchemy import select

from app.db.models import Site, SiteSemstormOpportunityState, SiteSemstormPromotedItem
from app.services import semstorm_opportunity_state_service


def _seed_site(session_factory) -> int:
    with session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com")
        session.add(site)
        session.commit()
        return int(site.id)


def test_upsert_opportunity_state_uses_site_and_normalized_keyword(sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        first = semstorm_opportunity_state_service.upsert_opportunity_state(
            session,
            site_id=site_id,
            normalized_keyword=" SEO Audit ",
            state_status="accepted",
            source_run_id=3,
            note="Keep this",
        )
        session.flush()
        first_id = int(first.id)

        updated = semstorm_opportunity_state_service.upsert_opportunity_state(
            session,
            site_id=site_id,
            normalized_keyword="seo audit",
            state_status="dismissed",
            source_run_id=4,
            note="Out of scope",
        )
        session.commit()

    assert int(updated.id) == first_id
    assert updated.normalized_keyword == "seo audit"
    assert updated.state_status == "dismissed"
    assert updated.source_run_id == 4
    assert updated.accepted_at is not None
    assert updated.dismissed_at is not None
    assert updated.note == "Out of scope"

    with sqlite_session_factory() as session:
        rows = list(session.scalars(select(SiteSemstormOpportunityState)))

    assert len(rows) == 1
    assert rows[0].opportunity_key.startswith("semstorm:")


def test_create_promoted_item_is_idempotent_per_site_keyword(sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        first, created_first = semstorm_opportunity_state_service.create_promoted_item(
            session,
            site_id=site_id,
            source_run_id=2,
            keyword="SEO Audit",
            normalized_keyword="seo audit",
            bucket="core_opportunity",
            decision_type="create_new_page",
            opportunity_score_v2=91,
            coverage_status="missing",
            best_match_page_url=None,
            gsc_signal_status="none",
            source_payload_json={"keyword": "SEO Audit"},
        )
        session.flush()
        second, created_second = semstorm_opportunity_state_service.create_promoted_item(
            session,
            site_id=site_id,
            source_run_id=3,
            keyword="Seo audit",
            normalized_keyword=" seo audit ",
            bucket="quick_win",
            decision_type="expand_existing_page",
            opportunity_score_v2=50,
            coverage_status="weak_coverage",
            best_match_page_url="https://example.com/seo-audit",
            gsc_signal_status="present",
            source_payload_json={"keyword": "Seo audit"},
        )
        session.commit()

    assert created_first is True
    assert created_second is False
    assert int(first.id) == int(second.id)
    assert first.keyword == "SEO Audit"
    assert first.source_run_id == 2

    with sqlite_session_factory() as session:
        rows = list(session.scalars(select(SiteSemstormPromotedItem)))

    assert len(rows) == 1
    assert rows[0].normalized_keyword == "seo audit"
    assert rows[0].promotion_status == "active"
