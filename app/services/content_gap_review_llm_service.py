from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.text_processing import collapse_whitespace, normalize_text_for_hash, tokenize_topic_text
from app.db.models import GscTopQuery, Page, SiteContentGapCandidate, SiteContentGapReviewRun
from app.db.session import SessionLocal
from app.integrations.openai.client import OpenAiConfigurationError, OpenAiIntegrationError, OpenAiLlmClient
from app.services import content_gap_item_materialization_service, content_gap_review_run_service
from app.services.competitive_gap_language_service import output_language_instruction
from app.services.content_gap_candidate_service import DEFAULT_GSC_DATE_RANGE


logger = logging.getLogger(__name__)

CONTENT_GAP_REVIEW_COMPLETION_LIMITS = (1600, 2400)
CONTENT_GAP_REVIEW_MAX_SHORTLIST_PAGES = 5
CONTENT_GAP_REVIEW_MAX_SHORTLIST_QUERIES = 5


class ContentGapReviewLlmServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "content_gap_review_execution_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(slots=True)
class ContentGapReviewExecutionResult:
    review_run_id: int
    run_id: int
    batch_count: int
    materialized_item_count: int
    llm_provider: str | None
    llm_model: str | None
    prompt_version: str | None


class _BatchDecisionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_index: int = Field(ge=1, le=20)
    decision_action: Literal["keep", "remove", "merge", "rewrite"]
    fit_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    decision_reason_text: str = Field(min_length=1, max_length=400)
    decision_reason_code: str | None = Field(default=None, max_length=64)
    reviewed_phrase: str | None = Field(default=None, max_length=255)
    reviewed_topic_label: str | None = Field(default=None, max_length=255)
    reviewed_normalized_topic_key: str | None = Field(default=None, max_length=255)
    reviewed_gap_type: str | None = Field(default=None, max_length=64)
    merge_target_candidate_key: str | None = Field(default=None, max_length=96)
    merge_target_phrase: str | None = Field(default=None, max_length=255)
    remove_reason_code: str | None = Field(default=None, max_length=64)
    remove_reason_text: str | None = Field(default=None, max_length=400)
    rewrite_reason_text: str | None = Field(default=None, max_length=400)
    review_group_key: str | None = Field(default=None, max_length=96)
    group_primary: bool | None = None
    own_site_alignment_summary: list[str] = Field(default_factory=list, max_length=3)
    gsc_support_summary: list[str] = Field(default_factory=list, max_length=3)
    competitor_evidence_summary: list[str] = Field(default_factory=list, max_length=3)
    sort_score: float | None = Field(default=None, ge=0.0, le=100.0)


class _BatchReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[_BatchDecisionOutput] = Field(min_length=1, max_length=20)


def execute_review_run(
    session: Session,
    *,
    site_id: int,
    run_id: int,
    client: OpenAiLlmClient | Any | None = None,
    lease_owner: str = "content_gap_review_llm",
) -> ContentGapReviewExecutionResult:
    run = _load_review_run_or_raise(session, site_id=site_id, run_id=run_id)
    if run.status == "queued":
        if not content_gap_review_run_service.claim_review_run(
            session,
            site_id=site_id,
            run_id=run_id,
            lease_owner=lease_owner,
        ):
            raise ContentGapReviewLlmServiceError(
                "Content Gap review run could not be claimed.",
                code="run_not_claimed",
            )
        session.expire_all()
        run = _load_review_run_or_raise(session, site_id=site_id, run_id=run_id)
    elif run.status != "running":
        raise ContentGapReviewLlmServiceError(
            f"Content Gap review run {run_id} is not executable from status '{run.status}'.",
            code="invalid_run_status",
        )

    resolved_client = client or OpenAiLlmClient()
    if not resolved_client.is_available():
        error = ContentGapReviewLlmServiceError(_resolve_unavailable_message(), code=_resolve_unavailable_code())
        _mark_run_failed(session, run=run, error=error)
        raise error

    try:
        candidates = _load_review_run_candidates(session, run=run)
        if _build_candidate_set_hash(candidates) != run.candidate_set_hash:
            raise ContentGapReviewLlmServiceError(
                "Review run candidate scope no longer matches the frozen candidate set hash.",
                code="candidate_set_mismatch",
            )

        own_pages = _load_own_page_context_rows(session, basis_crawl_job_id=run.basis_crawl_job_id)
        own_context_hash, _own_pages_count = content_gap_review_run_service._build_own_context_hash(
            session,
            basis_crawl_job_id=run.basis_crawl_job_id,
        )
        if own_context_hash != run.own_context_hash:
            raise ContentGapReviewLlmServiceError(
                "Own-site snapshot context no longer matches the frozen review run context.",
                code="own_context_mismatch",
            )

        gsc_queries = _load_gsc_query_context_rows(session, basis_crawl_job_id=run.basis_crawl_job_id)
        gsc_context_hash, _gsc_query_count = content_gap_review_run_service._build_gsc_context_hash(
            session,
            basis_crawl_job_id=run.basis_crawl_job_id,
        )
        if gsc_context_hash != run.gsc_context_hash:
            raise ContentGapReviewLlmServiceError(
                "GSC snapshot context no longer matches the frozen review run context.",
                code="gsc_context_mismatch",
            )

        candidate_batches = _chunk_candidates(candidates, batch_size=max(1, int(run.batch_size or 1)))
        if len(candidate_batches) != int(run.batch_count or 0):
            raise ContentGapReviewLlmServiceError(
                "Review run batch plan no longer matches the frozen candidate scope.",
                code="batch_plan_mismatch",
            )

        all_decisions: list[content_gap_item_materialization_service.SanitizedContentGapDecision] = []
        for index, batch in enumerate(candidate_batches, start=1):
            content_gap_review_run_service.touch_review_run(
                session,
                site_id=site_id,
                run_id=run_id,
                stage="batch_review",
                completed_batch_count=index - 1,
                lease_owner=lease_owner,
            )
            batch_output = _call_review_batch_llm(
                client=resolved_client,
                run=run,
                batch=batch,
                own_pages=own_pages,
                gsc_queries=gsc_queries,
            )
            batch_decisions = _normalize_batch_output(batch_output, batch=batch)
            all_decisions.extend(batch_decisions)

        content_gap_review_run_service.touch_review_run(
            session,
            site_id=site_id,
            run_id=run_id,
            stage="materialize_items",
            completed_batch_count=len(candidate_batches),
            lease_owner=lease_owner,
        )
        materialization_summary = content_gap_item_materialization_service.materialize_review_items(
            session,
            site_id=site_id,
            review_run_id=run.id,
            decisions=all_decisions,
        )
        content_gap_review_run_service._complete_review_run_in_session(
            session,
            site_id=site_id,
            run_id=run_id,
            completed_batch_count=len(candidate_batches),
        )
        session.commit()
        return ContentGapReviewExecutionResult(
            review_run_id=run.id,
            run_id=run.run_id,
            batch_count=len(candidate_batches),
            materialized_item_count=materialization_summary.created_count,
            llm_provider=getattr(resolved_client, "provider_name", None),
            llm_model=run.llm_model,
            prompt_version=run.prompt_version,
        )
    except Exception as exc:
        session.rollback()
        error = _normalize_execution_error(exc)
        with session.no_autoflush:
            failed_run = _load_review_run_or_raise(session, site_id=site_id, run_id=run_id)
            _mark_run_failed(session, run=failed_run, error=error)
        raise error from exc


def execute_review_run_task(
    site_id: int,
    run_id: int,
    *,
    lease_owner: str = "content_gap_review_llm",
) -> None:
    session = SessionLocal()
    try:
        execute_review_run(
            session,
            site_id=site_id,
            run_id=run_id,
            lease_owner=lease_owner,
        )
    finally:
        session.close()


def _load_review_run_or_raise(session: Session, *, site_id: int, run_id: int) -> SiteContentGapReviewRun:
    run = session.scalar(
        select(SiteContentGapReviewRun)
        .where(
            SiteContentGapReviewRun.site_id == site_id,
            SiteContentGapReviewRun.run_id == run_id,
        )
        .limit(1)
    )
    if run is None:
        raise ContentGapReviewLlmServiceError(
            f"Content Gap review run {run_id} not found for site {site_id}.",
            code="review_run_not_found",
        )
    return run


def _load_review_run_candidates(session: Session, *, run: SiteContentGapReviewRun) -> list[SiteContentGapCandidate]:
    selected_candidate_ids = sorted({int(candidate_id) for candidate_id in (run.selected_candidate_ids_json or [])})
    rows = session.scalars(
        select(SiteContentGapCandidate)
        .where(
            SiteContentGapCandidate.site_id == run.site_id,
            SiteContentGapCandidate.basis_crawl_job_id == run.basis_crawl_job_id,
            SiteContentGapCandidate.id.in_(selected_candidate_ids),
        )
        .order_by(SiteContentGapCandidate.id.asc())
    ).all()
    if len(rows) != len(selected_candidate_ids):
        raise ContentGapReviewLlmServiceError(
            "Review run candidate scope references missing or out-of-snapshot candidates.",
            code="candidate_scope_mismatch",
        )
    return rows


def _load_own_page_context_rows(session: Session, *, basis_crawl_job_id: int) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            Page.id,
            Page.normalized_url,
            Page.title,
            Page.h1,
            Page.meta_description,
            Page.page_type,
            Page.page_bucket,
        )
        .where(Page.crawl_job_id == basis_crawl_job_id)
        .order_by(Page.id.asc())
    ).all()
    payload: list[dict[str, Any]] = []
    for row in rows:
        payload.append(
            {
                "page_id": int(row.id),
                "normalized_url": row.normalized_url,
                "title": row.title,
                "h1": row.h1,
                "meta_description": row.meta_description,
                "page_type": row.page_type,
                "page_bucket": row.page_bucket,
                "tokens": _build_context_tokens(
                    row.normalized_url,
                    row.title,
                    row.h1,
                    row.meta_description,
                ),
            }
        )
    return payload


def _load_gsc_query_context_rows(session: Session, *, basis_crawl_job_id: int) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            GscTopQuery.page_id,
            GscTopQuery.normalized_url,
            GscTopQuery.query,
            GscTopQuery.clicks,
            GscTopQuery.impressions,
            GscTopQuery.position,
        )
        .where(
            GscTopQuery.crawl_job_id == basis_crawl_job_id,
            GscTopQuery.date_range_label == DEFAULT_GSC_DATE_RANGE,
        )
        .order_by(GscTopQuery.id.asc())
    ).all()
    payload: list[dict[str, Any]] = []
    for row in rows:
        payload.append(
            {
                "page_id": int(row.page_id) if row.page_id is not None else None,
                "normalized_url": row.normalized_url,
                "query": row.query,
                "clicks": int(row.clicks or 0),
                "impressions": int(row.impressions or 0),
                "position": float(row.position) if row.position is not None else None,
                "tokens": tokenize_topic_text(row.query),
            }
        )
    return payload


def _build_candidate_set_hash(candidates: list[SiteContentGapCandidate]) -> str:
    payload = [
        {
            "id": int(candidate.id),
            "candidate_key": str(candidate.candidate_key),
            "candidate_input_hash": str(candidate.candidate_input_hash),
            "generation_version": str(candidate.generation_version),
        }
        for candidate in sorted(candidates, key=lambda item: (item.id, item.candidate_key))
    ]
    return _hash_payload(payload)


def _build_own_context_hash(own_pages: list[dict[str, Any]]) -> str:
    payload = [
        {
            "page_id": int(page["page_id"]),
            "normalized_url": page["normalized_url"],
            "title": page["title"],
            "h1": page["h1"],
            "meta_description": page["meta_description"],
            "page_type": page["page_type"],
            "page_bucket": page["page_bucket"],
        }
        for page in own_pages
    ]
    return _hash_payload(payload)


def _build_gsc_context_hash(gsc_queries: list[dict[str, Any]]) -> str | None:
    if not gsc_queries:
        return None
    payload = [
        {
            "page_id": query["page_id"],
            "normalized_url": query["normalized_url"],
            "query": query["query"],
            "clicks": query["clicks"],
            "impressions": query["impressions"],
            "position": query["position"],
        }
        for query in gsc_queries
    ]
    return _hash_payload(payload)


def _chunk_candidates(
    candidates: list[SiteContentGapCandidate],
    *,
    batch_size: int,
) -> list[list[SiteContentGapCandidate]]:
    return [
        candidates[index : index + batch_size]
        for index in range(0, len(candidates), batch_size)
    ]


def _call_review_batch_llm(
    *,
    client: OpenAiLlmClient | Any,
    run: SiteContentGapReviewRun,
    batch: list[SiteContentGapCandidate],
    own_pages: list[dict[str, Any]],
    gsc_queries: list[dict[str, Any]],
) -> _BatchReviewOutput:
    parsed = None
    last_error: OpenAiIntegrationError | None = None
    for completion_limit in CONTENT_GAP_REVIEW_COMPLETION_LIMITS:
        try:
            parsed = client.parse_chat_completion(
                model=run.llm_model or get_settings().openai_model_competitor_merge,
                system_prompt=_review_batch_system_prompt(output_language=run.output_language),
                user_prompt=_review_batch_user_prompt(
                    run=run,
                    batch=batch,
                    own_pages=own_pages,
                    gsc_queries=gsc_queries,
                ),
                response_format=_BatchReviewOutput,
                max_completion_tokens=completion_limit,
                reasoning_effort="minimal",
                verbosity="low",
            )
            break
        except OpenAiIntegrationError as exc:
            last_error = exc
            if exc.code == "length_limit" and completion_limit != CONTENT_GAP_REVIEW_COMPLETION_LIMITS[-1]:
                continue
            raise ContentGapReviewLlmServiceError(str(exc), code=exc.code) from exc
        except OpenAiConfigurationError as exc:
            raise ContentGapReviewLlmServiceError(str(exc), code=exc.code) from exc
    if parsed is None:
        fallback_exc = last_error or ContentGapReviewLlmServiceError(
            "Content Gap review batch returned no structured output.",
            code="structured_output_missing",
        )
        raise ContentGapReviewLlmServiceError(str(fallback_exc), code=getattr(fallback_exc, "code", "structured_output_missing"))
    return parsed


def _normalize_batch_output(
    batch_output: _BatchReviewOutput,
    *,
    batch: list[SiteContentGapCandidate],
) -> list[content_gap_item_materialization_service.SanitizedContentGapDecision]:
    expected_indices = set(range(1, len(batch) + 1))
    actual_indices = {int(item.candidate_index) for item in batch_output.decisions}
    if actual_indices != expected_indices:
        raise ContentGapReviewLlmServiceError(
            "Structured review output does not exactly match the reviewed batch scope.",
            code="batch_scope_mismatch",
        )

    candidate_by_index = {index: candidate for index, candidate in enumerate(batch, start=1)}
    decisions: list[content_gap_item_materialization_service.SanitizedContentGapDecision] = []
    for item in sorted(batch_output.decisions, key=lambda decision: decision.candidate_index):
        candidate = candidate_by_index[int(item.candidate_index)]
        reviewed_normalized_topic_key = item.reviewed_normalized_topic_key
        if not reviewed_normalized_topic_key and item.reviewed_topic_label:
            reviewed_normalized_topic_key = normalize_text_for_hash(item.reviewed_topic_label).replace(" ", "-")[:255]
        own_summary = _normalize_summary_list(item.own_site_alignment_summary)
        gsc_summary = _normalize_summary_list(item.gsc_support_summary)
        competitor_summary = _normalize_summary_list(item.competitor_evidence_summary)
        decisions.append(
            content_gap_item_materialization_service.SanitizedContentGapDecision(
                source_candidate_id=int(candidate.id),
                decision_action=item.decision_action,
                decision_reason_text=item.decision_reason_text.strip(),
                fit_score=round(float(item.fit_score), 2),
                confidence=round(float(item.confidence), 2),
                reviewed_phrase=_clean_optional_text(item.reviewed_phrase, max_length=255),
                reviewed_topic_label=_clean_optional_text(item.reviewed_topic_label, max_length=255),
                reviewed_normalized_topic_key=_clean_optional_text(reviewed_normalized_topic_key, max_length=255),
                reviewed_gap_type=_clean_optional_text(item.reviewed_gap_type, max_length=64),
                decision_reason_code=_clean_optional_text(item.decision_reason_code, max_length=64),
                merge_target_candidate_key=_clean_optional_text(item.merge_target_candidate_key, max_length=96),
                merge_target_phrase=_clean_optional_text(item.merge_target_phrase, max_length=255),
                remove_reason_code=_clean_optional_text(item.remove_reason_code, max_length=64),
                remove_reason_text=_clean_optional_text(item.remove_reason_text, max_length=400),
                rewrite_reason_text=_clean_optional_text(item.rewrite_reason_text, max_length=400),
                review_group_key=_clean_optional_text(item.review_group_key, max_length=96),
                group_primary=item.group_primary,
                own_site_alignment_json={"summary": own_summary} if own_summary else None,
                gsc_support_json={"summary": gsc_summary} if gsc_summary else None,
                competitor_evidence_json={"summary": competitor_summary} if competitor_summary else None,
                raw_decision_json=item.model_dump(mode="json"),
                sort_score=round(float(item.sort_score), 2) if item.sort_score is not None else round(float(item.fit_score), 2),
            )
        )
    return decisions


def _review_batch_system_prompt(*, output_language: str) -> str:
    return (
        "You review candidate content gaps against the site's own snapshot-aware URL inventory and GSC query context. "
        "Use only the provided JSON payload. "
        "You must return exactly one structured decision per candidate. "
        "Do not invent URLs, queries, topics or evidence. "
        "Keep decisions conservative and operational. "
        "Preserve natural Unicode spelling in free-text outputs instead of transliterating to ASCII. "
        f"{output_language_instruction(output_language)}"
    )


def _review_batch_user_prompt(
    *,
    run: SiteContentGapReviewRun,
    batch: list[SiteContentGapCandidate],
    own_pages: list[dict[str, Any]],
    gsc_queries: list[dict[str, Any]],
) -> str:
    payload = {
        "prompt_version": run.prompt_version,
        "schema_version": run.schema_version,
        "task": "content_gap_review_batch",
        "review_run": {
            "run_id": run.run_id,
            "basis_crawl_job_id": run.basis_crawl_job_id,
            "output_language": run.output_language,
        },
        "candidates": [
            _serialize_candidate_for_batch(
                candidate,
                candidate_index=index,
                own_pages=own_pages,
                gsc_queries=gsc_queries,
            )
            for index, candidate in enumerate(batch, start=1)
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _serialize_candidate_for_batch(
    candidate: SiteContentGapCandidate,
    *,
    candidate_index: int,
    own_pages: list[dict[str, Any]],
    gsc_queries: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_tokens = _candidate_tokens(candidate)
    shortlisted_pages = _select_shortlisted_own_pages(candidate_tokens, own_pages)
    shortlisted_queries = _select_shortlisted_gsc_queries(candidate_tokens, gsc_queries)
    return {
        "candidate_index": candidate_index,
        "source_candidate_id": candidate.id,
        "source_candidate_key": candidate.candidate_key,
        "original_phrase": candidate.original_phrase,
        "original_topic_label": candidate.original_topic_label,
        "normalized_topic_key": candidate.normalized_topic_key,
        "gap_type": candidate.gap_type,
        "source_cluster_key": candidate.source_cluster_key,
        "competitor_count": candidate.competitor_count,
        "own_coverage_hint": candidate.own_coverage_hint,
        "deterministic_priority_score": candidate.deterministic_priority_score,
        "rationale_summary": candidate.rationale_summary,
        "signals": {
            "source_competitor_ids": list(candidate.source_competitor_ids_json or []),
            "source_competitor_page_ids": list(candidate.source_competitor_page_ids_json or []),
            "candidate_tokens": candidate_tokens,
        },
        "own_page_shortlist": shortlisted_pages,
        "gsc_query_shortlist": shortlisted_queries,
    }


def _candidate_tokens(candidate: SiteContentGapCandidate) -> list[str]:
    tokens = tokenize_topic_text(candidate.normalized_topic_key)
    tokens.extend(tokenize_topic_text(candidate.original_phrase))
    tokens.extend(tokenize_topic_text(candidate.original_topic_label))
    deduped: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped[:10]


def _select_shortlisted_own_pages(
    candidate_tokens: list[str],
    own_pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in own_pages:
        shared_terms = sorted(set(candidate_tokens) & set(row["tokens"]))
        if not shared_terms:
            continue
        score = float(len(shared_terms) * 10)
        scored.append((score, row | {"shared_terms": shared_terms}))
    scored.sort(key=lambda item: (-item[0], item[1]["page_id"]))
    return [
        {
            "page_id": row["page_id"],
            "normalized_url": row["normalized_url"],
            "title": row["title"],
            "h1": row["h1"],
            "meta_description": row["meta_description"],
            "page_type": row["page_type"],
            "page_bucket": row["page_bucket"],
            "shared_terms": row["shared_terms"],
        }
        for _score, row in scored[:CONTENT_GAP_REVIEW_MAX_SHORTLIST_PAGES]
    ]


def _select_shortlisted_gsc_queries(
    candidate_tokens: list[str],
    gsc_queries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in gsc_queries:
        shared_terms = sorted(set(candidate_tokens) & set(row["tokens"]))
        if not shared_terms:
            continue
        score = float(len(shared_terms) * 10 + row["clicks"] + (row["impressions"] / 100.0))
        scored.append((score, row | {"shared_terms": shared_terms}))
    scored.sort(key=lambda item: (-item[0], item[1]["query"], item[1]["normalized_url"] or ""))
    return [
        {
            "query": row["query"],
            "clicks": row["clicks"],
            "impressions": row["impressions"],
            "position": row["position"],
            "normalized_url": row["normalized_url"],
            "shared_terms": row["shared_terms"],
        }
        for _score, row in scored[:CONTENT_GAP_REVIEW_MAX_SHORTLIST_QUERIES]
    ]


def _build_context_tokens(*values: str | None) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for value in values:
        for token in tokenize_topic_text(value):
            if token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens


def _normalize_summary_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = collapse_whitespace(value)
        if not text or text in cleaned:
            continue
        cleaned.append(text[:160])
    return cleaned[:3]


def _clean_optional_text(value: str | None, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = collapse_whitespace(value)
    if not cleaned:
        return None
    return cleaned[:max_length]


def _normalize_execution_error(exc: Exception) -> ContentGapReviewLlmServiceError:
    if isinstance(exc, ContentGapReviewLlmServiceError):
        return exc
    if isinstance(exc, content_gap_review_run_service.ContentGapReviewRunServiceError):
        return ContentGapReviewLlmServiceError(str(exc), code=exc.code)
    if isinstance(exc, content_gap_item_materialization_service.ContentGapItemMaterializationServiceError):
        return ContentGapReviewLlmServiceError(str(exc), code=exc.code)
    return ContentGapReviewLlmServiceError(
        "Content Gap review execution failed due to an unexpected backend error.",
        code="content_gap_review_execution_failed",
    )


def _mark_run_failed(
    session: Session,
    *,
    run: SiteContentGapReviewRun,
    error: ContentGapReviewLlmServiceError,
) -> None:
    content_gap_review_run_service._fail_review_run_in_session(
        session,
        site_id=run.site_id,
        run_id=run.run_id,
        error_code=error.code,
        error_message_safe=str(error),
    )
    session.commit()


def _resolve_unavailable_code() -> str:
    settings = get_settings()
    if not settings.openai_llm_enabled:
        return "llm_disabled"
    if not settings.openai_api_key:
        return "missing_api_key"
    return "llm_unavailable"


def _resolve_unavailable_message() -> str:
    settings = get_settings()
    if not settings.openai_llm_enabled:
        return "OpenAI Content Gap review is disabled in backend config."
    if not settings.openai_api_key:
        return "OPENAI_API_KEY is missing in backend config."
    return "OpenAI Content Gap review is currently unavailable."


def _hash_payload(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
