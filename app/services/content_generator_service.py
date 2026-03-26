from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import SiteContentGeneratorAsset
from app.db.session import SessionLocal
from app.integrations.openai.client import OpenAiLlmClient
from app.services import content_generator_context_service, content_generator_prompt_service


class ContentGeneratorServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "content_generator_service_error") -> None:
        super().__init__(message)
        self.code = code


def get_site_content_generator_asset(session: Session, site_id: int) -> dict[str, Any] | None:
    asset = _load_asset(session, site_id=site_id)
    if asset is None:
        return None
    return _serialize_asset(asset)


def generate_site_content_assets(
    session: Session,
    *,
    site_id: int,
    active_crawl_id: int | None = None,
    output_language: str = "en",
    client: OpenAiLlmClient | None = None,
) -> dict[str, Any]:
    resolved_client = client or OpenAiLlmClient()
    settings = get_settings()

    try:
        context = content_generator_context_service.build_content_generator_prompt_context(
            session,
            site_id=site_id,
            active_crawl_id=active_crawl_id,
        )
    except content_generator_context_service.ContentGeneratorContextServiceError as exc:
        raise ContentGeneratorServiceError(str(exc), code=exc.code) from exc

    asset = _get_or_create_asset(
        session,
        site_id=site_id,
        basis_crawl_job_id=context.basis_crawl_job_id,
    )
    _mark_asset_running(
        asset,
        basis_crawl_job_id=context.basis_crawl_job_id,
        source_urls=context.source_urls,
        source_pages_hash=context.source_pages_hash,
        llm_provider=getattr(resolved_client, "provider_name", None),
        llm_model=settings.openai_model_content_generator,
    )
    session.commit()

    try:
        generated = content_generator_prompt_service.generate_content_assets(
            context,
            client=resolved_client,
            output_language=output_language,
        )
    except content_generator_prompt_service.ContentGeneratorPromptServiceError as exc:
        session.rollback()
        failed_asset = _load_asset_or_raise(session, site_id=site_id)
        _mark_asset_failed(
            failed_asset,
            basis_crawl_job_id=context.basis_crawl_job_id,
            source_urls=context.source_urls,
            source_pages_hash=context.source_pages_hash,
            llm_provider=getattr(resolved_client, "provider_name", None),
            llm_model=settings.openai_model_content_generator,
            error=ContentGeneratorServiceError(str(exc), code=exc.code),
        )
        session.commit()
        raise ContentGeneratorServiceError(str(exc), code=exc.code) from exc
    except Exception as exc:
        session.rollback()
        failed_asset = _load_asset_or_raise(session, site_id=site_id)
        normalized_error = ContentGeneratorServiceError(
            str(exc) or "Content asset generation failed.",
            code=getattr(exc, "code", "content_generator_execution_failed"),
        )
        _mark_asset_failed(
            failed_asset,
            basis_crawl_job_id=context.basis_crawl_job_id,
            source_urls=context.source_urls,
            source_pages_hash=context.source_pages_hash,
            llm_provider=getattr(resolved_client, "provider_name", None),
            llm_model=settings.openai_model_content_generator,
            error=normalized_error,
        )
        session.commit()
        raise normalized_error from exc

    ready_asset = _load_asset_or_raise(session, site_id=site_id)
    _mark_asset_ready(ready_asset, generated=generated)
    session.commit()
    return _serialize_asset(ready_asset)


def generate_site_content_assets_task(
    *,
    site_id: int,
    active_crawl_id: int | None = None,
    output_language: str = "en",
) -> dict[str, Any]:
    session = SessionLocal()
    try:
        return generate_site_content_assets(
            session,
            site_id=site_id,
            active_crawl_id=active_crawl_id,
            output_language=output_language,
        )
    finally:
        session.close()


def _get_or_create_asset(session: Session, *, site_id: int, basis_crawl_job_id: int) -> SiteContentGeneratorAsset:
    asset = _load_asset(session, site_id=site_id)
    if asset is not None:
        return asset
    asset = SiteContentGeneratorAsset(
        site_id=site_id,
        basis_crawl_job_id=basis_crawl_job_id,
    )
    session.add(asset)
    session.flush()
    return asset


def _load_asset(session: Session, *, site_id: int) -> SiteContentGeneratorAsset | None:
    return session.scalar(
        select(SiteContentGeneratorAsset)
        .where(SiteContentGeneratorAsset.site_id == site_id)
        .limit(1)
    )


def _load_asset_or_raise(session: Session, *, site_id: int) -> SiteContentGeneratorAsset:
    asset = _load_asset(session, site_id=site_id)
    if asset is None:
        raise ContentGeneratorServiceError(
            f"SiteContentGeneratorAsset for site {site_id} was not found.",
            code="content_generator_asset_not_found",
        )
    return asset


def _mark_asset_running(
    asset: SiteContentGeneratorAsset,
    *,
    basis_crawl_job_id: int,
    source_urls: list[str],
    source_pages_hash: str,
    llm_provider: str | None,
    llm_model: str | None,
) -> None:
    asset.basis_crawl_job_id = basis_crawl_job_id
    asset.status = "running"
    asset.surfer_custom_instructions = None
    asset.seowriting_details_to_include = None
    asset.introductory_hook_brief = None
    asset.source_urls_json = list(source_urls)
    asset.source_pages_hash = source_pages_hash
    asset.prompt_version = content_generator_prompt_service.CONTENT_GENERATOR_PROMPT_VERSION
    asset.llm_provider = llm_provider
    asset.llm_model = llm_model
    asset.generated_at = None
    asset.last_error_code = None
    asset.last_error_message = None


def _mark_asset_ready(
    asset: SiteContentGeneratorAsset,
    *,
    generated: content_generator_prompt_service.GeneratedContentAssets,
) -> None:
    asset.status = "ready"
    asset.surfer_custom_instructions = generated.surfer_custom_instructions
    asset.seowriting_details_to_include = generated.seowriting_details_to_include
    asset.introductory_hook_brief = generated.introductory_hook_brief
    asset.prompt_version = generated.prompt_version
    asset.llm_provider = generated.llm_provider
    asset.llm_model = generated.llm_model
    asset.generated_at = datetime.now(timezone.utc)
    asset.last_error_code = None
    asset.last_error_message = None


def _mark_asset_failed(
    asset: SiteContentGeneratorAsset,
    *,
    basis_crawl_job_id: int,
    source_urls: list[str],
    source_pages_hash: str,
    llm_provider: str | None,
    llm_model: str | None,
    error: ContentGeneratorServiceError,
) -> None:
    asset.basis_crawl_job_id = basis_crawl_job_id
    asset.status = "failed"
    asset.surfer_custom_instructions = None
    asset.seowriting_details_to_include = None
    asset.introductory_hook_brief = None
    asset.source_urls_json = list(source_urls)
    asset.source_pages_hash = source_pages_hash
    asset.prompt_version = content_generator_prompt_service.CONTENT_GENERATOR_PROMPT_VERSION
    asset.llm_provider = llm_provider
    asset.llm_model = llm_model
    asset.generated_at = None
    asset.last_error_code = error.code
    asset.last_error_message = str(error)


def _serialize_asset(asset: SiteContentGeneratorAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "site_id": asset.site_id,
        "basis_crawl_job_id": asset.basis_crawl_job_id,
        "status": asset.status,
        "surfer_custom_instructions": asset.surfer_custom_instructions,
        "seowriting_details_to_include": asset.seowriting_details_to_include,
        "introductory_hook_brief": asset.introductory_hook_brief,
        "source_urls_json": list(asset.source_urls_json or []),
        "source_pages_hash": asset.source_pages_hash,
        "prompt_version": asset.prompt_version,
        "llm_provider": asset.llm_provider,
        "llm_model": asset.llm_model,
        "generated_at": asset.generated_at,
        "last_error_code": asset.last_error_code,
        "last_error_message": asset.last_error_message,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
    }
