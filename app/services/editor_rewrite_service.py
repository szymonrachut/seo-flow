from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.text_processing import collapse_whitespace
from app.db.models import (
    EditorDocument,
    EditorDocumentBlock,
    EditorReviewIssue,
    EditorReviewRun,
    EditorRewriteRun,
    Site,
    utcnow,
)
from app.services.editor_block_parser_service import build_editor_block_content_hash, build_editor_block_html
import app.services.editor_document_version_service as editor_document_version_service
import app.services.editor_rewrite_llm_service as editor_rewrite_llm_service
import app.services.editor_review_run_service as editor_review_run_service


DISMISSABLE_ISSUE_STATUSES = {"open", "rewrite_ready", "rewrite_requested"}
MANUAL_RESOLVABLE_ISSUE_STATUSES = {"open", "rewrite_ready", "rewrite_requested"}
REWRITE_REQUESTABLE_ISSUE_STATUSES = {"open", "rewrite_ready"}
APPLYABLE_ISSUE_STATUSES = {"rewrite_ready"}
TERMINAL_ISSUE_STATUSES = {"dismissed", "applied", "resolved_manual"}


class EditorRewriteServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "editor_rewrite_service_error") -> None:
        super().__init__(message)
        self.code = code


def dismiss_issue(
    session: Session,
    site_id: int,
    document_id: int,
    issue_id: int,
    *,
    dismiss_reason: str | None = None,
) -> dict[str, Any]:
    _get_document_or_raise(session, site_id, document_id)
    issue = _get_issue_or_raise(session, document_id, issue_id)
    _ensure_issue_status(issue, allowed_statuses=DISMISSABLE_ISSUE_STATUSES, action="dismiss")
    _ensure_issue_review_is_current(session, issue)

    now = utcnow()
    issue.status = "dismissed"
    issue.dismiss_reason = _trim_text_or_none(dismiss_reason, max_length=1000)
    issue.resolution_note = None
    issue.replacement_candidate_text = None
    issue.resolved_at = now
    issue.updated_at = now
    session.flush()
    return _serialize_issue(issue)


def resolve_issue_manually(
    session: Session,
    site_id: int,
    document_id: int,
    issue_id: int,
    *,
    resolution_note: str | None = None,
) -> dict[str, Any]:
    _get_document_or_raise(session, site_id, document_id)
    issue = _get_issue_or_raise(session, document_id, issue_id)
    _ensure_issue_status(issue, allowed_statuses=MANUAL_RESOLVABLE_ISSUE_STATUSES, action="resolve manually")
    _ensure_issue_review_is_current(session, issue)

    now = utcnow()
    issue.status = "resolved_manual"
    issue.dismiss_reason = None
    issue.resolution_note = _trim_text_or_none(resolution_note, max_length=1000)
    issue.replacement_candidate_text = None
    issue.resolved_at = now
    issue.updated_at = now
    session.flush()
    return _serialize_issue(issue)


def request_issue_rewrite(
    session: Session,
    site_id: int,
    document_id: int,
    issue_id: int,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)
    issue = _get_issue_or_raise(session, document_id, issue_id)
    _ensure_issue_status(issue, allowed_statuses=REWRITE_REQUESTABLE_ISSUE_STATUSES, action="request rewrite for")
    _ensure_issue_review_is_current(session, issue)

    active_blocks = _load_active_blocks(session, document.id)
    target_block = _get_active_block_or_raise(active_blocks, issue.block_key)
    input_hash = editor_rewrite_llm_service.build_input_hash(
        document,
        active_blocks,
        target_block,
        issue,
    )
    now = utcnow()
    rewrite_run = EditorRewriteRun(
        document_id=document.id,
        review_issue_id=issue.id,
        block_key=issue.block_key,
        status="queued",
        model_name=editor_rewrite_llm_service.get_llm_model_name(),
        prompt_version=editor_rewrite_llm_service.EDITOR_REWRITE_LLM_PROMPT_VERSION,
        schema_version=editor_rewrite_llm_service.EDITOR_REWRITE_LLM_SCHEMA_VERSION,
        input_hash=input_hash,
        source_block_content_hash=target_block.content_hash,
        created_at=now,
        updated_at=now,
    )
    session.add(rewrite_run)
    session.flush()

    previous_status = issue.status
    previous_candidate_text = issue.replacement_candidate_text
    _mark_issue_rewrite_requested(issue)
    _mark_rewrite_run_running(rewrite_run)
    session.flush()

    try:
        result = editor_rewrite_llm_service.rewrite_issue_block(
            document,
            active_blocks,
            target_block,
            issue,
            client=client,
        )
        rewrite_run.model_name = result.llm_model
        rewrite_run.prompt_version = result.prompt_version
        rewrite_run.schema_version = result.schema_version
        rewrite_run.result_text = result.rewritten_text
        _mark_rewrite_run_completed(rewrite_run)
        _mark_issue_rewrite_ready(issue, rewritten_text=result.rewritten_text)
    except editor_rewrite_llm_service.EditorRewriteLlmServiceError as exc:
        _mark_rewrite_run_failed(rewrite_run, error_code=exc.code, error_message=str(exc))
        _restore_issue_after_rewrite_failure(
            issue,
            previous_status=previous_status,
            previous_candidate_text=previous_candidate_text,
        )
    except Exception as exc:  # pragma: no cover - defensive fallback
        _mark_rewrite_run_failed(
            rewrite_run,
            error_code=getattr(exc, "code", None) or "editor_rewrite_generation_failed",
            error_message=str(exc),
        )
        _restore_issue_after_rewrite_failure(
            issue,
            previous_status=previous_status,
            previous_candidate_text=previous_candidate_text,
        )

    session.flush()
    return _serialize_rewrite_run(session, rewrite_run)


def get_rewrite_run(
    session: Session,
    site_id: int,
    document_id: int,
    rewrite_run_id: int,
) -> dict[str, Any]:
    _get_document_or_raise(session, site_id, document_id)
    rewrite_run = _get_rewrite_run_or_raise(session, document_id, rewrite_run_id)
    return _serialize_rewrite_run(session, rewrite_run)


def list_issue_rewrite_runs(
    session: Session,
    site_id: int,
    document_id: int,
    issue_id: int,
) -> dict[str, Any]:
    _get_document_or_raise(session, site_id, document_id)
    issue = _get_issue_or_raise(session, document_id, issue_id)
    runs = session.scalars(
        select(EditorRewriteRun)
        .where(
            EditorRewriteRun.document_id == document_id,
            EditorRewriteRun.review_issue_id == issue.id,
        )
        .order_by(EditorRewriteRun.created_at.desc(), EditorRewriteRun.id.desc())
    ).all()
    return {
        "document_id": document_id,
        "review_issue_id": issue.id,
        "items": [_serialize_rewrite_run(session, run) for run in runs],
    }


def apply_rewrite_run(
    session: Session,
    site_id: int,
    document_id: int,
    rewrite_run_id: int,
) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)
    rewrite_run = _get_rewrite_run_or_raise(session, document_id, rewrite_run_id)
    if rewrite_run.review_issue_id is None:
        raise EditorRewriteServiceError(
            f"Rewrite run {rewrite_run_id} is not linked to an issue.",
            code="rewrite_issue_missing",
        )

    issue = _get_issue_or_raise(session, document_id, int(rewrite_run.review_issue_id))
    if issue.block_key != rewrite_run.block_key:
        raise EditorRewriteServiceError(
            "Rewrite run block_key does not match the linked issue.",
            code="rewrite_issue_block_mismatch",
        )
    if rewrite_run.status == "applied":
        raise EditorRewriteServiceError(
            f"Rewrite run {rewrite_run_id} has already been applied.",
            code="rewrite_already_applied",
        )
    if rewrite_run.status != "completed":
        raise EditorRewriteServiceError(
            f"Rewrite run {rewrite_run_id} must be completed before apply.",
            code="rewrite_not_ready",
        )
    if issue.status not in APPLYABLE_ISSUE_STATUSES:
        raise EditorRewriteServiceError(
            f"Issue {issue.id} is not ready for apply from status '{issue.status}'.",
            code="issue_not_ready_for_apply",
        )

    rewritten_text = _trim_text_or_none(rewrite_run.result_text, max_length=12000)
    if not rewritten_text:
        raise EditorRewriteServiceError(
            f"Rewrite run {rewrite_run_id} has no generated text to apply.",
            code="rewrite_result_missing",
        )

    active_blocks = _load_active_blocks(session, document.id)
    target_block = _get_active_block_or_raise(active_blocks, rewrite_run.block_key)
    current_input_hash = editor_rewrite_llm_service.build_input_hash(
        document,
        active_blocks,
        target_block,
        issue,
    )
    if rewrite_run.input_hash and current_input_hash != rewrite_run.input_hash:
        raise EditorRewriteServiceError(
            "Current block state no longer matches the rewrite input that produced this rewrite run.",
            code="rewrite_input_mismatch",
        )

    now = utcnow()
    target_block.is_active = False
    target_block.updated_at = now

    updated_block = EditorDocumentBlock(
        document_id=document.id,
        block_key=target_block.block_key,
        block_type=target_block.block_type,
        block_level=target_block.block_level,
        parent_block_key=target_block.parent_block_key,
        position_index=target_block.position_index,
        text_content=rewritten_text,
        html_content=build_editor_block_html(
            block_type=target_block.block_type,
            block_level=target_block.block_level,
            text_content=rewritten_text,
        ),
        context_path=target_block.context_path,
        content_hash=build_editor_block_content_hash(
            block_type=target_block.block_type,
            block_level=target_block.block_level,
            text_content=rewritten_text,
            context_path=target_block.context_path,
        ),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(updated_block)
    session.flush()

    editor_document_version_service.refresh_active_block_contexts(session, document.id)
    session.flush()
    session.refresh(updated_block)
    active_blocks = _load_active_blocks(session, document.id)
    editor_document_version_service.sync_document_representations_from_blocks(document, active_blocks)
    editor_document_version_service.capture_document_version(
        session,
        document,
        source_of_change="rewrite_apply",
        metadata_json={
            "block_key": target_block.block_key,
            "review_issue_id": issue.id,
            "rewrite_run_id": rewrite_run.id,
        },
        active_blocks=active_blocks,
    )

    issue.status = "applied"
    issue.dismiss_reason = None
    issue.resolution_note = issue.resolution_note or "Applied AI rewrite."
    issue.replacement_candidate_text = rewritten_text
    issue.resolved_at = now
    issue.updated_at = now

    rewrite_run.status = "applied"
    rewrite_run.applied_at = now
    rewrite_run.updated_at = now
    rewrite_run.error_code = None
    rewrite_run.error_message = None

    session.flush()

    return {
        "document": _serialize_document(session, document),
        "issue": _serialize_issue(issue),
        "rewrite_run": _serialize_rewrite_run(session, rewrite_run),
        "updated_block": _serialize_block(updated_block),
    }


def _get_site_or_raise(session: Session, site_id: int) -> Site:
    site = session.get(Site, site_id)
    if site is None:
        raise EditorRewriteServiceError(f"Site {site_id} not found.", code="not_found")
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
        raise EditorRewriteServiceError(
            f"Editor document {document_id} for site {site_id} not found.",
            code="not_found",
        )
    return document


def _get_issue_or_raise(session: Session, document_id: int, issue_id: int) -> EditorReviewIssue:
    issue = session.scalar(
        select(EditorReviewIssue)
        .where(
            EditorReviewIssue.id == issue_id,
            EditorReviewIssue.document_id == document_id,
        )
        .limit(1)
    )
    if issue is None:
        raise EditorRewriteServiceError(
            f"Editor review issue {issue_id} for document {document_id} not found.",
            code="not_found",
        )
    return issue


def _get_rewrite_run_or_raise(session: Session, document_id: int, rewrite_run_id: int) -> EditorRewriteRun:
    rewrite_run = session.scalar(
        select(EditorRewriteRun)
        .where(
            EditorRewriteRun.id == rewrite_run_id,
            EditorRewriteRun.document_id == document_id,
        )
        .limit(1)
    )
    if rewrite_run is None:
        raise EditorRewriteServiceError(
            f"Editor rewrite run {rewrite_run_id} for document {document_id} not found.",
            code="not_found",
        )
    return rewrite_run


def _load_active_blocks(session: Session, document_id: int) -> list[EditorDocumentBlock]:
    return session.scalars(
        select(EditorDocumentBlock)
        .where(
            EditorDocumentBlock.document_id == document_id,
            EditorDocumentBlock.is_active.is_(True),
        )
        .order_by(EditorDocumentBlock.position_index.asc(), EditorDocumentBlock.id.asc())
    ).all()


def _get_active_block_or_raise(
    active_blocks: list[EditorDocumentBlock],
    block_key: str,
) -> EditorDocumentBlock:
    normalized_block_key = collapse_whitespace(block_key)
    for block in active_blocks:
        if block.block_key == normalized_block_key:
            return block
    raise EditorRewriteServiceError(
        f"Active block {normalized_block_key} was not found in the current document state.",
        code="active_block_not_found",
    )


def _ensure_issue_status(
    issue: EditorReviewIssue,
    *,
    allowed_statuses: set[str],
    action: str,
) -> None:
    if issue.status in TERMINAL_ISSUE_STATUSES and issue.status not in allowed_statuses:
        raise EditorRewriteServiceError(
            f"Issue {issue.id} cannot be used to {action} because it is already '{issue.status}'.",
            code="issue_not_actionable",
        )
    if issue.status not in allowed_statuses:
        raise EditorRewriteServiceError(
            f"Issue {issue.id} cannot be used to {action} from status '{issue.status}'.",
            code="invalid_issue_status",
        )


def _ensure_issue_review_is_current(session: Session, issue: EditorReviewIssue) -> None:
    review_run = session.get(EditorReviewRun, issue.review_run_id)
    if review_run is None:
        raise EditorRewriteServiceError(
            f"Review run {issue.review_run_id} for issue {issue.id} was not found.",
            code="review_run_not_found",
        )
    if not editor_review_run_service.review_run_matches_current_document(session, review_run):
        raise EditorRewriteServiceError(
            "This issue belongs to a stale review of an older document state. Run review again before changing issue workflow.",
            code="issue_review_stale",
        )


def _mark_issue_rewrite_requested(issue: EditorReviewIssue) -> None:
    issue.status = "rewrite_requested"
    issue.resolved_at = None
    issue.updated_at = utcnow()


def _mark_issue_rewrite_ready(issue: EditorReviewIssue, *, rewritten_text: str) -> None:
    issue.status = "rewrite_ready"
    issue.replacement_candidate_text = rewritten_text
    issue.resolved_at = None
    issue.updated_at = utcnow()


def _restore_issue_after_rewrite_failure(
    issue: EditorReviewIssue,
    *,
    previous_status: str,
    previous_candidate_text: str | None,
) -> None:
    issue.status = previous_status if previous_status in REWRITE_REQUESTABLE_ISSUE_STATUSES else "open"
    issue.replacement_candidate_text = previous_candidate_text
    issue.resolved_at = None
    issue.updated_at = utcnow()


def _mark_rewrite_run_running(rewrite_run: EditorRewriteRun) -> None:
    now = utcnow()
    rewrite_run.status = "running"
    rewrite_run.started_at = now
    rewrite_run.finished_at = None
    rewrite_run.applied_at = None
    rewrite_run.error_code = None
    rewrite_run.error_message = None
    rewrite_run.updated_at = now


def _mark_rewrite_run_completed(rewrite_run: EditorRewriteRun) -> None:
    now = utcnow()
    rewrite_run.status = "completed"
    rewrite_run.finished_at = now
    rewrite_run.error_code = None
    rewrite_run.error_message = None
    rewrite_run.updated_at = now


def _mark_rewrite_run_failed(
    rewrite_run: EditorRewriteRun,
    *,
    error_code: str,
    error_message: str,
) -> None:
    now = utcnow()
    rewrite_run.status = "failed"
    rewrite_run.finished_at = now
    rewrite_run.error_code = (error_code or "editor_rewrite_failed")[:64]
    rewrite_run.error_message = (error_message or "Editor rewrite failed.")[:1000]
    rewrite_run.updated_at = now


def _trim_text_or_none(value: str | None, *, max_length: int) -> str | None:
    cleaned = collapse_whitespace(value or "")
    if not cleaned:
        return None
    return cleaned[:max_length]


def _count_active_blocks(session: Session, document_id: int) -> int:
    count = session.scalar(
        select(func.count(EditorDocumentBlock.id)).where(
            EditorDocumentBlock.document_id == document_id,
            EditorDocumentBlock.is_active.is_(True),
        )
    )
    return int(count or 0)


def _refresh_document_normalized_content(session: Session, document: EditorDocument) -> None:
    active_blocks = _load_active_blocks(session, document.id)
    editor_document_version_service.sync_document_representations_from_blocks(document, active_blocks)


def _serialize_document(session: Session, document: EditorDocument) -> dict[str, Any]:
    return {
        "id": document.id,
        "site_id": document.site_id,
        "title": document.title,
        "document_type": document.document_type,
        "source_format": document.source_format,
        "source_content": document.source_content,
        "normalized_content": document.normalized_content,
        "topic_brief_json": document.topic_brief_json,
        "facts_context_json": document.facts_context_json,
        "status": document.status,
        "active_block_count": _count_active_blocks(session, document.id),
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def _serialize_block(block: EditorDocumentBlock) -> dict[str, Any]:
    return {
        "id": block.id,
        "document_id": block.document_id,
        "block_key": block.block_key,
        "block_type": block.block_type,
        "block_level": block.block_level,
        "parent_block_key": block.parent_block_key,
        "position_index": block.position_index,
        "text_content": block.text_content,
        "html_content": block.html_content,
        "context_path": block.context_path,
        "content_hash": block.content_hash,
        "is_active": block.is_active,
        "created_at": block.created_at,
        "updated_at": block.updated_at,
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


def _serialize_rewrite_run(session: Session, rewrite_run: EditorRewriteRun) -> dict[str, Any]:
    matches_current_document = _rewrite_run_matches_current_document(session, rewrite_run)
    matches_current_block = _rewrite_run_matches_current_block(session, rewrite_run)
    return {
        "id": rewrite_run.id,
        "document_id": rewrite_run.document_id,
        "review_issue_id": rewrite_run.review_issue_id,
        "block_key": rewrite_run.block_key,
        "status": rewrite_run.status,
        "model_name": rewrite_run.model_name,
        "prompt_version": rewrite_run.prompt_version,
        "schema_version": rewrite_run.schema_version,
        "input_hash": rewrite_run.input_hash,
        "source_block_content_hash": rewrite_run.source_block_content_hash,
        "result_text": rewrite_run.result_text,
        "started_at": rewrite_run.started_at,
        "finished_at": rewrite_run.finished_at,
        "applied_at": rewrite_run.applied_at,
        "error_code": rewrite_run.error_code,
        "error_message": rewrite_run.error_message,
        "matches_current_document": matches_current_document,
        "matches_current_block": matches_current_block,
        "is_stale": not matches_current_document,
        "created_at": rewrite_run.created_at,
        "updated_at": rewrite_run.updated_at,
    }


def _rewrite_run_matches_current_block(session: Session, rewrite_run: EditorRewriteRun) -> bool:
    document = session.get(EditorDocument, rewrite_run.document_id)
    if document is None:
        return False
    active_blocks = _load_active_blocks(session, document.id)
    target_block = next((block for block in active_blocks if block.block_key == rewrite_run.block_key), None)
    if target_block is None:
        return False
    if not rewrite_run.source_block_content_hash:
        return True
    return target_block.content_hash == rewrite_run.source_block_content_hash


def _rewrite_run_matches_current_document(session: Session, rewrite_run: EditorRewriteRun) -> bool:
    document = session.get(EditorDocument, rewrite_run.document_id)
    if document is None:
        return False
    if rewrite_run.review_issue_id is None:
        return False
    issue = session.get(EditorReviewIssue, rewrite_run.review_issue_id)
    if issue is None:
        return False
    active_blocks = _load_active_blocks(session, document.id)
    target_block = next((block for block in active_blocks if block.block_key == rewrite_run.block_key), None)
    if target_block is None:
        return False
    if not rewrite_run.input_hash:
        return _rewrite_run_matches_current_block(session, rewrite_run)
    current_input_hash = editor_rewrite_llm_service.build_input_hash(
        document,
        active_blocks,
        target_block,
        issue,
    )
    return current_input_hash == rewrite_run.input_hash
