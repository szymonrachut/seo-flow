from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import CrawlJob, CrawlJobStatus, SiteContentGeneratorAsset
from app.db.session import SessionLocal
from app.integrations.openai.client import OpenAiLlmClient
from app.services import content_generator_context_service, content_generator_prompt_service, site_service


MANUAL_GENERATION_PRECONDITION_ERROR_CODES = frozenset(
    {
        "site_context_error",
        "active_crawl_missing",
        "active_crawl_not_finished",
        "active_crawl_has_no_pages",
        "no_eligible_source_pages",
        "source_selection_empty",
    }
)


class ContentGeneratorServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "content_generator_service_error") -> None:
        super().__init__(message)
        self.code = code


def get_site_content_generator_asset(session: Session, site_id: int) -> dict[str, Any] | None:
    asset = _load_asset(session, site_id=site_id)
    if asset is None:
        return None
    return _serialize_asset(asset)


def build_site_content_generator_asset_view(
    session: Session,
    site_id: int,
    *,
    active_crawl_id: int | None = None,
) -> dict[str, Any]:
    try:
        workspace = site_service.resolve_site_workspace_context(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
        )
    except site_service.SiteServiceError as exc:
        raise ContentGeneratorServiceError(str(exc), code="site_context_error") from exc

    active_crawl = workspace["active_crawl"]
    active_crawl_status = _serialize_crawl_status(active_crawl.status) if active_crawl is not None else None
    asset = _load_asset(session, site_id=site_id)
    serialized_asset = _serialize_asset(asset) if asset is not None else None

    return {
        "site_id": site_id,
        "has_assets": asset is not None,
        "can_regenerate": active_crawl_status == CrawlJobStatus.FINISHED.value,
        "active_crawl_id": active_crawl.id if active_crawl is not None else None,
        "active_crawl_status": active_crawl_status,
        "status": serialized_asset["status"] if serialized_asset is not None else None,
        "basis_crawl_job_id": serialized_asset["basis_crawl_job_id"] if serialized_asset is not None else None,
        "surfer_custom_instructions": (
            serialized_asset["surfer_custom_instructions"] if serialized_asset is not None else None
        ),
        "seowriting_details_to_include": (
            serialized_asset["seowriting_details_to_include"] if serialized_asset is not None else None
        ),
        "introductory_hook_brief": serialized_asset["introductory_hook_brief"] if serialized_asset is not None else None,
        "source_urls": list(serialized_asset["source_urls_json"]) if serialized_asset is not None else [],
        "source_pages_hash": serialized_asset["source_pages_hash"] if serialized_asset is not None else None,
        "prompt_version": serialized_asset["prompt_version"] if serialized_asset is not None else None,
        "llm_provider": serialized_asset["llm_provider"] if serialized_asset is not None else None,
        "llm_model": serialized_asset["llm_model"] if serialized_asset is not None else None,
        "generated_at": serialized_asset["generated_at"] if serialized_asset is not None else None,
        "last_error_code": serialized_asset["last_error_code"] if serialized_asset is not None else None,
        "last_error_message": serialized_asset["last_error_message"] if serialized_asset is not None else None,
    }


def generate_site_content_assets_action(
    session: Session,
    *,
    site_id: int,
    output_language: str = "en",
) -> dict[str, Any]:
    try:
        generate_site_content_assets(
            session,
            site_id=site_id,
            output_language=output_language,
        )
    except ContentGeneratorServiceError as exc:
        if exc.code in MANUAL_GENERATION_PRECONDITION_ERROR_CODES:
            raise
        return {
            "success": False,
            "generation_triggered": True,
            "asset": build_site_content_generator_asset_view(session, site_id),
            "error_code": exc.code,
            "error_message": str(exc),
        }

    return {
        "success": True,
        "generation_triggered": True,
        "asset": build_site_content_generator_asset_view(session, site_id),
        "error_code": None,
        "error_message": None,
    }


def auto_generate_first_site_content_assets_for_crawl(
    crawl_job_id: int,
    *,
    output_language: str = "en",
) -> dict[str, Any]:
    session = SessionLocal()
    try:
        crawl_job = session.get(CrawlJob, crawl_job_id)
        if crawl_job is None:
            return {
                "triggered": False,
                "success": False,
                "skip_reason": "crawl_job_not_found",
                "site_id": None,
                "crawl_job_id": crawl_job_id,
                "asset_status": None,
                "basis_crawl_job_id": None,
                "error_code": None,
                "error_message": None,
            }

        crawl_status = _serialize_crawl_status(crawl_job.status)
        if crawl_status != CrawlJobStatus.FINISHED.value:
            return {
                "triggered": False,
                "success": False,
                "skip_reason": "crawl_not_finished",
                "site_id": crawl_job.site_id,
                "crawl_job_id": crawl_job.id,
                "asset_status": None,
                "basis_crawl_job_id": None,
                "error_code": None,
                "error_message": None,
            }

        existing_asset = _load_asset(session, site_id=crawl_job.site_id)
        if existing_asset is not None:
            return {
                "triggered": False,
                "success": False,
                "skip_reason": "asset_exists",
                "site_id": crawl_job.site_id,
                "crawl_job_id": crawl_job.id,
                "asset_status": existing_asset.status,
                "basis_crawl_job_id": existing_asset.basis_crawl_job_id,
                "error_code": None,
                "error_message": None,
            }

        try:
            payload = generate_site_content_assets(
                session,
                site_id=crawl_job.site_id,
                active_crawl_id=crawl_job.id,
                output_language=output_language,
            )
        except ContentGeneratorServiceError as exc:
            asset_view = build_site_content_generator_asset_view(
                session,
                crawl_job.site_id,
                active_crawl_id=crawl_job.id,
            )
            return {
                "triggered": True,
                "success": False,
                "skip_reason": None,
                "site_id": crawl_job.site_id,
                "crawl_job_id": crawl_job.id,
                "asset_status": asset_view["status"],
                "basis_crawl_job_id": asset_view["basis_crawl_job_id"],
                "error_code": exc.code,
                "error_message": str(exc),
            }

        return {
            "triggered": True,
            "success": True,
            "skip_reason": None,
            "site_id": crawl_job.site_id,
            "crawl_job_id": crawl_job.id,
            "asset_status": payload["status"],
            "basis_crawl_job_id": payload["basis_crawl_job_id"],
            "error_code": None,
            "error_message": None,
        }
    finally:
        session.close()


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


def _serialize_crawl_status(value: CrawlJobStatus | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, CrawlJobStatus):
        return value.value
    return str(value)
