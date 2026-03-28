from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services import semstorm_brief_llm_service, semstorm_brief_service
from tests.test_semstorm_brief_service import _seed_plan_items


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _seed_brief_item(session_factory, monkeypatch) -> dict[str, int]:
    ids = _seed_plan_items(session_factory, monkeypatch)
    with session_factory() as session:
        created = semstorm_brief_service.create_semstorm_brief_items(
            session,
            ids["site_id"],
            plan_item_ids=[ids["local_seo_pricing_plan_id"]],
        )
        session.commit()
    ids["brief_id"] = int(created["items"][0]["id"])
    return ids


def test_mock_brief_enrichment_creates_run_and_apply_is_idempotent(sqlite_session_factory, monkeypatch) -> None:
    ids = _seed_brief_item(sqlite_session_factory, monkeypatch)
    monkeypatch.setenv("SEMSTORM_BRIEF_ENGINE_MODE", "mock")
    monkeypatch.setenv("SEMSTORM_BRIEF_LLM_ENABLED", "false")
    get_settings.cache_clear()

    with sqlite_session_factory() as session:
        enrichment_run = semstorm_brief_llm_service.enrich_semstorm_brief(
            session,
            ids["site_id"],
            ids["brief_id"],
        )
        first_apply = semstorm_brief_llm_service.apply_semstorm_brief_enrichment_run(
            session,
            ids["site_id"],
            ids["brief_id"],
            enrichment_run["id"],
        )
        second_apply = semstorm_brief_llm_service.apply_semstorm_brief_enrichment_run(
            session,
            ids["site_id"],
            ids["brief_id"],
            enrichment_run["id"],
        )
        listed_runs = semstorm_brief_llm_service.list_semstorm_brief_enrichment_runs(
            session,
            ids["site_id"],
            ids["brief_id"],
        )
        session.commit()

    assert enrichment_run["status"] == "completed"
    assert enrichment_run["engine_mode"] == "mock"
    assert enrichment_run["model_name"] == "mock-semstorm-brief-enrichment-v1"
    assert enrichment_run["suggestions"]["improved_brief_title"] == "Execution brief: Local SEO Pricing"
    assert enrichment_run["suggestions"]["editorial_notes"]

    assert first_apply["applied"] is True
    assert "brief_title" in first_apply["applied_fields"]
    assert "recommended_page_title" in first_apply["applied_fields"]
    assert "source_notes" in first_apply["applied_fields"]
    assert any(note.startswith("AI note:") for note in first_apply["brief"]["source_notes"])

    assert second_apply["applied"] is False
    assert second_apply["skipped_reason"] == "already_applied"
    assert listed_runs["summary"]["total_count"] == 1
    assert listed_runs["summary"]["completed_count"] == 1
    assert listed_runs["summary"]["applied_count"] == 1
    assert listed_runs["items"][0]["is_applied"] is True


class PartialOutputClient:
    def parse_chat_completion(self, **kwargs):
        response_format = kwargs["response_format"]
        return response_format(
            improved_brief_title="   ",
            improved_page_title="Local SEO Pricing Guide | Better Fit",
            improved_h1="",
            improved_angle_summary=" Refine the brief around clear pricing decisions and package comparison. ",
            improved_sections=["", "Pricing context", "Pricing context", "Package comparison"],
            improved_internal_link_targets=[
                "notaurl",
                "https://example.com/content-strategy",
                "https://example.com/content-strategy",
            ],
            editorial_notes=[" Lead with pricing clarity. ", ""],
            risk_flags=["Do not dilute the transactional intent."],
        )


def test_llm_brief_enrichment_normalizes_partial_usable_output(sqlite_session_factory, monkeypatch) -> None:
    ids = _seed_brief_item(sqlite_session_factory, monkeypatch)
    monkeypatch.setenv("SEMSTORM_BRIEF_ENGINE_MODE", "llm")
    monkeypatch.setenv("SEMSTORM_BRIEF_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SEMSTORM_BRIEF_LLM_MODEL", "gpt-5-mini")
    get_settings.cache_clear()

    with sqlite_session_factory() as session:
        enrichment_run = semstorm_brief_llm_service.enrich_semstorm_brief(
            session,
            ids["site_id"],
            ids["brief_id"],
            client=PartialOutputClient(),
        )
        session.commit()

    assert enrichment_run["status"] == "completed"
    assert enrichment_run["engine_mode"] == "llm"
    assert enrichment_run["model_name"] == "gpt-5-mini"
    assert enrichment_run["suggestions"]["improved_brief_title"] is None
    assert enrichment_run["suggestions"]["improved_page_title"] == "Local SEO Pricing Guide | Better Fit"
    assert enrichment_run["suggestions"]["improved_sections"] == ["Pricing context", "Package comparison"]
    assert enrichment_run["suggestions"]["improved_internal_link_targets"] == [
        "https://example.com/content-strategy"
    ]
    assert enrichment_run["suggestions"]["editorial_notes"] == ["Lead with pricing clarity."]
    assert enrichment_run["suggestions"]["risk_flags"] == ["Do not dilute the transactional intent."]


class EmptyOutputClient:
    def parse_chat_completion(self, **kwargs):
        response_format = kwargs["response_format"]
        return response_format()


def test_llm_brief_enrichment_rejects_empty_structured_output(sqlite_session_factory, monkeypatch) -> None:
    ids = _seed_brief_item(sqlite_session_factory, monkeypatch)
    monkeypatch.setenv("SEMSTORM_BRIEF_ENGINE_MODE", "llm")
    monkeypatch.setenv("SEMSTORM_BRIEF_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    with sqlite_session_factory() as session:
        with pytest.raises(semstorm_brief_llm_service.SemstormBriefLlmServiceError) as exc_info:
            semstorm_brief_llm_service.enrich_semstorm_brief(
                session,
                ids["site_id"],
                ids["brief_id"],
                client=EmptyOutputClient(),
            )
        session.commit()
        listed_runs = semstorm_brief_llm_service.list_semstorm_brief_enrichment_runs(
            session,
            ids["site_id"],
            ids["brief_id"],
        )

    assert exc_info.value.code == "no_usable_suggestions"
    assert listed_runs["summary"]["failed_count"] == 1
    assert listed_runs["items"][0]["status"] == "failed"
    assert listed_runs["items"][0]["error_code"] == "no_usable_suggestions"


def test_llm_brief_enrichment_surfaces_missing_api_key(sqlite_session_factory, monkeypatch) -> None:
    ids = _seed_brief_item(sqlite_session_factory, monkeypatch)
    monkeypatch.setenv("SEMSTORM_BRIEF_ENGINE_MODE", "llm")
    monkeypatch.setenv("SEMSTORM_BRIEF_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    with sqlite_session_factory() as session:
        with pytest.raises(semstorm_brief_llm_service.SemstormBriefLlmServiceError) as exc_info:
            semstorm_brief_llm_service.enrich_semstorm_brief(
                session,
                ids["site_id"],
                ids["brief_id"],
            )
        session.commit()
        listed_runs = semstorm_brief_llm_service.list_semstorm_brief_enrichment_runs(
            session,
            ids["site_id"],
            ids["brief_id"],
        )

    assert exc_info.value.code == "missing_api_key"
    assert listed_runs["summary"]["failed_count"] == 1
    assert listed_runs["items"][0]["error_code"] == "missing_api_key"
