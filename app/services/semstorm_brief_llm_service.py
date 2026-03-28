from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.text_processing import collapse_whitespace
from app.db.models import Site, SiteSemstormBriefEnrichmentRun, SiteSemstormBriefItem, SiteSemstormPlanItem, utcnow
from app.integrations.openai.client import OpenAiConfigurationError, OpenAiIntegrationError, OpenAiLlmClient
from app.services import semstorm_brief_service
from app.services.competitive_gap_language_service import output_language_instruction


SemstormBriefEnrichmentStatus = Literal["completed", "failed"]
SemstormBriefEnrichmentEngineMode = Literal["auto", "mock", "llm"]
ResolvedSemstormBriefEnrichmentEngineMode = Literal["mock", "llm"]

SEMSTORM_BRIEF_ENRICHMENT_PROMPT_VERSION = "semstorm-brief-enrichment-v1"
SEMSTORM_BRIEF_ENRICHMENT_COMPLETION_LIMITS = (900, 1400)
SEMSTORM_BRIEF_ENRICHMENT_MOCK_MODEL = "mock-semstorm-brief-enrichment-v1"


class SemstormBriefLlmServiceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "semstorm_brief_enrichment_error",
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class SemstormBriefEnrichmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    improved_brief_title: str | None = Field(default=None, max_length=400)
    improved_page_title: str | None = Field(default=None, max_length=400)
    improved_h1: str | None = Field(default=None, max_length=400)
    improved_angle_summary: str | None = Field(default=None, max_length=2000)
    improved_sections: list[str] = Field(default_factory=list, max_length=10)
    improved_internal_link_targets: list[str] = Field(default_factory=list, max_length=8)
    editorial_notes: list[str] = Field(default_factory=list, max_length=8)
    risk_flags: list[str] = Field(default_factory=list, max_length=8)


def enrich_semstorm_brief(
    session: Session,
    site_id: int,
    brief_id: int,
    *,
    output_language: str = "en",
    client: OpenAiLlmClient | Any | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    brief_item = _get_brief_item_or_raise(session, site_id, brief_id)
    input_hash = _build_brief_input_hash(brief_item)
    now = utcnow()
    run = SiteSemstormBriefEnrichmentRun(
        site_id=site_id,
        brief_item_id=brief_item.id,
        status="failed",
        engine_mode="mock",
        model_name=None,
        input_hash=input_hash,
        output_summary_json=None,
        error_code=None,
        error_message_safe=None,
        is_applied=False,
        applied_at=None,
        created_at=now,
        updated_at=now,
    )
    session.add(run)
    session.flush()

    try:
        resolved_mode, model_name = _resolve_engine_mode(settings, client=client)
        run.engine_mode = resolved_mode
        run.model_name = model_name

        if resolved_mode == "mock":
            raw_output = _build_mock_enrichment_output(brief_item)
        else:
            raw_output = _call_llm_enrichment(
                brief_item=brief_item,
                output_language=output_language,
                client=client,
                settings=settings,
            )

        normalized_output = _normalize_output_summary(raw_output)
        if not _has_usable_output(normalized_output):
            raise SemstormBriefLlmServiceError(
                "Brief enrichment returned no usable suggestions.",
                code="no_usable_suggestions",
                status_code=502,
            )

        run.status = "completed"
        run.output_summary_json = normalized_output
        run.error_code = None
        run.error_message_safe = None
        run.updated_at = utcnow()
        session.flush()
        session.refresh(run)
        return serialize_brief_enrichment_run(run)
    except Exception as exc:
        error = _normalize_enrichment_error(exc)
        run.status = "failed"
        run.output_summary_json = None
        run.error_code = error.code
        run.error_message_safe = str(error)
        run.updated_at = utcnow()
        session.flush()
        raise error from exc


def list_semstorm_brief_enrichment_runs(
    session: Session,
    site_id: int,
    brief_id: int,
) -> dict[str, Any]:
    _ensure_site_exists(session, site_id)
    _get_brief_item_or_raise(session, site_id, brief_id)
    rows = list(
        session.scalars(
            select(SiteSemstormBriefEnrichmentRun)
            .where(
                SiteSemstormBriefEnrichmentRun.site_id == site_id,
                SiteSemstormBriefEnrichmentRun.brief_item_id == brief_id,
            )
            .order_by(SiteSemstormBriefEnrichmentRun.created_at.desc(), SiteSemstormBriefEnrichmentRun.id.desc())
        )
    )
    return {
        "site_id": site_id,
        "brief_id": brief_id,
        "summary": {
            "total_count": len(rows),
            "completed_count": sum(1 for row in rows if row.status == "completed"),
            "failed_count": sum(1 for row in rows if row.status == "failed"),
            "applied_count": sum(1 for row in rows if bool(row.is_applied)),
        },
        "items": [serialize_brief_enrichment_run(row) for row in rows],
    }


def apply_semstorm_brief_enrichment_run(
    session: Session,
    site_id: int,
    brief_id: int,
    run_id: int,
) -> dict[str, Any]:
    brief_item = _get_brief_item_or_raise(session, site_id, brief_id)
    run = _get_enrichment_run_or_raise(session, site_id, brief_id, run_id)

    if run.status != "completed":
        raise SemstormBriefLlmServiceError(
            "Only completed enrichment runs can be applied.",
            code="invalid_enrichment_status",
            status_code=409,
        )
    if bool(run.is_applied):
        return {
            "site_id": site_id,
            "brief_id": brief_id,
            "run_id": run.id,
            "applied": False,
            "skipped_reason": "already_applied",
            "applied_fields": [],
            "brief": semstorm_brief_service.serialize_brief_item(brief_item),
            "enrichment_run": serialize_brief_enrichment_run(run),
        }

    normalized_output = _normalize_output_summary(run.output_summary_json or {})
    if not _has_usable_output(normalized_output):
        return {
            "site_id": site_id,
            "brief_id": brief_id,
            "run_id": run.id,
            "applied": False,
            "skipped_reason": "no_usable_suggestions",
            "applied_fields": [],
            "brief": semstorm_brief_service.serialize_brief_item(brief_item),
            "enrichment_run": serialize_brief_enrichment_run(run),
        }

    applied_fields = _apply_output_to_brief(brief_item, normalized_output)
    if not applied_fields:
        return {
            "site_id": site_id,
            "brief_id": brief_id,
            "run_id": run.id,
            "applied": False,
            "skipped_reason": "no_changes",
            "applied_fields": [],
            "brief": semstorm_brief_service.serialize_brief_item(brief_item),
            "enrichment_run": serialize_brief_enrichment_run(run),
        }

    now = utcnow()
    brief_item.updated_at = now
    run.is_applied = True
    run.applied_at = now
    run.updated_at = now
    session.flush()
    session.refresh(brief_item)
    session.refresh(run)
    return {
        "site_id": site_id,
        "brief_id": brief_id,
        "run_id": run.id,
        "applied": True,
        "skipped_reason": None,
        "applied_fields": applied_fields,
        "brief": semstorm_brief_service.serialize_brief_item(brief_item),
        "enrichment_run": serialize_brief_enrichment_run(run),
    }


def serialize_brief_enrichment_run(row: SiteSemstormBriefEnrichmentRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "site_id": row.site_id,
        "brief_item_id": row.brief_item_id,
        "status": row.status,
        "engine_mode": row.engine_mode,
        "model_name": row.model_name,
        "input_hash": row.input_hash,
        "suggestions": _normalize_output_summary(row.output_summary_json or {}),
        "error_code": row.error_code,
        "error_message_safe": row.error_message_safe,
        "is_applied": bool(row.is_applied),
        "applied_at": row.applied_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _ensure_site_exists(session: Session, site_id: int) -> None:
    exists = session.scalar(select(Site.id).where(Site.id == site_id))
    if exists is None:
        raise SemstormBriefLlmServiceError(
            f"Site {site_id} not found.",
            code="not_found",
            status_code=404,
        )


def _get_brief_item_or_raise(session: Session, site_id: int, brief_id: int) -> SiteSemstormBriefItem:
    _ensure_site_exists(session, site_id)
    brief_item = session.scalar(
        select(SiteSemstormBriefItem)
        .where(
            SiteSemstormBriefItem.site_id == site_id,
            SiteSemstormBriefItem.id == brief_id,
        )
        .options(selectinload(SiteSemstormBriefItem.plan_item).selectinload(SiteSemstormPlanItem.promoted_item))
    )
    if brief_item is None:
        raise SemstormBriefLlmServiceError(
            f"Semstorm brief item {brief_id} not found.",
            code="not_found",
            status_code=404,
        )
    return brief_item


def _get_enrichment_run_or_raise(
    session: Session,
    site_id: int,
    brief_id: int,
    run_id: int,
) -> SiteSemstormBriefEnrichmentRun:
    row = session.scalar(
        select(SiteSemstormBriefEnrichmentRun).where(
            SiteSemstormBriefEnrichmentRun.site_id == site_id,
            SiteSemstormBriefEnrichmentRun.brief_item_id == brief_id,
            SiteSemstormBriefEnrichmentRun.id == run_id,
        )
    )
    if row is None:
        raise SemstormBriefLlmServiceError(
            f"Semstorm brief enrichment run {run_id} not found.",
            code="not_found",
            status_code=404,
        )
    return row


def _resolve_engine_mode(
    settings: Settings,
    *,
    client: OpenAiLlmClient | Any | None,
) -> tuple[ResolvedSemstormBriefEnrichmentEngineMode, str]:
    configured_mode = settings.semstorm_brief_engine_mode
    if configured_mode == "mock":
        return ("mock", SEMSTORM_BRIEF_ENRICHMENT_MOCK_MODEL)
    if configured_mode == "auto":
        resolved_client = client or OpenAiLlmClient()
        if settings.semstorm_brief_llm_enabled and _client_is_available(resolved_client):
            return ("llm", settings.semstorm_brief_llm_model)
        return ("mock", SEMSTORM_BRIEF_ENRICHMENT_MOCK_MODEL)
    _raise_llm_unavailable_if_needed(settings, client=client)
    return ("llm", settings.semstorm_brief_llm_model)


def _raise_llm_unavailable_if_needed(settings: Settings, *, client: OpenAiLlmClient | Any | None) -> None:
    if not settings.semstorm_brief_llm_enabled:
        raise SemstormBriefLlmServiceError(
            "Semstorm brief AI enrichment is disabled in backend config.",
            code="llm_disabled",
            status_code=503,
        )
    if not settings.openai_api_key:
        raise SemstormBriefLlmServiceError(
            "OPENAI_API_KEY is missing in backend config.",
            code="missing_api_key",
            status_code=503,
        )
    resolved_client = client or OpenAiLlmClient()
    if not _client_is_available(resolved_client):
        raise SemstormBriefLlmServiceError(
            "OpenAI Semstorm brief enrichment is currently unavailable.",
            code="llm_unavailable",
            status_code=503,
        )


def _call_llm_enrichment(
    *,
    brief_item: SiteSemstormBriefItem,
    output_language: str,
    client: OpenAiLlmClient | Any | None,
    settings: Settings,
) -> SemstormBriefEnrichmentOutput | Mapping[str, Any]:
    resolved_client = client or OpenAiLlmClient()
    parsed = None
    last_error: OpenAiIntegrationError | None = None
    for completion_limit in SEMSTORM_BRIEF_ENRICHMENT_COMPLETION_LIMITS:
        try:
            parsed = resolved_client.parse_chat_completion(
                model=settings.semstorm_brief_llm_model,
                system_prompt=_brief_enrichment_system_prompt(output_language=output_language),
                user_prompt=_brief_enrichment_user_prompt(brief_item, output_language=output_language),
                response_format=SemstormBriefEnrichmentOutput,
                max_completion_tokens=completion_limit,
                reasoning_effort="minimal",
                verbosity="low",
                timeout_seconds=settings.semstorm_brief_llm_timeout_seconds,
            )
            break
        except OpenAiIntegrationError as exc:
            last_error = exc
            if exc.code == "length_limit" and completion_limit != SEMSTORM_BRIEF_ENRICHMENT_COMPLETION_LIMITS[-1]:
                continue
            raise SemstormBriefLlmServiceError(str(exc), code=exc.code, status_code=502) from exc
        except OpenAiConfigurationError as exc:
            raise SemstormBriefLlmServiceError(str(exc), code=exc.code, status_code=503) from exc

    if parsed is None:
        fallback_exc = last_error or SemstormBriefLlmServiceError(
            "Semstorm brief enrichment returned no structured output.",
            code="structured_output_missing",
            status_code=502,
        )
        raise SemstormBriefLlmServiceError(
            str(fallback_exc),
            code=getattr(fallback_exc, "code", "structured_output_missing"),
            status_code=502,
        )
    return parsed


def _brief_enrichment_system_prompt(*, output_language: str) -> str:
    return (
        "You improve an existing SEO brief scaffold for manual execution. "
        "Use only the provided JSON context. "
        "Do not generate article body copy. "
        "Return only structured suggestions that improve the brief title, page title, H1, angle, section outline, "
        "internal link targets, editorial notes and risk flags. "
        "Preserve natural Unicode spelling in free-text outputs instead of transliterating to ASCII. "
        f"{output_language_instruction(output_language)}"
    )


def _brief_enrichment_user_prompt(
    brief_item: SiteSemstormBriefItem,
    *,
    output_language: str,
) -> str:
    plan_item = brief_item.plan_item
    promoted_item = plan_item.promoted_item if plan_item is not None else None
    payload = {
        "prompt_version": SEMSTORM_BRIEF_ENRICHMENT_PROMPT_VERSION,
        "task": "semstorm_brief_enrichment",
        "output_language": output_language,
        "brief": semstorm_brief_service.serialize_brief_item(brief_item),
        "plan_context": {
            "plan_item_id": int(plan_item.id) if plan_item is not None else None,
            "state_status": str(plan_item.state_status or "") if plan_item is not None else None,
            "target_page_type": str(plan_item.target_page_type or "") if plan_item is not None else None,
            "decision_type_snapshot": str(plan_item.decision_type_snapshot or "") if plan_item is not None else None,
            "bucket_snapshot": str(plan_item.bucket_snapshot or "") if plan_item is not None else None,
            "coverage_status_snapshot": str(plan_item.coverage_status_snapshot or "") if plan_item is not None else None,
            "gsc_signal_status_snapshot": str(plan_item.gsc_signal_status_snapshot or "") if plan_item is not None else None,
            "opportunity_score_v2_snapshot": int(plan_item.opportunity_score_v2_snapshot or 0)
            if plan_item is not None
            else 0,
            "best_match_page_url_snapshot": plan_item.best_match_page_url_snapshot if plan_item is not None else None,
        },
        "promoted_context": {
            "promoted_item_id": int(promoted_item.id) if promoted_item is not None else None,
            "keyword": promoted_item.keyword if promoted_item is not None else None,
            "coverage_status": promoted_item.coverage_status if promoted_item is not None else None,
            "gsc_signal_status": promoted_item.gsc_signal_status if promoted_item is not None else None,
            "source_payload": promoted_item.source_payload_json if promoted_item is not None else None,
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _build_mock_enrichment_output(brief_item: SiteSemstormBriefItem) -> dict[str, Any]:
    primary_keyword = collapse_whitespace(brief_item.primary_keyword or "") or "keyword"
    keyword_label = _title_case(primary_keyword)
    brief_type = str(brief_item.brief_type or "new_page")
    current_sections = _normalize_string_list(brief_item.sections_json or [], max_length=140)
    current_links = _normalize_link_list(brief_item.internal_link_targets_json or [])

    if brief_type == "new_page":
        improved_page_title = f"{keyword_label} | Practical Guide and Next Steps"
    elif brief_type == "expand_existing":
        improved_page_title = f"{keyword_label} | Expanded Guide and Supporting Detail"
    elif brief_type == "refresh_existing":
        improved_page_title = f"{keyword_label} | Updated Guide and Next Steps"
    else:
        improved_page_title = f"{keyword_label} | Supporting Topic Brief"

    improved_sections = current_sections or [
        f"Why {keyword_label} matters",
        "Key decision points",
        "Process, checklist or framework",
        "Examples and proof points",
        "FAQs and objections",
        "Next steps and internal links",
    ]
    if not any("FAQ" in section.upper() for section in improved_sections):
        improved_sections.append("FAQs and objections")
    improved_sections = _normalize_string_list(improved_sections, max_length=140)[:7]

    editorial_notes = [
        "Keep the brief operational and decision-oriented rather than article-like.",
        f"Use '{primary_keyword}' in the page title, H1 and opening section.",
    ]
    risk_flags = []
    if str(brief_item.search_intent or "mixed") == "transactional":
        risk_flags.append("Avoid turning a transactional keyword into a generic educational article.")
    if brief_item.target_url_existing:
        risk_flags.append("Preserve the existing page intent and avoid splitting the topic into duplicate URLs.")

    angle_summary = collapse_whitespace(brief_item.angle_summary or "")
    improved_angle_summary = (
        f"{angle_summary} Focus the execution packet on a clear scope, decision path and internal link plan."
        if angle_summary
        else f"Use this brief to turn '{primary_keyword}' into a clear execution packet with a practical angle and explicit next step."
    )

    return {
        "improved_brief_title": f"Execution brief: {keyword_label}",
        "improved_page_title": improved_page_title,
        "improved_h1": keyword_label,
        "improved_angle_summary": improved_angle_summary,
        "improved_sections": improved_sections,
        "improved_internal_link_targets": current_links[:4],
        "editorial_notes": editorial_notes,
        "risk_flags": risk_flags,
    }


def _build_brief_input_hash(brief_item: SiteSemstormBriefItem) -> str:
    payload = {
        "brief_id": int(brief_item.id),
        "state_status": str(brief_item.state_status or ""),
        "brief_title": brief_item.brief_title,
        "brief_type": brief_item.brief_type,
        "primary_keyword": brief_item.primary_keyword,
        "secondary_keywords": list(brief_item.secondary_keywords_json or []),
        "search_intent": brief_item.search_intent,
        "target_url_existing": brief_item.target_url_existing,
        "proposed_url_slug": brief_item.proposed_url_slug,
        "recommended_page_title": brief_item.recommended_page_title,
        "recommended_h1": brief_item.recommended_h1,
        "content_goal": brief_item.content_goal,
        "angle_summary": brief_item.angle_summary,
        "sections": list(brief_item.sections_json or []),
        "internal_link_targets": list(brief_item.internal_link_targets_json or []),
        "source_notes": list(brief_item.source_notes_json or []),
    }
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_output_summary(value: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json")
    else:
        payload = dict(value)
    return {
        "improved_brief_title": _normalize_optional_text(payload.get("improved_brief_title"), max_length=400),
        "improved_page_title": _normalize_optional_text(payload.get("improved_page_title"), max_length=400),
        "improved_h1": _normalize_optional_text(payload.get("improved_h1"), max_length=400),
        "improved_angle_summary": _normalize_optional_text(payload.get("improved_angle_summary"), max_length=2000),
        "improved_sections": _normalize_string_list(payload.get("improved_sections"), max_length=140)[:10],
        "improved_internal_link_targets": _normalize_link_list(payload.get("improved_internal_link_targets"))[:8],
        "editorial_notes": _normalize_string_list(payload.get("editorial_notes"), max_length=240)[:8],
        "risk_flags": _normalize_string_list(payload.get("risk_flags"), max_length=240)[:8],
    }


def _has_usable_output(payload: Mapping[str, Any]) -> bool:
    return any(
        bool(payload.get(key))
        for key in (
            "improved_brief_title",
            "improved_page_title",
            "improved_h1",
            "improved_angle_summary",
            "improved_sections",
            "improved_internal_link_targets",
            "editorial_notes",
            "risk_flags",
        )
    )


def _apply_output_to_brief(brief_item: SiteSemstormBriefItem, payload: Mapping[str, Any]) -> list[str]:
    applied_fields: list[str] = []

    def assign_text(field_name: str, new_value: Any) -> None:
        nonlocal applied_fields
        normalized = _normalize_optional_text(new_value)
        if not normalized:
            return
        if getattr(brief_item, field_name) == normalized:
            return
        setattr(brief_item, field_name, normalized)
        applied_fields.append(field_name)

    assign_text("brief_title", payload.get("improved_brief_title"))
    assign_text("recommended_page_title", payload.get("improved_page_title"))
    assign_text("recommended_h1", payload.get("improved_h1"))
    assign_text("angle_summary", payload.get("improved_angle_summary"))

    improved_sections = _normalize_string_list(payload.get("improved_sections"), max_length=140)[:10]
    if improved_sections and list(brief_item.sections_json or []) != improved_sections:
        brief_item.sections_json = improved_sections
        applied_fields.append("sections")

    improved_links = _normalize_link_list(payload.get("improved_internal_link_targets"))[:8]
    if improved_links and list(brief_item.internal_link_targets_json or []) != improved_links:
        brief_item.internal_link_targets_json = improved_links
        applied_fields.append("internal_link_targets")

    note_candidates = [
        *[f"AI note: {value}" for value in _normalize_string_list(payload.get("editorial_notes"), max_length=240)[:8]],
        *[f"Risk flag: {value}" for value in _normalize_string_list(payload.get("risk_flags"), max_length=240)[:8]],
    ]
    if note_candidates:
        merged_notes = list(brief_item.source_notes_json or [])
        for candidate in note_candidates:
            if candidate not in merged_notes:
                merged_notes.append(candidate)
        if list(brief_item.source_notes_json or []) != merged_notes:
            brief_item.source_notes_json = merged_notes
            applied_fields.append("source_notes")

    return applied_fields


def _normalize_optional_text(value: Any, *, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    text = collapse_whitespace(str(value))
    if not text:
        return None
    if max_length is not None:
        return text[:max_length]
    return text


def _normalize_string_list(value: Any, *, max_length: int) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    deduped: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = _normalize_optional_text(item, max_length=max_length)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _normalize_link_list(value: Any) -> list[str]:
    candidates = _normalize_string_list(value, max_length=2048)
    return [candidate for candidate in candidates if _looks_like_link_target(candidate)]


def _looks_like_link_target(value: str) -> bool:
    lower_value = value.lower()
    return lower_value.startswith("https://") or lower_value.startswith("http://") or lower_value.startswith("/")


def _title_case(value: str) -> str:
    return " ".join(part.upper() if part.lower() in {"seo", "gsc", "faq", "url", "urls", "cpc", "ai"} else part.capitalize() for part in value.split())


def _client_is_available(client: OpenAiLlmClient | Any) -> bool:
    availability_method = getattr(client, "is_available", None)
    if callable(availability_method):
        return bool(availability_method())
    return True


def _normalize_enrichment_error(exc: Exception) -> SemstormBriefLlmServiceError:
    if isinstance(exc, SemstormBriefLlmServiceError):
        return exc
    if hasattr(exc, "code") and hasattr(exc, "status_code"):
        return SemstormBriefLlmServiceError(
            str(exc),
            code=str(getattr(exc, "code")),
            status_code=int(getattr(exc, "status_code")),
        )
    if isinstance(exc, semstorm_brief_service.SemstormBriefServiceError):
        return SemstormBriefLlmServiceError(str(exc), code=exc.code, status_code=exc.status_code)
    return SemstormBriefLlmServiceError(
        "Semstorm brief enrichment failed due to an unexpected backend error.",
        code="semstorm_brief_enrichment_failed",
        status_code=500,
    )
