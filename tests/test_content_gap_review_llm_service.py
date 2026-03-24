from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.db.models import SiteContentGapItem, SiteContentGapReviewRun
from app.services import content_gap_review_llm_service, content_gap_review_run_service
from tests.test_content_gap_review_run_service import (
    _add_candidate,
    _add_gsc_query,
    _seed_site_with_two_crawls,
)


class _RecordingReviewClient:
    provider_name = "openai-test"

    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = list(payloads)
        self.user_payloads: list[dict] = []

    def is_available(self) -> bool:
        return True

    def parse_chat_completion(
        self,
        *,
        user_prompt: str,
        response_format,
        **_: object,
    ):
        self.user_payloads.append(json.loads(user_prompt))
        if not self._payloads:
            raise AssertionError("No fake LLM payload configured for this batch.")
        return response_format.model_validate(self._payloads.pop(0))


def test_execute_review_run_completes_and_materializes_items(sqlite_session_factory) -> None:
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
        candidate_b = _add_candidate(
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
        _add_gsc_query(
            session,
            site_id=ids["site_id"],
            crawl_job_id=ids["crawl_b_id"],
            page_id=ids["page_b_id"],
            url="https://example.com/seo-audit",
            normalized_url="https://example.com/seo-audit",
            query="seo audit checklist",
        )
        queued_run = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            batch_size=1,
        )
        session.commit()

    fake_client = _RecordingReviewClient(
        [
            {
                "decisions": [
                    {
                        "candidate_index": 1,
                        "decision_action": "keep",
                        "fit_score": 92,
                        "confidence": 0.87,
                        "decision_reason_text": "Strong match for the site's offer.",
                        "reviewed_phrase": "Local SEO",
                        "reviewed_topic_label": "Local SEO",
                        "reviewed_normalized_topic_key": "local-seo",
                        "reviewed_gap_type": "NEW_TOPIC",
                        "own_site_alignment_summary": ["https://example.com/local-seo"],
                        "gsc_support_summary": ["local seo services"],
                        "competitor_evidence_summary": ["2 competitor pages"],
                    }
                ]
            },
            {
                "decisions": [
                    {
                        "candidate_index": 1,
                        "decision_action": "rewrite",
                        "fit_score": 76,
                        "confidence": 0.81,
                        "decision_reason_text": "Narrow the topic phrasing.",
                        "reviewed_phrase": "SEO audit process",
                        "reviewed_topic_label": "SEO Audit Process",
                        "reviewed_normalized_topic_key": "seo-audit-process",
                        "reviewed_gap_type": "EXPAND_TOPIC",
                        "rewrite_reason_text": "Makes the topic more specific.",
                        "own_site_alignment_summary": ["https://example.com/local-seo"],
                        "competitor_evidence_summary": ["2 competitor pages"],
                    }
                ]
            },
        ]
    )

    with sqlite_session_factory() as session:
        result = content_gap_review_llm_service.execute_review_run(
            session,
            site_id=ids["site_id"],
            run_id=queued_run["run_id"],
            client=fake_client,
            lease_owner="test-worker",
        )

    with sqlite_session_factory() as session:
        run = session.scalar(
            select(SiteContentGapReviewRun).where(
                SiteContentGapReviewRun.site_id == ids["site_id"],
                SiteContentGapReviewRun.run_id == queued_run["run_id"],
            )
        )
        items = session.scalars(
            select(SiteContentGapItem)
            .where(SiteContentGapItem.review_run_id == queued_run["id"])
            .order_by(SiteContentGapItem.source_candidate_id.asc())
        ).all()

    assert result.run_id == queued_run["run_id"]
    assert result.batch_count == 2
    assert result.materialized_item_count == 2
    assert run is not None
    assert run.status == "completed"
    assert run.completed_batch_count == run.batch_count == 2
    assert len(items) == 2
    assert all(item.basis_crawl_job_id == ids["crawl_a_id"] for item in items)
    assert items[0].decision_action == "keep"
    assert items[1].decision_action == "rewrite"

    serialized_payload = json.dumps(fake_client.user_payloads)
    assert "local seo services" in serialized_payload
    assert "seo audit checklist" not in serialized_payload


def test_execute_review_run_fails_without_partial_item_write_on_scope_mismatch(sqlite_session_factory) -> None:
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
        queued_run = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            batch_size=1,
        )
        session.commit()

    fake_client = _RecordingReviewClient(
        [
            {
                "decisions": [
                    {
                        "candidate_index": 1,
                        "decision_action": "keep",
                        "fit_score": 90,
                        "confidence": 0.85,
                        "decision_reason_text": "Strong fit.",
                    }
                ]
            },
            {
                "decisions": [
                    {
                        "candidate_index": 2,
                        "decision_action": "keep",
                        "fit_score": 82,
                        "confidence": 0.8,
                        "decision_reason_text": "Scope mismatch.",
                    }
                ]
            },
        ]
    )

    with sqlite_session_factory() as session:
        with pytest.raises(content_gap_review_llm_service.ContentGapReviewLlmServiceError) as exc_info:
            content_gap_review_llm_service.execute_review_run(
                session,
                site_id=ids["site_id"],
                run_id=queued_run["run_id"],
                client=fake_client,
                lease_owner="test-worker",
            )

    with sqlite_session_factory() as session:
        run = session.scalar(
            select(SiteContentGapReviewRun).where(
                SiteContentGapReviewRun.site_id == ids["site_id"],
                SiteContentGapReviewRun.run_id == queued_run["run_id"],
            )
        )
        items = session.scalars(
            select(SiteContentGapItem).where(SiteContentGapItem.review_run_id == queued_run["id"])
        ).all()

    assert exc_info.value.code == "batch_scope_mismatch"
    assert run is not None
    assert run.status == "failed"
    assert run.error_code == "batch_scope_mismatch"
    assert items == []


def test_review_batch_prompt_and_materialized_fields_preserve_polish_diacritics(sqlite_session_factory) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    with sqlite_session_factory() as session:
        _add_candidate(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            candidate_key="gap-pl",
            candidate_input_hash="hash-pl",
            topic_key="pozycjonowanie-lokalne",
            topic_label="Pozycjonowanie lokalne",
        )
        _add_gsc_query(
            session,
            site_id=ids["site_id"],
            crawl_job_id=ids["crawl_a_id"],
            page_id=ids["page_a_id"],
            url="https://example.com/pozycjonowanie-lokalne",
            normalized_url="https://example.com/pozycjonowanie-lokalne",
            query="pozycjonowanie lokalne łódź",
        )
        queued_run = content_gap_review_run_service.queue_review_run(
            session,
            site_id=ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            batch_size=1,
            output_language="pl",
        )
        session.commit()

    fake_client = _RecordingReviewClient(
        [
            {
                "decisions": [
                    {
                        "candidate_index": 1,
                        "decision_action": "rewrite",
                        "fit_score": 88,
                        "confidence": 0.91,
                        "decision_reason_text": "Temat dobrze pasuje do oferty w Łodzi.",
                        "reviewed_phrase": "Pozycjonowanie lokalne w Łodzi",
                        "reviewed_topic_label": "Pozycjonowanie lokalne w Łodzi",
                        "reviewed_normalized_topic_key": "pozycjonowanie-lokalne-w-lodzi",
                        "reviewed_gap_type": "NEW_TOPIC",
                        "rewrite_reason_text": "Doprecyzowuje frazę z polskimi znakami.",
                        "gsc_support_summary": ["pozycjonowanie lokalne łódź"],
                    }
                ]
            }
        ]
    )

    with sqlite_session_factory() as session:
        content_gap_review_llm_service.execute_review_run(
            session,
            site_id=ids["site_id"],
            run_id=queued_run["run_id"],
            client=fake_client,
            lease_owner="test-worker",
        )

    prompt_payload = fake_client.user_payloads[0]
    serialized_prompt = json.dumps(prompt_payload, ensure_ascii=False)
    assert "pozycjonowanie lokalne łódź" in serialized_prompt

    with sqlite_session_factory() as session:
        item = session.scalar(
            select(SiteContentGapItem).where(SiteContentGapItem.review_run_id == queued_run["id"])
        )

    assert item is not None
    assert item.reviewed_phrase == "Pozycjonowanie lokalne w Łodzi"
    assert item.reviewed_topic_label == "Pozycjonowanie lokalne w Łodzi"
    assert item.decision_reason_text == "Temat dobrze pasuje do oferty w Łodzi."
    assert item.rewrite_reason_text == "Doprecyzowuje frazę z polskimi znakami."
