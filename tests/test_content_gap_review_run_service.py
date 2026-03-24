from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import (
    CrawlJob,
    CrawlJobStatus,
    GscProperty,
    GscTopQuery,
    Page,
    Site,
    SiteContentGapCandidate,
    SiteContentGapReviewRun,
)
from app.services import content_gap_review_run_service
from app.services.content_gap_candidate_service import CONTENT_GAP_CANDIDATE_GENERATION_VERSION
from tests.test_competitor_sync_service import FIXED_TIME


def _seed_site_with_two_crawls(sqlite_session_factory) -> dict[str, int]:
    with sqlite_session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com", created_at=FIXED_TIME)
        session.add(site)
        session.flush()

        crawl_a = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=FIXED_TIME,
            started_at=FIXED_TIME,
            finished_at=FIXED_TIME,
            settings_json={"start_url": "https://example.com"},
            stats_json={},
        )
        crawl_b = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=FIXED_TIME + timedelta(days=1),
            started_at=FIXED_TIME + timedelta(days=1),
            finished_at=FIXED_TIME + timedelta(days=1),
            settings_json={"start_url": "https://example.com"},
            stats_json={},
        )
        session.add_all([crawl_a, crawl_b])
        session.flush()

        page_a = Page(
            crawl_job_id=crawl_a.id,
            url="https://example.com/local-seo",
            normalized_url="https://example.com/local-seo",
            title="Local SEO",
            h1="Local SEO",
            meta_description="Local SEO services.",
            page_type="service",
            page_bucket="money",
        )
        page_b = Page(
            crawl_job_id=crawl_b.id,
            url="https://example.com/seo-audit",
            normalized_url="https://example.com/seo-audit",
            title="SEO Audit",
            h1="SEO Audit",
            meta_description="SEO audit services.",
            page_type="service",
            page_bucket="money",
        )
        session.add_all([page_a, page_b])
        session.commit()
        return {
            "site_id": site.id,
            "crawl_a_id": crawl_a.id,
            "crawl_b_id": crawl_b.id,
            "page_a_id": page_a.id,
            "page_b_id": page_b.id,
        }


def _add_candidate(
    session,
    *,
    site_id: int,
    basis_crawl_job_id: int,
    candidate_key: str,
    candidate_input_hash: str,
    topic_key: str,
    topic_label: str,
    created_at=FIXED_TIME,
) -> SiteContentGapCandidate:
    candidate = SiteContentGapCandidate(
        site_id=site_id,
        basis_crawl_job_id=basis_crawl_job_id,
        candidate_key=candidate_key,
        candidate_input_hash=candidate_input_hash,
        status="active",
        current=True,
        generation_version=CONTENT_GAP_CANDIDATE_GENERATION_VERSION,
        rules_version="competitive-gap-legacy-read-model-v1",
        normalized_topic_key=topic_key,
        original_topic_label=topic_label,
        original_phrase=topic_label,
        gap_type="NEW_TOPIC",
        source_cluster_key=f"cluster:{candidate_key}",
        source_cluster_hash=f"cluster-hash:{candidate_input_hash}",
        source_competitor_ids_json=[1, 2],
        source_competitor_page_ids_json=[11, 12],
        competitor_count=2,
        own_coverage_hint="none",
        deterministic_priority_score=80,
        rationale_summary=f"Rationale for {topic_label}",
        signals_json={"semantic": {"candidate_source_mode": "legacy"}},
        review_needed=True,
        review_visibility="visible",
        first_generated_at=created_at,
        last_generated_at=created_at,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(candidate)
    session.flush()
    return candidate


def _add_gsc_query(
    session,
    *,
    site_id: int,
    crawl_job_id: int,
    page_id: int,
    url: str,
    normalized_url: str,
    query: str,
) -> None:
    gsc_property = session.scalar(select(GscProperty).where(GscProperty.site_id == site_id))
    if gsc_property is None:
        gsc_property = GscProperty(
            site_id=site_id,
            property_uri="sc-domain:example.com",
            permission_level="siteOwner",
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        session.add(gsc_property)
        session.flush()

    session.add(
        GscTopQuery(
            gsc_property_id=gsc_property.id,
            crawl_job_id=crawl_job_id,
            page_id=page_id,
            url=url,
            normalized_url=normalized_url,
            date_range_label="last_28_days",
            query=query,
            clicks=5,
            impressions=70,
            ctr=0.07,
            position=8.0,
            fetched_at=FIXED_TIME,
            created_at=FIXED_TIME,
        )
    )
    session.flush()


def test_queue_review_run_freezes_candidate_and_context_hashes(sqlite_session_factory) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
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
        _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-b",
            candidate_input_hash="hash-b",
            topic_key="seo-audit",
            topic_label="SEO Audit",
        )
        _add_gsc_query(
            session,
            site_id=ids["site_id"],
            crawl_job_id=ids["crawl_a_id"],
            page_id=ids["page_a_id"],
            url="https://example.com/local-seo",
            normalized_url="https://example.com/local-seo",
            query="local seo services",
        )

        payload = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            output_language="pl",
        )
        session.commit()

        run = session.scalar(
            select(SiteContentGapReviewRun).where(SiteContentGapReviewRun.site_id == ids["site_id"])
        )

    assert payload["basis_crawl_job_id"] == ids["crawl_a_id"]
    assert payload["candidate_count"] == 2
    assert len(payload["selected_candidate_ids_json"]) == 2
    assert payload["candidate_set_hash"]
    assert payload["own_context_hash"]
    assert payload["gsc_context_hash"]
    assert payload["candidate_generation_version"] == CONTENT_GAP_CANDIDATE_GENERATION_VERSION
    assert payload["llm_model"] == get_settings().openai_model_competitor_merge
    assert payload["prompt_version"] == content_gap_review_run_service.CONTENT_GAP_REVIEW_PROMPT_VERSION
    assert payload["schema_version"] == content_gap_review_run_service.CONTENT_GAP_REVIEW_SCHEMA_VERSION
    assert payload["context_summary_json"]["has_gsc_context"] is True
    assert payload["context_summary_json"]["gsc_query_count"] == 1
    assert payload["output_language"] == "pl"
    assert run is not None
    assert run.basis_crawl_job_id == ids["crawl_a_id"]


def test_queue_review_run_uses_null_gsc_hash_when_snapshot_has_no_gsc(sqlite_session_factory) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
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
        payload = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
        )
        session.commit()

    assert payload["gsc_context_hash"] is None
    assert payload["context_summary_json"]["has_gsc_context"] is False
    assert payload["context_summary_json"]["gsc_query_count"] == 0


def test_queue_review_run_rejects_candidate_scope_from_other_snapshot(sqlite_session_factory) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    with sqlite_session_factory() as session:
        candidate_a = _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-a",
            candidate_input_hash="hash-a",
            topic_key="local-seo",
            topic_label="Local SEO",
        )
        _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_b_id"],
            candidate_key="gap-b",
            candidate_input_hash="hash-b",
            topic_key="seo-audit",
            topic_label="SEO Audit",
        )

        with pytest.raises(content_gap_review_run_service.ContentGapReviewRunServiceError) as exc_info:
            content_gap_review_run_service.queue_review_run(
                session,
                site_id=ids["site_id"],
                basis_crawl_job_id=ids["crawl_b_id"],
                selected_candidate_ids=[candidate_a.id],
            )

    assert exc_info.value.code == "candidate_scope_mismatch"


def test_queue_review_run_rejects_snapshot_without_current_candidates(sqlite_session_factory) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
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
        with pytest.raises(content_gap_review_run_service.ContentGapReviewRunServiceError) as exc_info:
            content_gap_review_run_service.queue_review_run(
                session,
                site_id=ids["site_id"],
                basis_crawl_job_id=ids["crawl_b_id"],
            )

    assert exc_info.value.code == "no_candidates"


def test_review_run_lifecycle_retry_and_stale(sqlite_session_factory, monkeypatch) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    monkeypatch.setattr(content_gap_review_run_service, "SessionLocal", sqlite_session_factory)

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
        queued = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
        )
        session.commit()

    with sqlite_session_factory() as session:
        claimed = content_gap_review_run_service.claim_review_run(
            session,
            site_id=ids["site_id"],
            run_id=queued["run_id"],
            lease_owner="worker-1",
        )
        assert claimed is True
        content_gap_review_run_service.touch_review_run(
            session,
            site_id=ids["site_id"],
            run_id=queued["run_id"],
            stage="prepare_context",
            completed_batch_count=0,
        )

    content_gap_review_run_service.complete_review_run(
        ids["site_id"],
        queued["run_id"],
        completed_batch_count=1,
    )

    with sqlite_session_factory() as session:
        completed = session.scalar(
            select(SiteContentGapReviewRun).where(
                SiteContentGapReviewRun.site_id == ids["site_id"],
                SiteContentGapReviewRun.run_id == queued["run_id"],
            )
        )
        assert completed is not None
        assert completed.status == "completed"
        assert completed.completed_batch_count == completed.batch_count

        second = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
        )
        session.commit()

    with sqlite_session_factory() as session:
        assert content_gap_review_run_service.claim_review_run(
            session,
            site_id=ids["site_id"],
            run_id=second["run_id"],
        )

    content_gap_review_run_service.fail_review_run(
        ids["site_id"],
        second["run_id"],
        error_code="review_failed",
        error_message_safe="Review failed.",
    )

    with sqlite_session_factory() as session:
        retry_payload = content_gap_review_run_service.retry_review_run(
            session,
            site_id=ids["site_id"],
            run_id=second["run_id"],
        )
        session.commit()

        failed = session.scalar(
            select(SiteContentGapReviewRun).where(
                SiteContentGapReviewRun.site_id == ids["site_id"],
                SiteContentGapReviewRun.run_id == second["run_id"],
            )
        )
        retry_run = session.scalar(
            select(SiteContentGapReviewRun).where(
                SiteContentGapReviewRun.site_id == ids["site_id"],
                SiteContentGapReviewRun.run_id == retry_payload["run_id"],
            )
        )
        assert failed is not None
        assert failed.status == "failed"
        assert retry_run is not None
        assert retry_run.retry_of_run_id == failed.id

        retry_run.status = "running"
        retry_run.stage = "prepare_context"
        retry_run.started_at = FIXED_TIME
        retry_run.lease_expires_at = FIXED_TIME - timedelta(seconds=1)
        retry_run.last_heartbeat_at = FIXED_TIME - timedelta(seconds=2)
        session.commit()

        stale_count = content_gap_review_run_service.reconcile_stale_review_runs(
            session,
            site_id=ids["site_id"],
        )
        session.commit()

        stale_run = session.scalar(
            select(SiteContentGapReviewRun).where(
                SiteContentGapReviewRun.site_id == ids["site_id"],
                SiteContentGapReviewRun.run_id == retry_payload["run_id"],
            )
        )

    assert stale_count == 1
    assert stale_run is not None
    assert stale_run.status == "stale"
    assert stale_run.error_code == content_gap_review_run_service.CONTENT_GAP_REVIEW_STALE_ERROR_CODE
