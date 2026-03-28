from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.text_processing import collapse_whitespace
from app.db.models import (
    EditorDocument,
    EditorDocumentBlock,
    EditorReviewIssue,
    EditorReviewRun,
    Site,
    utcnow,
)
import app.services.editor_review_engine_service as editor_review_engine_service
import app.services.editor_document_version_service as editor_document_version_service
import app.services.editor_review_llm_service as editor_review_llm_service


class EditorReviewRunServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "editor_review_run_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class _ReviewEngineSpec:
    engine_kind: str
    engine_version: str
    model_name: str | None
    prompt_version: str | None
    schema_version: str | None


def create_review_run(
    session: Session,
    site_id: int,
    document_id: int,
    *,
    review_mode: str = "standard",
    client: Any | None = None,
    engine_mode: str | None = None,
) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)
    active_blocks = _load_active_blocks(session, document_id)
    normalized_review_mode = _normalize_review_mode(review_mode)
    document_version_hash = editor_document_version_service.build_current_document_version_hash(
        document,
        active_blocks=active_blocks,
    )
    engine_spec = _select_review_engine(client=client, engine_mode=engine_mode)
    input_hash = _build_input_hash(
        document_version_hash=document_version_hash,
        review_mode=normalized_review_mode,
        block_count=len(active_blocks),
        engine_version=engine_spec.engine_version,
    )

    now = utcnow()
    run = EditorReviewRun(
        document_id=document.id,
        document_version_hash=document_version_hash,
        review_mode=normalized_review_mode,
        status="queued",
        model_name=engine_spec.model_name,
        prompt_version=engine_spec.prompt_version,
        schema_version=engine_spec.schema_version,
        input_hash=input_hash,
        created_at=now,
        updated_at=now,
    )
    session.add(run)
    session.flush()

    _mark_run_running(run)
    session.flush()

    if not active_blocks:
        _mark_run_failed(
            run,
            error_code="no_active_blocks",
            error_message="Review run requires an active parsed block set for the document.",
        )
        session.flush()
        return _serialize_review_run(session, run)

    try:
        if engine_spec.engine_kind == "llm":
            llm_result = editor_review_llm_service.review_document(
                document,
                active_blocks,
                review_mode=normalized_review_mode,
                client=client,
            )
            run.model_name = llm_result.llm_model
            run.prompt_version = llm_result.prompt_version
            run.schema_version = llm_result.schema_version
            issue_drafts = llm_result.issue_drafts
        else:
            issue_drafts = editor_review_engine_service.generate_review_issues(
                active_blocks,
                review_mode=normalized_review_mode,
            )
        issue_rows = [
            EditorReviewIssue(
                review_run_id=run.id,
                document_id=document.id,
                block_key=draft.block_key,
                issue_type=draft.issue_type,
                severity=draft.severity,
                confidence=draft.confidence,
                message=draft.message,
                reason=draft.reason,
                replacement_instruction=draft.replacement_instruction,
                replacement_candidate_text=draft.replacement_candidate_text,
                status="open",
                created_at=now,
                updated_at=now,
            )
            for draft in issue_drafts
        ]
        if issue_rows:
            session.add_all(issue_rows)
        _mark_run_completed(run)
    except editor_review_llm_service.EditorReviewLlmServiceError as exc:
        _mark_run_failed(
            run,
            error_code=exc.code,
            error_message=str(exc),
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        _mark_run_failed(
            run,
            error_code=getattr(exc, "code", None) or "editor_review_engine_error",
            error_message=str(exc),
        )

    session.flush()
    return _serialize_review_run(session, run)


def get_review_run(
    session: Session,
    site_id: int,
    document_id: int,
    review_run_id: int,
) -> dict[str, Any]:
    run = _get_review_run_or_raise(session, site_id, document_id, review_run_id)
    return _serialize_review_run(session, run)


def list_review_runs(session: Session, site_id: int, document_id: int) -> dict[str, Any]:
    _get_document_or_raise(session, site_id, document_id)
    rows = session.scalars(
        select(EditorReviewRun)
        .where(EditorReviewRun.document_id == document_id)
        .order_by(EditorReviewRun.created_at.desc(), EditorReviewRun.id.desc())
    ).all()
    return {
        "document_id": document_id,
        "items": [_serialize_review_run(session, row) for row in rows],
    }


def list_document_issues(session: Session, site_id: int, document_id: int) -> dict[str, Any]:
    _get_document_or_raise(session, site_id, document_id)
    latest_run = _get_latest_review_run(session, document_id)
    if latest_run is None:
        return {
            "document_id": document_id,
            "review_run_id": None,
            "review_run_status": None,
            "review_mode": None,
            "review_matches_current_document": None,
            "items": [],
        }
    return {
        "document_id": document_id,
        "review_run_id": latest_run.id,
        "review_run_status": latest_run.status,
        "review_mode": latest_run.review_mode,
        "review_matches_current_document": review_run_matches_current_document(session, latest_run),
        "items": [_serialize_issue(issue) for issue in _load_run_issues(session, latest_run.id)],
    }


def list_review_run_issues(
    session: Session,
    site_id: int,
    document_id: int,
    review_run_id: int,
) -> dict[str, Any]:
    run = _get_review_run_or_raise(session, site_id, document_id, review_run_id)
    return {
        "document_id": document_id,
        "review_run_id": run.id,
        "review_run_status": run.status,
        "review_mode": run.review_mode,
        "review_matches_current_document": review_run_matches_current_document(session, run),
        "items": [_serialize_issue(issue) for issue in _load_run_issues(session, run.id)],
    }


def get_review_summary(session: Session, site_id: int, document_id: int) -> dict[str, Any]:
    _get_document_or_raise(session, site_id, document_id)
    review_runs_count = int(
        session.scalar(select(func.count(EditorReviewRun.id)).where(EditorReviewRun.document_id == document_id)) or 0
    )
    latest_run = _get_latest_review_run(session, document_id)
    if latest_run is None:
        return {
            "document_id": document_id,
            "review_run_count": 0,
            "latest_review_run_id": None,
            "latest_review_run_status": None,
            "latest_review_run_finished_at": None,
            "issue_count": 0,
            "issue_block_count": 0,
            "severity_counts": {"low": 0, "medium": 0, "high": 0},
        }

    issue_rows = _load_run_issues(session, latest_run.id)
    issue_count, issue_block_count, severity_counts = _summarize_issues(issue_rows)
    return {
        "document_id": document_id,
        "review_run_count": review_runs_count,
        "latest_review_run_id": latest_run.id,
        "latest_review_run_status": latest_run.status,
        "latest_review_run_finished_at": latest_run.finished_at,
        "latest_review_matches_current_document": review_run_matches_current_document(session, latest_run),
        "issue_count": issue_count,
        "issue_block_count": issue_block_count,
        "severity_counts": severity_counts,
    }


def _get_site_or_raise(session: Session, site_id: int) -> Site:
    site = session.get(Site, site_id)
    if site is None:
        raise EditorReviewRunServiceError(f"Site {site_id} not found.", code="not_found")
    return site


def _get_document_or_raise(session: Session, site_id: int, document_id: int) -> EditorDocument:
    _get_site_or_raise(session, site_id)
    document = session.scalar(
        select(EditorDocument)
        .where(
            EditorDocument.id == document_id,
            EditorDocument.site_id == site_id,
        )
        .limit(1)
    )
    if document is None:
        raise EditorReviewRunServiceError(
            f"Editor document {document_id} for site {site_id} not found.",
            code="not_found",
        )
    return document


def _get_review_run_or_raise(
    session: Session,
    site_id: int,
    document_id: int,
    review_run_id: int,
) -> EditorReviewRun:
    _get_document_or_raise(session, site_id, document_id)
    run = session.scalar(
        select(EditorReviewRun)
        .where(
            EditorReviewRun.id == review_run_id,
            EditorReviewRun.document_id == document_id,
        )
        .limit(1)
    )
    if run is None:
        raise EditorReviewRunServiceError(
            f"Editor review run {review_run_id} for document {document_id} not found.",
            code="not_found",
        )
    return run


def _get_latest_review_run(session: Session, document_id: int) -> EditorReviewRun | None:
    return session.scalar(
        select(EditorReviewRun)
        .where(EditorReviewRun.document_id == document_id)
        .order_by(EditorReviewRun.created_at.desc(), EditorReviewRun.id.desc())
        .limit(1)
    )


def _load_active_blocks(session: Session, document_id: int) -> list[EditorDocumentBlock]:
    return session.scalars(
        select(EditorDocumentBlock)
        .where(
            EditorDocumentBlock.document_id == document_id,
            EditorDocumentBlock.is_active.is_(True),
        )
        .order_by(EditorDocumentBlock.position_index.asc(), EditorDocumentBlock.id.asc())
    ).all()


def _load_run_issues(session: Session, review_run_id: int) -> list[EditorReviewIssue]:
    return session.scalars(
        select(EditorReviewIssue)
        .where(EditorReviewIssue.review_run_id == review_run_id)
        .order_by(EditorReviewIssue.id.asc())
    ).all()


def _serialize_review_run(session: Session, run: EditorReviewRun) -> dict[str, Any]:
    issues = _load_run_issues(session, run.id)
    issue_count, issue_block_count, severity_counts = _summarize_issues(issues)
    return {
        "id": run.id,
        "document_id": run.document_id,
        "document_version_hash": run.document_version_hash,
        "review_mode": run.review_mode,
        "status": run.status,
        "model_name": run.model_name,
        "prompt_version": run.prompt_version,
        "schema_version": run.schema_version,
        "input_hash": run.input_hash,
        "issue_count": issue_count,
        "issue_block_count": issue_block_count,
        "severity_counts": severity_counts,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "matches_current_document": review_run_matches_current_document(session, run),
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _serialize_issue(issue: EditorReviewIssue) -> dict[str, Any]:
    return {
        "id": issue.id,
        "review_run_id": issue.review_run_id,
        "document_id": issue.document_id,
        "block_key": issue.block_key,
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "confidence": issue.confidence,
        "message": issue.message,
        "reason": issue.reason,
        "replacement_instruction": issue.replacement_instruction,
        "replacement_candidate_text": issue.replacement_candidate_text,
        "status": issue.status,
        "dismiss_reason": issue.dismiss_reason,
        "resolution_note": issue.resolution_note,
        "created_at": issue.created_at,
        "updated_at": issue.updated_at,
        "resolved_at": issue.resolved_at,
    }


def _summarize_issues(issues: list[EditorReviewIssue]) -> tuple[int, int, dict[str, int]]:
    severity_counts = Counter(issue.severity for issue in issues)
    block_keys = {issue.block_key for issue in issues}
    return (
        len(issues),
        len(block_keys),
        {
            "low": int(severity_counts.get("low", 0)),
            "medium": int(severity_counts.get("medium", 0)),
            "high": int(severity_counts.get("high", 0)),
        },
    )


def _build_input_hash(*, document_version_hash: str, review_mode: str, block_count: int, engine_version: str) -> str:
    payload = {
        "document_version_hash": document_version_hash,
        "review_mode": review_mode,
        "block_count": block_count,
        "engine_version": engine_version,
    }
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _select_review_engine(*, client: Any | None, engine_mode: str | None) -> _ReviewEngineSpec:
    normalized_engine_mode = _normalize_engine_mode(engine_mode or get_settings().editor_review_engine_mode)
    if normalized_engine_mode == "mock":
        return _mock_engine_spec()
    if normalized_engine_mode == "llm":
        return _llm_engine_spec()
    if editor_review_llm_service.llm_is_available(client):
        return _llm_engine_spec()
    return _mock_engine_spec()


def _mock_engine_spec() -> _ReviewEngineSpec:
    return _ReviewEngineSpec(
        engine_kind="mock",
        engine_version=editor_review_engine_service.MOCK_EDITOR_REVIEW_ENGINE_VERSION,
        model_name=editor_review_engine_service.MOCK_EDITOR_REVIEW_MODEL_NAME,
        prompt_version=editor_review_engine_service.MOCK_EDITOR_REVIEW_PROMPT_VERSION,
        schema_version=editor_review_engine_service.MOCK_EDITOR_REVIEW_SCHEMA_VERSION,
    )


def _llm_engine_spec() -> _ReviewEngineSpec:
    llm_model = editor_review_llm_service.get_llm_model_name()
    return _ReviewEngineSpec(
        engine_kind="llm",
        engine_version=editor_review_llm_service.build_engine_version(llm_model=llm_model),
        model_name=llm_model,
        prompt_version=editor_review_llm_service.EDITOR_REVIEW_LLM_PROMPT_VERSION,
        schema_version=editor_review_llm_service.EDITOR_REVIEW_LLM_SCHEMA_VERSION,
    )


def _normalize_review_mode(review_mode: str | None) -> str:
    normalized_mode = collapse_whitespace(review_mode or "standard").lower()
    if normalized_mode in {"standard", "strict", "light"}:
        return normalized_mode
    return "standard"


def _normalize_engine_mode(engine_mode: str | None) -> str:
    normalized_mode = collapse_whitespace(engine_mode or "auto").lower()
    if normalized_mode in {"auto", "mock", "llm"}:
        return normalized_mode
    return "auto"


def _mark_run_running(run: EditorReviewRun) -> None:
    now = utcnow()
    run.status = "running"
    run.started_at = now
    run.finished_at = None
    run.error_code = None
    run.error_message = None
    run.updated_at = now


def _mark_run_completed(run: EditorReviewRun) -> None:
    now = utcnow()
    run.status = "completed"
    run.finished_at = now
    run.error_code = None
    run.error_message = None
    run.updated_at = now


def _mark_run_failed(run: EditorReviewRun, *, error_code: str, error_message: str) -> None:
    now = utcnow()
    run.status = "failed"
    run.finished_at = now
    run.error_code = (error_code or "editor_review_run_failed")[:64]
    run.error_message = (error_message or "Editor review run failed.")[:1000]
    run.updated_at = now


def review_run_matches_current_document(session: Session, run: EditorReviewRun) -> bool:
    document = session.get(EditorDocument, run.document_id)
    if document is None:
        return False
    active_blocks = _load_active_blocks(session, document.id)
    current_document_hash = editor_document_version_service.build_current_document_version_hash(
        document,
        active_blocks=active_blocks,
    )
    return current_document_hash == run.document_version_hash
