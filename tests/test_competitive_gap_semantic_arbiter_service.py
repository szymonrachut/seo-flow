from __future__ import annotations

import json
from datetime import timedelta, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import (
    SiteCompetitorPage,
    SiteCompetitorSemanticCandidate,
    SiteCompetitorSemanticDecision,
    SiteCompetitorSemanticRun,
)
from app.services import (
    competitive_gap_semantic_arbiter_service,
    competitive_gap_semantic_run_service,
    competitive_gap_semantic_service,
)
from tests.competitive_gap_test_utils import seed_competitive_gap_site


class FakeSemanticClient:
    provider_name = "openai"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def is_available(self) -> bool:
        return True

    def parse_chat_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_format,
        max_completion_tokens: int,
        reasoning_effort: str | None = None,
        verbosity: str = "low",
    ):
        payload = json.loads(user_prompt)
        self.calls.append(
            {
                "model": model,
                "system_prompt": system_prompt,
                "task": payload["task"],
                "max_completion_tokens": max_completion_tokens,
                "reasoning_effort": reasoning_effort,
                "verbosity": verbosity,
            }
        )
        if payload["task"] == "competitor_topic_merge":
            decisions = []
            for candidate in payload["candidates"]:
                signals = candidate["deterministic_signals"]
                relation = "same_topic" if signals["exact_topic_key_match"] else "related_subtopic"
                decisions.append(
                    {
                        "candidate_index": candidate["candidate_index"],
                        "relation": relation,
                        "confidence": 0.81 if relation == "same_topic" else 0.68,
                        "merge_rationale": f"Deterministic overlap suggests {relation}.",
                    }
                )
            return response_format(
                canonical_topic_label=payload["source_topic"]["raw_topic_label"],
                decisions=decisions,
            )
        decisions = []
        for candidate in payload["candidates"]:
            signals = candidate["deterministic_signals"]
            if signals["exact_topic_key_match"]:
                relation = "exact_match"
                confidence = 0.9
            elif signals["shared_primary_tokens"] >= 1:
                relation = "semantic_match"
                confidence = 0.74
            else:
                relation = "no_meaningful_match"
                confidence = 0.36
            decisions.append(
                {
                    "candidate_index": candidate["candidate_index"],
                    "relation": relation,
                    "confidence": confidence,
                    "match_rationale": f"Deterministic overlap suggests {relation}.",
                }
            )
        return response_format(
            canonical_topic_label=payload["source_topic"]["raw_topic_label"],
            decisions=decisions,
        )


def _prepare_semantic_foundation(sqlite_session_factory) -> dict[str, int]:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    with sqlite_session_factory() as session:
        competitor_ids = [ids["competitor_a_id"], ids["competitor_b_id"]]
        for competitor_id in competitor_ids:
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
    return ids


def test_run_competitor_semantic_arbiter_persists_decisions_and_reuses_cache(sqlite_session_factory) -> None:
    ids = _prepare_semantic_foundation(sqlite_session_factory)
    client = FakeSemanticClient()

    with sqlite_session_factory() as session:
        first = competitive_gap_semantic_arbiter_service.run_competitor_semantic_arbiter(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            mode="full",
            active_crawl_id=ids["crawl_job_id"],
            client=client,
        )
        session.commit()

        assert first.semantic_candidates_count >= 1
        assert first.semantic_llm_jobs_count >= 1
        assert first.semantic_resolved_count == first.semantic_candidates_count
        assert first.semantic_cache_hits == 0

        decisions = session.scalars(
            select(SiteCompetitorSemanticDecision)
            .where(SiteCompetitorSemanticDecision.site_id == ids["site_id"])
            .order_by(SiteCompetitorSemanticDecision.id.asc())
        ).all()
        assert decisions
        assert any(row.decision_type == "merge" for row in decisions)
        assert any(row.decision_type == "own_match" for row in decisions)
        assert all(row.canonical_topic_label for row in decisions)

        with sqlite_session_factory() as session:
            second = competitive_gap_semantic_arbiter_service.run_competitor_semantic_arbiter(
                session,
                site_id=ids["site_id"],
                competitor_id=ids["competitor_a_id"],
                mode="incremental",
                active_crawl_id=ids["crawl_job_id"],
                source_candidate_ids=list(first.source_candidate_ids),
                client=client,
            )
            session.commit()

        assert second.semantic_llm_jobs_count == 0
        assert second.semantic_cache_hits >= first.semantic_candidates_count
        assert second.semantic_fallback_count == 0


def test_run_competitor_semantic_arbiter_falls_back_when_llm_is_unavailable(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _prepare_semantic_foundation(sqlite_session_factory)
    monkeypatch.setenv("OPENAI_LLM_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    with sqlite_session_factory() as session:
        result = competitive_gap_semantic_arbiter_service.run_competitor_semantic_arbiter(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            mode="full",
            active_crawl_id=ids["crawl_job_id"],
        )
        session.commit()

        assert result.semantic_candidates_count >= 1
        assert result.semantic_fallback_count >= 1
        assert result.semantic_llm_jobs_count == 0

        fallback_rows = session.scalars(
            select(SiteCompetitorSemanticDecision)
            .where(
                SiteCompetitorSemanticDecision.site_id == ids["site_id"],
                SiteCompetitorSemanticDecision.fallback_used.is_(True),
            )
        ).all()
        assert fallback_rows
    get_settings.cache_clear()


def test_run_competitor_semantic_arbiter_emits_stage_heartbeats_during_persisted_run(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _prepare_semantic_foundation(sqlite_session_factory)
    client = FakeSemanticClient()

    with sqlite_session_factory() as session:
        candidate_ids = session.scalars(
            select(SiteCompetitorSemanticCandidate.id)
            .where(
                SiteCompetitorSemanticCandidate.competitor_id == ids["competitor_a_id"],
                SiteCompetitorSemanticCandidate.current.is_(True),
            )
            .order_by(SiteCompetitorSemanticCandidate.id.asc())
        ).all()
        queued_run = competitive_gap_semantic_run_service.queue_semantic_run(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            trigger_source="manual_full",
            mode="full",
            active_crawl_id=ids["crawl_job_id"],
            source_candidate_ids=candidate_ids,
            llm_provider="openai",
            llm_model="gpt-5.4-mini",
            prompt_version=competitive_gap_semantic_arbiter_service.SEMANTIC_ARBITER_PROMPT_VERSION,
        )
        session.commit()

    with sqlite_session_factory() as session:
        claimed = competitive_gap_semantic_run_service.claim_semantic_run(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            run_id=queued_run["run_id"],
        )
        assert claimed is True

    captured_stages: list[str] = []
    original_touch = competitive_gap_semantic_run_service.touch_semantic_run

    def recording_touch(*args, **kwargs):
        captured_stages.append(str(kwargs.get("stage")))
        return original_touch(*args, **kwargs)

    monkeypatch.setattr(competitive_gap_semantic_run_service, "touch_semantic_run", recording_touch)

    with sqlite_session_factory() as session:
        result = competitive_gap_semantic_arbiter_service.run_competitor_semantic_arbiter(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            semantic_run_id=queued_run["run_id"],
            persist_progress=True,
            client=client,
        )
        session.commit()

    assert result.semantic_candidates_count >= 1
    assert "prepare_candidates" in captured_stages
    assert "own_semantic_profiling" in captured_stages
    assert "merge_topics" in captured_stages
    assert "canonicalization" in captured_stages
    assert "cluster_to_own_match" in captured_stages
    assert "cluster_build" in captured_stages
    assert "final_synthesis" in captured_stages


def test_run_competitor_semantic_arbiter_respects_requested_output_language(sqlite_session_factory) -> None:
    get_settings.cache_clear()
    ids = _prepare_semantic_foundation(sqlite_session_factory)
    client = FakeSemanticClient()

    with sqlite_session_factory() as session:
        result = competitive_gap_semantic_arbiter_service.run_competitor_semantic_arbiter(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            mode="full",
            active_crawl_id=ids["crawl_job_id"],
            client=client,
            output_language="pl",
        )
        session.commit()

    assert result.semantic_llm_jobs_count >= 1
    assert result.llm_model == "gpt-5.4-mini"
    assert all(str(call["model"]) == "gpt-5.4-mini" for call in client.calls)
    assert any("Polish" in str(call["system_prompt"]) for call in client.calls)
    get_settings.cache_clear()


def test_queued_semantic_run_waits_longer_than_running_lease_before_stale(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _prepare_semantic_foundation(sqlite_session_factory)

    with sqlite_session_factory() as session:
        candidate_ids = session.scalars(
            select(SiteCompetitorSemanticCandidate.id)
            .where(
                SiteCompetitorSemanticCandidate.competitor_id == ids["competitor_a_id"],
                SiteCompetitorSemanticCandidate.current.is_(True),
            )
            .order_by(SiteCompetitorSemanticCandidate.id.asc())
        ).all()
        queued_run = competitive_gap_semantic_run_service.queue_semantic_run(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            trigger_source="manual_full",
            mode="full",
            active_crawl_id=ids["crawl_job_id"],
            source_candidate_ids=candidate_ids,
            llm_provider="openai",
            llm_model="gpt-5.4-mini",
            prompt_version=competitive_gap_semantic_arbiter_service.SEMANTIC_ARBITER_PROMPT_VERSION,
        )
        session.commit()

    with sqlite_session_factory() as session:
        run = session.scalars(
            select(SiteCompetitorSemanticRun)
            .where(
                SiteCompetitorSemanticRun.site_id == ids["site_id"],
                SiteCompetitorSemanticRun.competitor_id == ids["competitor_a_id"],
                SiteCompetitorSemanticRun.run_id == queued_run["run_id"],
            )
            .limit(1)
        ).first()
        assert run is not None
        queued_at = run.last_heartbeat_at
        assert queued_at is not None
        assert run.lease_expires_at is not None
        assert run.status == "queued"
        assert (run.lease_expires_at - queued_at) >= timedelta(
            seconds=competitive_gap_semantic_run_service.DEFAULT_SEMANTIC_QUEUED_LEASE_SECONDS - 1,
        )
        queued_reference = queued_at if queued_at.tzinfo is not None else queued_at.replace(tzinfo=timezone.utc)

    monkeypatch.setattr(
        competitive_gap_semantic_run_service,
        "utcnow",
        lambda: queued_reference
        + timedelta(seconds=competitive_gap_semantic_run_service.DEFAULT_SEMANTIC_RUNNING_LEASE_SECONDS + 5),
    )

    with sqlite_session_factory() as session:
        touched = competitive_gap_semantic_run_service.reconcile_stale_semantic_runs(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
        )
        session.commit()
        assert touched == 0
        run = session.scalars(
            select(SiteCompetitorSemanticRun)
            .where(
                SiteCompetitorSemanticRun.site_id == ids["site_id"],
                SiteCompetitorSemanticRun.competitor_id == ids["competitor_a_id"],
                SiteCompetitorSemanticRun.run_id == queued_run["run_id"],
            )
            .limit(1)
        ).first()
        assert run is not None
        assert run.status == "queued"
