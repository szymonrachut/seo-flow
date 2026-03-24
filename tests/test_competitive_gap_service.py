from __future__ import annotations

import csv
import io
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.core.text_processing import VISIBLE_TEXT_CHAR_LIMIT, hash_content_text
from app.db.models import SiteCompetitor, SiteCompetitorPage, SiteCompetitorPageExtraction, Site, SiteContentGapCandidate
from sqlalchemy import select

from app.services import (
    content_gap_candidate_service,
    content_gap_item_materialization_service,
    content_gap_review_run_service,
    competitive_gap_own_semantic_service,
    competitive_gap_semantic_service,
    competitive_gap_service,
    site_competitor_service,
)
from app.services.competitive_gap_keys import build_competitive_gap_key
from app.services.competitive_gap_page_diagnostics import (
    get_page_visible_text_chars,
    get_page_visible_text_truncated,
)
from app.services.competitive_gap_semantic_card_service import build_semantic_card
from app.services.export_service import build_site_competitive_gap_csv
from tests.competitive_gap_test_utils import FIXED_TIME, seed_competitive_gap_site
from tests.test_content_gap_review_run_service import _add_candidate, _seed_site_with_two_crawls


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_competitor_page_visible_text_is_sanitized_limited_and_hashed(db_session) -> None:
    site = Site(root_url="https://example.com", domain="example.com", created_at=FIXED_TIME)
    db_session.add(site)
    db_session.flush()

    competitor = SiteCompetitor(
        site_id=site.id,
        label="Competitor",
        root_url="https://competitor.com",
        domain="competitor.com",
        is_active=True,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    db_session.add(competitor)
    db_session.flush()

    raw_text = ("Alpha \n\n Beta   " * 2_000).strip()
    page = SiteCompetitorPage(
        site_id=site.id,
        competitor_id=competitor.id,
        url="https://competitor.com/page",
        normalized_url="https://competitor.com/page",
        visible_text=raw_text,
        fetched_at=FIXED_TIME,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    db_session.add(page)
    db_session.flush()

    assert page.visible_text is not None
    assert "\n" not in page.visible_text
    assert "  " not in page.visible_text
    assert get_page_visible_text_chars(page) == len(page.visible_text)
    assert get_page_visible_text_chars(page) == VISIBLE_TEXT_CHAR_LIMIT
    assert get_page_visible_text_truncated(page) is True
    assert page.content_text_hash == hash_content_text(raw_text)


def test_page_requires_extraction_changes_when_content_hash_changes(db_session) -> None:
    site = Site(root_url="https://example.com", domain="example.com", created_at=FIXED_TIME)
    db_session.add(site)
    db_session.flush()

    competitor = SiteCompetitor(
        site_id=site.id,
        label="Competitor",
        root_url="https://competitor.com",
        domain="competitor.com",
        is_active=True,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    db_session.add(competitor)
    db_session.flush()

    page = SiteCompetitorPage(
        site_id=site.id,
        competitor_id=competitor.id,
        url="https://competitor.com/page",
        normalized_url="https://competitor.com/page",
        visible_text="Alpha beta",
        fetched_at=FIXED_TIME,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    db_session.add(page)
    db_session.flush()

    extraction = SiteCompetitorPageExtraction(
        site_id=site.id,
        competitor_id=competitor.id,
        competitor_page_id=page.id,
        content_hash_at_extraction=page.content_text_hash,
        semantic_version="competitive-gap-semantic-card-v1",
        semantic_input_hash="test-hash",
        semantic_card_json=build_semantic_card(
            primary_topic="Alpha Beta",
            topic_labels=["Alpha Beta"],
            core_problem="Alpha beta",
            dominant_intent="commercial",
            page_role="money_page",
            content_format="service_page",
            what_this_page_is_about="Alpha beta",
            what_this_page_is_not_about="Not another topic.",
            commerciality="high",
            evidence_snippets=["Alpha beta"],
            confidence=0.8,
        ),
        topic_key="alpha-beta",
        topic_label="Alpha Beta",
        extracted_at=FIXED_TIME,
    )
    db_session.add(extraction)
    db_session.flush()

    assert site_competitor_service.page_requires_extraction(page, extraction) is False

    page.visible_text = "Alpha beta gamma"
    db_session.flush()

    assert site_competitor_service.page_requires_extraction(page, extraction) is True


def test_competitive_gap_service_builds_stable_gap_rows_and_uses_latest_extraction(sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            gsc_date_range="last_28_days",
            page=1,
            page_size=50,
        )

        assert payload["context"]["active_crawl_id"] == ids["crawl_job_id"]
        assert payload["context"]["strategy_present"] is True
        assert payload["context"]["empty_state_reason"] is None
        assert payload["context"]["data_readiness"]["gap_ready"] is True
        assert payload["context"]["data_readiness"]["total_current_extractions_count"] >= 1
        assert payload["summary"]["counts_by_type"]["NEW_TOPIC"] >= 1
        assert payload["summary"]["counts_by_type"]["EXPAND_EXISTING_TOPIC"] >= 1
        assert payload["summary"]["counts_by_type"]["MISSING_SUPPORTING_PAGE"] >= 1

        rows_by_type = {row["gap_type"]: row for row in payload["items"]}
        assert all(row["topic_key"] != "legacy-local" for row in payload["items"])
        assert all(row["semantic_cluster_key"] for row in payload["items"])
        assert all(row["canonical_topic_label"] for row in payload["items"])
        assert all(row["own_match_status"] in {"exact_match", "semantic_match", "partial_coverage", "no_meaningful_match"} for row in payload["items"])

        new_topic = rows_by_type["NEW_TOPIC"]
        assert new_topic["topic_key"] == "local-seo"
        assert new_topic["topic_label"] == "Local SEO"
        assert new_topic["target_page_id"] is None
        assert new_topic["gap_key"] == build_competitive_gap_key(
            gap_type="NEW_TOPIC",
            topic_key=new_topic["semantic_cluster_key"],
            target_page_id=None,
            suggested_page_type=new_topic["suggested_page_type"],
        )
        assert new_topic["own_match_status"] == "no_meaningful_match"

        missing_support = rows_by_type["MISSING_SUPPORTING_PAGE"]
        assert missing_support["topic_key"] == "seo-audit"
        assert missing_support["target_page_id"] == ids["audit_page_id"]
        assert missing_support["suggested_page_type"] == "faq"
        assert missing_support["own_match_status"] in {"partial_coverage", "semantic_match", "exact_match"}

        expand_existing = rows_by_type["EXPAND_EXISTING_TOPIC"]
        assert expand_existing["topic_key"] == "content-strategy"
        assert expand_existing["target_page_id"] == ids["content_strategy_page_id"]
        assert expand_existing["target_url"] == "https://example.com/content-strategy"
        assert 0.35 <= float(expand_existing["confidence"]) <= 0.95
        assert expand_existing["semantic_cluster_key"] != new_topic["semantic_cluster_key"]


def test_competitive_gap_read_model_reuses_current_own_semantic_profiles(sqlite_session_factory, monkeypatch) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        first_payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            gsc_date_range="last_28_days",
            page=1,
            page_size=50,
        )
        assert first_payload["items"]
        session.commit()

    monkeypatch.setattr(
        competitive_gap_own_semantic_service,
        "ensure_current_own_page_semantic_profiles",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("should reuse current profiles")),
    )

    with sqlite_session_factory() as session:
        second_payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            gsc_date_range="last_28_days",
            page=1,
            page_size=50,
        )

    assert second_payload["items"]


def test_competitive_gap_read_model_uses_legacy_source_mode_by_default(monkeypatch) -> None:
    legacy_payload = {"context": {"empty_state_reason": None}, "summary": {}, "items": []}
    call_order: list[str] = []

    monkeypatch.delenv("CONTENT_GAP_READ_MODEL_MODE", raising=False)
    monkeypatch.setattr(
        competitive_gap_service,
        "_build_current_competitive_gap_read_model",
        lambda *args, **kwargs: call_order.append("legacy") or legacy_payload,
    )
    monkeypatch.setattr(
        competitive_gap_service,
        "_build_reviewed_content_gap_read_model",
        lambda *args, **kwargs: call_order.append("reviewed") or None,
    )
    monkeypatch.setattr(
        competitive_gap_service,
        "_build_raw_candidate_content_gap_read_model",
        lambda *args, **kwargs: call_order.append("raw_candidates") or None,
    )

    payload = competitive_gap_service._build_competitive_gap_read_model(
        session=None,  # type: ignore[arg-type]
        site_id=1,
        active_crawl_id=2,
        gsc_date_range="last_28_days",
    )

    assert payload is legacy_payload
    assert call_order == ["legacy"]


def test_competitive_gap_read_model_hybrid_mode_falls_back_to_legacy_pipeline(monkeypatch) -> None:
    legacy_payload = {"context": {"empty_state_reason": None}, "summary": {}, "items": []}
    call_order: list[str] = []

    monkeypatch.setenv("CONTENT_GAP_READ_MODEL_MODE", "hybrid")
    monkeypatch.setattr(
        competitive_gap_service,
        "_build_reviewed_content_gap_read_model",
        lambda *args, **kwargs: call_order.append("reviewed") or None,
    )
    monkeypatch.setattr(
        competitive_gap_service,
        "_build_raw_candidate_content_gap_read_model",
        lambda *args, **kwargs: call_order.append("raw_candidates") or None,
    )
    monkeypatch.setattr(
        competitive_gap_service,
        "_build_current_competitive_gap_read_model",
        lambda *args, **kwargs: call_order.append("legacy") or legacy_payload,
    )

    payload = competitive_gap_service._build_competitive_gap_read_model(
        session=None,  # type: ignore[arg-type]
        site_id=1,
        active_crawl_id=2,
        gsc_date_range="last_28_days",
    )

    assert payload is legacy_payload
    assert call_order == ["reviewed", "raw_candidates", "legacy"]


def test_semantic_read_model_is_skipped_when_candidate_volume_is_too_large() -> None:
    candidates = [SimpleNamespace(id=index) for index in range(competitive_gap_service.SEMANTIC_READ_MODEL_MAX_CANDIDATES + 1)]

    assert competitive_gap_service._should_skip_semantic_read_model(candidates) is True
    assert (
        competitive_gap_service._should_skip_semantic_read_model(
            candidates[: competitive_gap_service.SEMANTIC_READ_MODEL_MAX_CANDIDATES]
        )
        is False
    )


def test_competitive_gap_read_model_prefers_reviewed_items_for_active_snapshot(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    monkeypatch.setenv("CONTENT_GAP_READ_MODEL_MODE", "hybrid")

    with sqlite_session_factory() as session:
        content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            ids["site_id"],
            basis_crawl_job_id=ids["crawl_job_id"],
        )
        run_payload = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_job_id"],
        )
        candidates = session.scalars(
            select(SiteContentGapCandidate)
            .where(
                SiteContentGapCandidate.site_id == ids["site_id"],
                SiteContentGapCandidate.basis_crawl_job_id == ids["crawl_job_id"],
                SiteContentGapCandidate.current.is_(True),
                SiteContentGapCandidate.status == "active",
            )
            .order_by(SiteContentGapCandidate.id.asc())
        ).all()
        content_gap_item_materialization_service.materialize_review_items(
            session,
            site_id=ids["site_id"],
            review_run_id=run_payload["id"],
            decisions=[
                content_gap_item_materialization_service.SanitizedContentGapDecision(
                    source_candidate_id=int(candidate.id),
                    decision_action="keep",
                    decision_reason_text=f"Keep {candidate.original_topic_label}.",
                    fit_score=80.0 + index,
                    confidence=0.8,
                    reviewed_phrase=candidate.original_phrase,
                    reviewed_topic_label=candidate.original_topic_label,
                    reviewed_normalized_topic_key=candidate.normalized_topic_key,
                    reviewed_gap_type=candidate.gap_type,
                )
                for index, candidate in enumerate(candidates, start=1)
            ],
        )
        content_gap_review_run_service._complete_review_run_in_session(
            session,
            site_id=ids["site_id"],
            run_id=run_payload["run_id"],
            completed_batch_count=run_payload["batch_count"],
        )
        session.commit()

    with sqlite_session_factory() as session:
        payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            active_crawl_id=ids["crawl_job_id"],
            page=1,
            page_size=50,
        )

    assert payload["context"]["data_source_mode"] == "reviewed"
    assert payload["context"]["basis_crawl_job_id"] == ids["crawl_job_id"]
    assert payload["context"]["is_outdated_for_active_crawl"] is False
    assert payload["items"]
    assert all(item["decision_action"] == "keep" for item in payload["items"])
    assert all(item["fit_score"] is not None for item in payload["items"])


def test_competitive_gap_read_model_falls_back_to_raw_candidates_when_reviewed_missing(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    monkeypatch.setenv("CONTENT_GAP_READ_MODEL_MODE", "hybrid")

    with sqlite_session_factory() as session:
        content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            ids["site_id"],
            basis_crawl_job_id=ids["crawl_job_id"],
        )
        session.commit()

    with sqlite_session_factory() as session:
        payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            active_crawl_id=ids["crawl_job_id"],
            page=1,
            page_size=50,
        )

    assert payload["context"]["data_source_mode"] == "raw_candidates"
    assert payload["items"]
    assert all(item["decision_action"] is None for item in payload["items"])
    assert all(item["topic_label"] for item in payload["items"])


def test_competitive_gap_read_model_falls_back_to_legacy_for_changed_active_snapshot(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    monkeypatch.setenv("CONTENT_GAP_READ_MODEL_MODE", "hybrid")

    with sqlite_session_factory() as session:
        _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-a",
            candidate_input_hash="hash-a",
            topic_key="local-seo",
            topic_label="Local SEO",
        )
        session.commit()

    with sqlite_session_factory() as session:
        payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            active_crawl_id=ids["crawl_b_id"],
            page=1,
            page_size=25,
        )

    assert payload["context"]["data_source_mode"] == "legacy"
    assert payload["context"]["active_crawl_id"] == ids["crawl_b_id"]
    assert payload["context"]["is_outdated_for_active_crawl"] is True


def test_competitive_gap_topic_filter_and_csv_export_reuse_same_rows(sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        filtered = competitive_gap_service.get_all_competitive_gap_rows(
            session,
            ids["site_id"],
            topic="local seo",
            sort_by="priority_score",
            sort_order="desc",
        )
        assert len(filtered) >= 1
        assert all("local seo" in row["topic_label"].lower() or "local-seo" in row["topic_key"] for row in filtered)

        csv_content = build_site_competitive_gap_csv(
            session,
            ids["site_id"],
            topic="local seo",
            sort_by="priority_score",
            sort_order="desc",
        )

    rows = list(csv.DictReader(io.StringIO(csv_content.lstrip("\ufeff"))))
    assert len(rows) == len(filtered)
    assert all("Local SEO" in row["topic_label"] or "local-seo" in row["topic_key"] for row in rows)
    assert all(row["semantic_cluster_key"].startswith("sg:") for row in rows)
    assert all(row["canonical_topic_label"] for row in rows)
    assert all(row["own_match_status"] for row in rows)


def test_competitive_gap_csv_export_reuses_raw_candidate_source_selection(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    monkeypatch.setenv("CONTENT_GAP_READ_MODEL_MODE", "hybrid")

    with sqlite_session_factory() as session:
        content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            ids["site_id"],
            basis_crawl_job_id=ids["crawl_job_id"],
        )
        session.commit()

    with sqlite_session_factory() as session:
        filtered = competitive_gap_service.get_all_competitive_gap_rows(
            session,
            ids["site_id"],
            active_crawl_id=ids["crawl_job_id"],
            topic="local seo",
            sort_by="priority_score",
            sort_order="desc",
        )
        csv_content = build_site_competitive_gap_csv(
            session,
            ids["site_id"],
            active_crawl_id=ids["crawl_job_id"],
            topic="local seo",
            sort_by="priority_score",
            sort_order="desc",
        )

    assert filtered
    rows = list(csv.DictReader(io.StringIO(csv_content.lstrip("\ufeff"))))
    assert [row["gap_key"] for row in rows] == [row["gap_key"] for row in filtered]


def test_competitive_gap_service_filters_by_match_status_sorts_by_key_values_and_excludes_low_value_topics(
    sqlite_session_factory,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        competitor = session.query(SiteCompetitor).filter(SiteCompetitor.id == ids["competitor_a_id"]).one()
        privacy_page = SiteCompetitorPage(
            site_id=ids["site_id"],
            competitor_id=competitor.id,
            url="https://competitor-a.com/privacy-policy",
            normalized_url="https://competitor-a.com/privacy-policy",
            final_url="https://competitor-a.com/privacy-policy",
            status_code=200,
            title="Privacy Policy",
            h1="Privacy Policy",
            page_type="legal",
            page_bucket="trust",
            visible_text="Privacy policy content for legal compliance.",
            fetched_at=FIXED_TIME,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        session.add(privacy_page)
        session.flush()
        session.add(
            SiteCompetitorPageExtraction(
                site_id=ids["site_id"],
                competitor_id=competitor.id,
                competitor_page_id=privacy_page.id,
                content_hash_at_extraction=privacy_page.content_text_hash,
                topic_key="privacy-policy",
                topic_label="Privacy Policy",
                page_role="utility_page",
                confidence=0.72,
                extracted_at=FIXED_TIME,
            )
        )
        session.commit()

    with sqlite_session_factory() as session:
        no_match_rows = competitive_gap_service.get_all_competitive_gap_rows(
            session,
            ids["site_id"],
            own_match_status="no_meaningful_match",
            sort_by="business_value_score",
            sort_order="desc",
        )
        assert no_match_rows
        assert all(row["own_match_status"] == "no_meaningful_match" for row in no_match_rows)
        scores = [int(row["business_value_score"]) for row in no_match_rows]
        assert scores == sorted(scores, reverse=True)

        all_rows = competitive_gap_service.get_all_competitive_gap_rows(
            session,
            ids["site_id"],
            sort_by="merged_topic_count",
            sort_order="desc",
        )
        assert all("privacy" not in str(row["topic_key"]).lower() for row in all_rows)
        assert all("privacy" not in str(row["topic_label"]).lower() for row in all_rows)


def test_competitive_gap_service_reports_missing_strategy_and_missing_current_extractions(sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        site = session.get(Site, ids["site_id"])
        assert site is not None
        if site.content_strategy is not None:
            session.delete(site.content_strategy)
        session.query(SiteCompetitorPageExtraction).filter(
            SiteCompetitorPageExtraction.site_id == ids["site_id"]
        ).delete(synchronize_session=False)
        session.commit()

    with sqlite_session_factory() as session:
        payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            gsc_date_range="last_28_days",
            page=1,
            page_size=25,
        )

        assert payload["items"] == []
        assert payload["context"]["strategy_present"] is False
        assert payload["context"]["empty_state_reason"] == "no_competitor_extractions"
        assert payload["context"]["data_readiness"]["has_strategy"] is False
        assert "strategy" in payload["context"]["data_readiness"]["missing_inputs"]
        assert "competitor_extractions" in payload["context"]["data_readiness"]["missing_inputs"]
        assert payload["context"]["data_readiness"]["total_competitor_pages_count"] >= 1
        assert payload["context"]["data_readiness"]["total_current_extractions_count"] == 0


def test_competitive_gap_service_reports_no_competitor_pages(sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        session.query(SiteCompetitorPageExtraction).filter(
            SiteCompetitorPageExtraction.site_id == ids["site_id"]
        ).delete(synchronize_session=False)
        session.query(SiteCompetitorPage).filter(
            SiteCompetitorPage.site_id == ids["site_id"]
        ).delete(synchronize_session=False)
        session.commit()

    with sqlite_session_factory() as session:
        payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            gsc_date_range="last_28_days",
            page=1,
            page_size=25,
        )

        assert payload["items"] == []
        assert payload["context"]["empty_state_reason"] == "no_competitor_pages"
        assert "competitor_pages" in payload["context"]["data_readiness"]["missing_inputs"]
        assert payload["context"]["data_readiness"]["total_competitor_pages_count"] == 0


def test_resolve_cluster_coverage_prefers_partial_or_strong_coverage_over_no_meaningful_when_anchors_align() -> None:
    cluster_card = build_semantic_card(
        primary_topic="Local SEO",
        topic_labels=["Local SEO"],
        core_problem="Local SEO support for growing businesses.",
        dominant_intent="commercial",
        secondary_intents=[],
        page_role="money_page",
        content_format="service_page",
        what_this_page_is_about="Local SEO support for growing businesses.",
        what_this_page_is_not_about="Not another topic.",
        commerciality="high",
        evidence_snippets=["Local SEO"],
        confidence=0.82,
    )
    own_page = competitive_gap_service.OwnPageTopicProfile(
        page_id=101,
        url="https://example.com/local-seo-services",
        normalized_url="https://example.com/local-seo-services",
        title="Local SEO Services",
        h1="Local SEO Services",
        meta_description="Local SEO services and Google Business Profile support.",
        page_type="service",
        page_bucket="commercial",
        priority_score=58,
        impressions=180,
        clicks=12,
        word_count=620,
        semantic_input_hash="own-local-seo-hash",
        semantic_card=build_semantic_card(
            primary_topic="Google Business Profile Optimization",
            topic_labels=["Google Business Profile Optimization"],
            core_problem="GBP optimization for local visibility.",
            dominant_intent="commercial",
            secondary_intents=[],
            page_role="money_page",
            content_format="service_page",
            what_this_page_is_about="GBP optimization for local visibility.",
            what_this_page_is_not_about="Not another topic.",
            commerciality="high",
            evidence_snippets=["Google Business Profile"],
            confidence=0.76,
        ),
        dominant_intent="commercial",
        page_role="money_page",
        content_format="service_page",
        geo_scope=None,
        entities=[],
        supporting_subtopics=[],
        topic_key="google-business-profile",
        topic_tokens={"google", "business", "profile"},
    )

    coverage = competitive_gap_service._resolve_cluster_coverage(
        cluster_card=cluster_card,
        cluster_members=[SimpleNamespace(page_type="service")],
        own_pages=[own_page],
    )

    assert coverage["coverage_type"] in {"partial_coverage", "strong_semantic_coverage"}
    assert coverage["coverage_type"] != "no_meaningful_coverage"
    assert coverage["coverage_reason_code"] in {"partial_semantic_overlap", "strong_semantic_overlap"}
    assert coverage["coverage_debug"]["anchor_overlap_score"] >= 0.22


def test_dedupe_equivalent_gap_rows_merges_logically_equivalent_recommendations() -> None:
    base_row = {
        "gap_key": "gap-a",
        "semantic_cluster_key": "sg:a",
        "gap_type": "EXPAND_EXISTING_TOPIC",
        "gap_detail_type": "EXPAND_EXISTING_PAGE",
        "coverage_type": "strong_semantic_coverage",
        "canonical_topic_label": "Local SEO",
        "topic_label": "Local SEO Services",
        "topic_key": "local-seo-services",
        "target_page_id": 11,
        "cluster_intent_profile": "commercial",
        "cluster_role_summary": {"money_page": 2},
        "competitor_ids": [1],
        "competitor_urls": ["https://competitor-a.com/local-seo"],
        "coverage_best_own_urls": ["https://example.com/local-seo"],
        "supporting_evidence": ["Local SEO services"],
        "cluster_entities": ["GBP"],
        "priority_score": 74,
        "competitor_count": 1,
        "merged_topic_count": 1,
        "cluster_member_count": 1,
        "coverage_confidence": 0.81,
        "cluster_confidence": 0.77,
        "signals": {
            "semantic": {
                "source_candidate_ids": [101],
                "source_topic_keys": ["local-seo-services"],
            }
        },
    }
    duplicate_row = {
        **base_row,
        "gap_key": "gap-b",
        "semantic_cluster_key": "sg:b",
        "topic_label": "Local SEO",
        "topic_key": "local-seo",
        "competitor_ids": [2],
        "competitor_urls": ["https://competitor-b.com/local-seo"],
        "supporting_evidence": ["Local SEO"],
        "signals": {
            "semantic": {
                "source_candidate_ids": [202],
                "source_topic_keys": ["local-seo"],
            }
        },
        "priority_score": 72,
        "competitor_count": 1,
    }
    distinct_row = {
        **base_row,
        "gap_key": "gap-c",
        "semantic_cluster_key": "sg:c",
        "canonical_topic_label": "SEO Audit",
        "topic_label": "SEO Audit",
        "topic_key": "seo-audit",
        "competitor_ids": [3],
        "coverage_type": "partial_coverage",
        "gap_detail_type": "MISSING_SUPPORTING_CONTENT",
    }

    rows = competitive_gap_service._dedupe_equivalent_gap_rows([base_row, duplicate_row, distinct_row])

    assert len(rows) == 2
    merged_local = next(row for row in rows if row["canonical_topic_label"] == "Local SEO")
    assert sorted(merged_local["competitor_ids"]) == [1, 2]
    assert sorted(merged_local["signals"]["semantic"]["source_candidate_ids"]) == [101, 202]
    assert merged_local["signals"]["semantic"]["dedupe_count"] == 2
    assert "matching canonical topic" in merged_local["signals"]["semantic"]["dedupe_reason"]


def test_competitive_gap_service_reports_no_competitors_and_no_active_crawl(sqlite_session_factory) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        competitors = session.query(SiteCompetitor).filter(SiteCompetitor.site_id == ids["site_id"]).all()
        for competitor in competitors:
            competitor.is_active = False
        session.commit()

    with sqlite_session_factory() as session:
        payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            gsc_date_range="last_28_days",
            page=1,
            page_size=25,
        )
        assert payload["context"]["empty_state_reason"] == "no_competitors"
        assert "competitors" in payload["context"]["data_readiness"]["missing_inputs"]

    with sqlite_session_factory() as session:
        site = Site(root_url="https://no-crawl.example", domain="no-crawl.example", created_at=FIXED_TIME)
        session.add(site)
        session.commit()
        site_id = site.id

    with sqlite_session_factory() as session:
        payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            site_id,
            gsc_date_range="last_28_days",
            page=1,
            page_size=25,
        )
        assert payload["items"] == []
        assert payload["context"]["empty_state_reason"] == "no_active_crawl"
        assert payload["context"]["data_readiness"]["has_active_crawl"] is False
        assert "active_crawl" in payload["context"]["data_readiness"]["missing_inputs"]


def test_semantic_gap_payload_reuses_own_site_candidate_lookup_once_per_request(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    get_settings.cache_clear()
    monkeypatch.setenv("OPENAI_LLM_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with sqlite_session_factory() as session:
        competitors = session.query(SiteCompetitor).filter(SiteCompetitor.site_id == ids["site_id"]).all()
        for competitor in competitors:
            for page in competitor.pages:
                page.status_code = 200
                page.visible_text = ((page.visible_text or page.title or page.h1 or "seo topic") + " ") * 12
        session.commit()

    with sqlite_session_factory() as session:
        for competitor_id in [ids["competitor_a_id"], ids["competitor_b_id"]]:
            page_ids = session.scalars(
                select(SiteCompetitorPage.id)
                .where(SiteCompetitorPage.competitor_id == competitor_id)
                .order_by(SiteCompetitorPage.id.asc())
            ).all()
            competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
                session,
                ids["site_id"],
                competitor_id,
                page_ids=page_ids,
            )
        session.commit()

    original_list_own_site_match_candidates = competitive_gap_semantic_service.list_own_site_match_candidates
    call_count = 0

    def counting_list_own_site_match_candidates(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original_list_own_site_match_candidates(*args, **kwargs)

    monkeypatch.setattr(competitive_gap_semantic_service, "list_own_site_match_candidates", counting_list_own_site_match_candidates)

    with sqlite_session_factory() as session:
        payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            active_crawl_id=ids["crawl_job_id"],
            gsc_date_range="last_28_days",
            page=1,
            page_size=25,
        )

    assert payload["items"]
    assert call_count == 0
    get_settings.cache_clear()
