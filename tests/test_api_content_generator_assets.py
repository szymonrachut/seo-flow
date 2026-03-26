from __future__ import annotations

from sqlalchemy import select

from app.db.models import CrawlJob, SiteContentGeneratorAsset
from app.services import content_generator_prompt_service, content_generator_service
from app.services.content_generator_prompt_service import CONTENT_GENERATOR_PROMPT_VERSION, GeneratedContentAssets
from tests.test_content_generator_service import (
    FIXED_TIME,
    _seed_content_generator_site,
    _valid_details_to_include,
    _valid_hook_brief,
    _valid_surfer_instructions,
)


def test_get_site_content_generator_assets_returns_existing_asset(api_client, sqlite_session_factory) -> None:
    ids = _seed_content_generator_site(sqlite_session_factory)
    with sqlite_session_factory() as session:
        session.add(
            SiteContentGeneratorAsset(
                site_id=ids["site_id"],
                basis_crawl_job_id=ids["active_crawl_id"],
                status="ready",
                surfer_custom_instructions="Persisted instructions",
                seowriting_details_to_include="Persisted details",
                introductory_hook_brief="Persisted hook",
                source_urls_json=["https://example.com/", "https://example.com/kontakt"],
                source_pages_hash="hash-123",
                prompt_version=CONTENT_GENERATOR_PROMPT_VERSION,
                llm_provider="openai",
                llm_model="gpt-5.4-mini",
                generated_at=FIXED_TIME,
                created_at=FIXED_TIME,
                updated_at=FIXED_TIME,
            )
        )
        session.commit()

    response = api_client.get(f"/sites/{ids['site_id']}/content-generator-assets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["site_id"] == ids["site_id"]
    assert payload["has_assets"] is True
    assert payload["can_regenerate"] is True
    assert payload["active_crawl_id"] == ids["active_crawl_id"]
    assert payload["active_crawl_status"] == "finished"
    assert payload["status"] == "ready"
    assert payload["basis_crawl_job_id"] == ids["active_crawl_id"]
    assert payload["source_urls"] == ["https://example.com/", "https://example.com/kontakt"]
    assert payload["source_pages_hash"] == "hash-123"


def test_get_site_content_generator_assets_returns_empty_state_without_asset(api_client, sqlite_session_factory) -> None:
    ids = _seed_content_generator_site(sqlite_session_factory)

    response = api_client.get(f"/sites/{ids['site_id']}/content-generator-assets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["site_id"] == ids["site_id"]
    assert payload["has_assets"] is False
    assert payload["can_regenerate"] is True
    assert payload["active_crawl_id"] == ids["active_crawl_id"]
    assert payload["status"] is None
    assert payload["basis_crawl_job_id"] is None
    assert payload["source_urls"] == []


def test_post_generate_regenerates_existing_singleton(api_client, sqlite_session_factory, monkeypatch) -> None:
    ids = _seed_content_generator_site(sqlite_session_factory)
    generated_languages: list[str] = []
    used_basis_crawls: list[int] = []

    with sqlite_session_factory() as session:
        session.add(
            SiteContentGeneratorAsset(
                site_id=ids["site_id"],
                basis_crawl_job_id=ids["old_crawl_id"],
                status="ready",
                surfer_custom_instructions="Old instructions",
                seowriting_details_to_include="Old details",
                introductory_hook_brief="Old hook",
                source_urls_json=["https://example.com/legacy-service"],
                source_pages_hash="old-hash",
                prompt_version="old-version",
                llm_provider="openai",
                llm_model="old-model",
                generated_at=FIXED_TIME,
                created_at=FIXED_TIME,
                updated_at=FIXED_TIME,
            )
        )
        session.commit()

    def fake_generate_content_assets(context, *, client=None, output_language="en"):
        generated_languages.append(output_language)
        used_basis_crawls.append(context.basis_crawl_job_id)
        return GeneratedContentAssets(
            surfer_custom_instructions=_valid_surfer_instructions(),
            seowriting_details_to_include=_valid_details_to_include(),
            introductory_hook_brief=_valid_hook_brief(),
            llm_provider="openai-test",
            llm_model="gpt-5.4-mini",
            prompt_version=CONTENT_GENERATOR_PROMPT_VERSION,
        )

    monkeypatch.setattr(content_generator_prompt_service, "generate_content_assets", fake_generate_content_assets)

    response = api_client.post(
        f"/sites/{ids['site_id']}/content-generator-assets/generate",
        json={"output_language": "pl"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["generation_triggered"] is True
    assert payload["error_code"] is None
    assert payload["asset"]["status"] == "ready"
    assert payload["asset"]["basis_crawl_job_id"] == ids["active_crawl_id"]
    assert payload["asset"]["llm_provider"] == "openai-test"
    assert generated_languages == ["pl"]
    assert used_basis_crawls == [ids["active_crawl_id"]]

    with sqlite_session_factory() as session:
        asset = session.scalar(
            select(SiteContentGeneratorAsset).where(SiteContentGeneratorAsset.site_id == ids["site_id"])
        )

    assert asset is not None
    assert asset.basis_crawl_job_id == ids["active_crawl_id"]
    assert asset.status == "ready"
    assert asset.surfer_custom_instructions == _valid_surfer_instructions()
    assert asset.llm_provider == "openai-test"


def test_auto_generate_first_site_content_assets_for_crawl_creates_first_asset(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_content_generator_site(sqlite_session_factory)
    used_languages: list[str] = []

    def fake_generate_content_assets(context, *, client=None, output_language="en"):
        used_languages.append(output_language)
        return GeneratedContentAssets(
            surfer_custom_instructions=_valid_surfer_instructions(),
            seowriting_details_to_include=_valid_details_to_include(),
            introductory_hook_brief=_valid_hook_brief(),
            llm_provider="openai-auto",
            llm_model="gpt-5.4-mini",
            prompt_version=CONTENT_GENERATOR_PROMPT_VERSION,
        )

    monkeypatch.setattr(content_generator_service, "SessionLocal", sqlite_session_factory)
    monkeypatch.setattr(content_generator_prompt_service, "generate_content_assets", fake_generate_content_assets)

    summary = content_generator_service.auto_generate_first_site_content_assets_for_crawl(
        ids["active_crawl_id"],
        output_language="pl",
    )

    assert summary["triggered"] is True
    assert summary["success"] is True
    assert summary["skip_reason"] is None
    assert summary["site_id"] == ids["site_id"]
    assert summary["basis_crawl_job_id"] == ids["active_crawl_id"]
    assert used_languages == ["pl"]

    with sqlite_session_factory() as session:
        asset = session.scalar(
            select(SiteContentGeneratorAsset).where(SiteContentGeneratorAsset.site_id == ids["site_id"])
        )

    assert asset is not None
    assert asset.status == "ready"
    assert asset.basis_crawl_job_id == ids["active_crawl_id"]


def test_auto_generate_first_site_content_assets_for_crawl_does_not_overwrite_existing_asset(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_content_generator_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        session.add(
            SiteContentGeneratorAsset(
                site_id=ids["site_id"],
                basis_crawl_job_id=ids["old_crawl_id"],
                status="ready",
                surfer_custom_instructions="Existing instructions",
                seowriting_details_to_include="Existing details",
                introductory_hook_brief="Existing hook",
                source_urls_json=["https://example.com/legacy-service"],
                source_pages_hash="existing-hash",
                prompt_version="old-version",
                llm_provider="openai",
                llm_model="old-model",
                generated_at=FIXED_TIME,
                created_at=FIXED_TIME,
                updated_at=FIXED_TIME,
            )
        )
        session.commit()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Auto-generation should not run when an asset already exists.")

    monkeypatch.setattr(content_generator_service, "SessionLocal", sqlite_session_factory)
    monkeypatch.setattr(content_generator_prompt_service, "generate_content_assets", fail_if_called)

    summary = content_generator_service.auto_generate_first_site_content_assets_for_crawl(ids["active_crawl_id"])

    assert summary["triggered"] is False
    assert summary["skip_reason"] == "asset_exists"
    assert summary["basis_crawl_job_id"] == ids["old_crawl_id"]

    with sqlite_session_factory() as session:
        asset = session.scalar(
            select(SiteContentGeneratorAsset).where(SiteContentGeneratorAsset.site_id == ids["site_id"])
        )

    assert asset is not None
    assert asset.basis_crawl_job_id == ids["old_crawl_id"]
    assert asset.surfer_custom_instructions == "Existing instructions"


def test_auto_generate_first_site_content_assets_for_crawl_persists_failed_asset_without_breaking_crawl(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_content_generator_site(sqlite_session_factory)

    def fake_generate_content_assets(*args, **kwargs):
        raise content_generator_prompt_service.ContentGeneratorPromptServiceError(
            "LLM provider failed.",
            code="provider_error",
        )

    monkeypatch.setattr(content_generator_service, "SessionLocal", sqlite_session_factory)
    monkeypatch.setattr(content_generator_prompt_service, "generate_content_assets", fake_generate_content_assets)

    summary = content_generator_service.auto_generate_first_site_content_assets_for_crawl(ids["active_crawl_id"])

    assert summary["triggered"] is True
    assert summary["success"] is False
    assert summary["error_code"] == "provider_error"
    assert summary["asset_status"] == "failed"

    with sqlite_session_factory() as session:
        asset = session.scalar(
            select(SiteContentGeneratorAsset).where(SiteContentGeneratorAsset.site_id == ids["site_id"])
        )
        crawl_status = session.execute(
            select(CrawlJob.status).where(CrawlJob.id == ids["active_crawl_id"])
        ).scalar_one()

    assert asset is not None
    assert asset.status == "failed"
    assert asset.basis_crawl_job_id == ids["active_crawl_id"]
    assert asset.last_error_code == "provider_error"
    assert asset.generated_at is None
    assert str(getattr(crawl_status, "value", crawl_status)) == "finished"
