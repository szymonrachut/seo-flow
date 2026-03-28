from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.ai_review_editor import (
    EditorDocumentBlockListResponse,
    EditorDocumentBlockDeleteResponse,
    EditorDocumentBlockInsertRequest,
    EditorDocumentBlockInsertResponse,
    EditorDocumentBlockUpdateRequest,
    EditorDocumentBlockUpdateResponse,
    EditorDocumentCreateRequest,
    EditorDocumentListResponse,
    EditorDocumentParseResponse,
    EditorDocumentResponse,
    EditorDocumentUpdateRequest,
    EditorDocumentVersionDiffResponse,
    EditorDocumentVersionListResponse,
    EditorDocumentVersionResponse,
    EditorDocumentVersionRestoreRequest,
    EditorDocumentVersionRestoreResponse,
    EditorRewriteApplyRequest,
    EditorRewriteApplyResponse,
    EditorRewriteRunCreateRequest,
    EditorRewriteRunListResponse,
    EditorRewriteRunResponse,
    EditorReviewIssueDismissRequest,
    EditorReviewIssueManualResolveRequest,
    EditorReviewIssueResponse,
    EditorReviewIssueListResponse,
    EditorReviewRunCreateRequest,
    EditorReviewRunListResponse,
    EditorReviewRunResponse,
    EditorReviewSummaryResponse,
)
import app.services.ai_review_editor_service as ai_review_editor_service
import app.services.editor_document_block_service as editor_document_block_service
import app.services.editor_document_version_service as editor_document_version_service
import app.services.editor_rewrite_service as editor_rewrite_service
import app.services.editor_review_run_service as editor_review_run_service


router = APIRouter(prefix="/sites", tags=["site-ai-review-editor"])


def _raise_http_for_ai_review_editor_error(exc: Exception) -> None:
    detail = str(exc)
    error_code = getattr(exc, "code", None)
    conflict_codes = {
        "already_current_version",
        "block_conflict",
        "invalid_issue_status",
        "issue_not_actionable",
        "issue_not_ready_for_apply",
        "issue_review_stale",
        "rewrite_already_applied",
        "rewrite_input_mismatch",
        "rewrite_not_ready",
    }
    if error_code == "not_found" or "not found" in detail.lower():
        status_code = status.HTTP_404_NOT_FOUND
    elif error_code in conflict_codes:
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.post(
    "/{site_id}/ai-review-editor/documents",
    response_model=EditorDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_editor_document(
    site_id: int,
    payload: EditorDocumentCreateRequest,
    session: Session = Depends(get_db),
) -> EditorDocumentResponse:
    try:
        result = ai_review_editor_service.create_document(
            session,
            site_id,
            title=payload.title,
            document_type=payload.document_type,
            source_format=payload.source_format,
            source_content=payload.source_content,
            topic_brief_json=payload.topic_brief_json,
            facts_context_json=payload.facts_context_json,
        )
    except ai_review_editor_service.AiReviewEditorServiceError as exc:
        _raise_http_for_ai_review_editor_error(exc)
    session.commit()
    return EditorDocumentResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents",
    response_model=EditorDocumentListResponse,
)
def list_editor_documents(
    site_id: int,
    session: Session = Depends(get_db),
) -> EditorDocumentListResponse:
    try:
        result = ai_review_editor_service.list_documents(session, site_id)
    except ai_review_editor_service.AiReviewEditorServiceError as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorDocumentListResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents/{document_id}",
    response_model=EditorDocumentResponse,
)
def get_editor_document(
    site_id: int,
    document_id: int,
    session: Session = Depends(get_db),
) -> EditorDocumentResponse:
    try:
        result = ai_review_editor_service.get_document(session, site_id, document_id)
    except ai_review_editor_service.AiReviewEditorServiceError as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorDocumentResponse.model_validate(result)


@router.put(
    "/{site_id}/ai-review-editor/documents/{document_id}",
    response_model=EditorDocumentResponse,
)
def update_editor_document(
    site_id: int,
    document_id: int,
    payload: EditorDocumentUpdateRequest,
    session: Session = Depends(get_db),
) -> EditorDocumentResponse:
    try:
        result = ai_review_editor_service.update_document(
            session,
            site_id,
            document_id,
            title=payload.title,
            document_type=payload.document_type,
            source_format=payload.source_format,
            source_content=payload.source_content,
            topic_brief_json=payload.topic_brief_json,
            facts_context_json=payload.facts_context_json,
            status=payload.status,
        )
    except ai_review_editor_service.AiReviewEditorServiceError as exc:
        _raise_http_for_ai_review_editor_error(exc)
    session.commit()
    return EditorDocumentResponse.model_validate(result)


@router.post(
    "/{site_id}/ai-review-editor/documents/{document_id}/parse",
    response_model=EditorDocumentParseResponse,
)
def parse_editor_document(
    site_id: int,
    document_id: int,
    session: Session = Depends(get_db),
) -> EditorDocumentParseResponse:
    try:
        result = ai_review_editor_service.parse_document_into_blocks(session, site_id, document_id)
    except ai_review_editor_service.AiReviewEditorServiceError as exc:
        _raise_http_for_ai_review_editor_error(exc)
    session.commit()
    return EditorDocumentParseResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents/{document_id}/blocks",
    response_model=EditorDocumentBlockListResponse,
)
def list_editor_document_blocks(
    site_id: int,
    document_id: int,
    session: Session = Depends(get_db),
) -> EditorDocumentBlockListResponse:
    try:
        result = ai_review_editor_service.list_document_blocks(session, site_id, document_id)
    except ai_review_editor_service.AiReviewEditorServiceError as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorDocumentBlockListResponse.model_validate(result)


@router.post(
    "/{site_id}/ai-review-editor/documents/{document_id}/blocks",
    response_model=EditorDocumentBlockInsertResponse,
    status_code=status.HTTP_201_CREATED,
)
def insert_editor_document_block(
    site_id: int,
    document_id: int,
    payload: EditorDocumentBlockInsertRequest,
    session: Session = Depends(get_db),
) -> EditorDocumentBlockInsertResponse:
    try:
        result = editor_document_block_service.insert_document_block(
            session,
            site_id,
            document_id,
            target_block_key=payload.target_block_key,
            position=payload.position,
            block_type=payload.block_type,
            block_level=payload.block_level,
            text_content=payload.text_content,
        )
    except (
        ai_review_editor_service.AiReviewEditorServiceError,
        editor_document_block_service.EditorDocumentBlockServiceError,
    ) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    session.commit()
    return EditorDocumentBlockInsertResponse.model_validate(result)


@router.put(
    "/{site_id}/ai-review-editor/documents/{document_id}/blocks/{block_key}",
    response_model=EditorDocumentBlockUpdateResponse,
)
def update_editor_document_block(
    site_id: int,
    document_id: int,
    block_key: str,
    payload: EditorDocumentBlockUpdateRequest,
    session: Session = Depends(get_db),
) -> EditorDocumentBlockUpdateResponse:
    try:
        result = editor_document_block_service.update_document_block(
            session,
            site_id,
            document_id,
            block_key,
            text_content=payload.text_content,
            expected_content_hash=payload.expected_content_hash,
        )
    except (
        ai_review_editor_service.AiReviewEditorServiceError,
        editor_document_block_service.EditorDocumentBlockServiceError,
    ) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    session.commit()
    return EditorDocumentBlockUpdateResponse.model_validate(result)


@router.delete(
    "/{site_id}/ai-review-editor/documents/{document_id}/blocks/{block_key}",
    response_model=EditorDocumentBlockDeleteResponse,
)
def delete_editor_document_block(
    site_id: int,
    document_id: int,
    block_key: str,
    session: Session = Depends(get_db),
) -> EditorDocumentBlockDeleteResponse:
    try:
        result = editor_document_block_service.delete_document_block(
            session,
            site_id,
            document_id,
            block_key,
        )
    except (
        ai_review_editor_service.AiReviewEditorServiceError,
        editor_document_block_service.EditorDocumentBlockServiceError,
    ) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    session.commit()
    return EditorDocumentBlockDeleteResponse.model_validate(result)


@router.post(
    "/{site_id}/ai-review-editor/documents/{document_id}/review-runs",
    response_model=EditorReviewRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_editor_review_run(
    site_id: int,
    document_id: int,
    payload: EditorReviewRunCreateRequest,
    session: Session = Depends(get_db),
) -> EditorReviewRunResponse:
    try:
        result = editor_review_run_service.create_review_run(
            session,
            site_id,
            document_id,
            review_mode=payload.review_mode,
        )
    except (ai_review_editor_service.AiReviewEditorServiceError, editor_review_run_service.EditorReviewRunServiceError) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    session.commit()
    return EditorReviewRunResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents/{document_id}/versions",
    response_model=EditorDocumentVersionListResponse,
)
def list_editor_document_versions(
    site_id: int,
    document_id: int,
    session: Session = Depends(get_db),
) -> EditorDocumentVersionListResponse:
    try:
        result = editor_document_version_service.list_document_versions(session, site_id, document_id)
    except editor_document_version_service.EditorDocumentVersionServiceError as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorDocumentVersionListResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents/{document_id}/versions/{version_id}",
    response_model=EditorDocumentVersionResponse,
)
def get_editor_document_version(
    site_id: int,
    document_id: int,
    version_id: int,
    session: Session = Depends(get_db),
) -> EditorDocumentVersionResponse:
    try:
        result = editor_document_version_service.get_document_version(session, site_id, document_id, version_id)
    except editor_document_version_service.EditorDocumentVersionServiceError as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorDocumentVersionResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents/{document_id}/versions/{version_id}/diff",
    response_model=EditorDocumentVersionDiffResponse,
)
def get_editor_document_version_diff(
    site_id: int,
    document_id: int,
    version_id: int,
    compare_to_version_id: int | None = None,
    session: Session = Depends(get_db),
) -> EditorDocumentVersionDiffResponse:
    try:
        result = editor_document_version_service.get_document_version_diff(
            session,
            site_id,
            document_id,
            version_id,
            compare_to_version_id=compare_to_version_id,
        )
    except editor_document_version_service.EditorDocumentVersionServiceError as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorDocumentVersionDiffResponse.model_validate(result)


@router.post(
    "/{site_id}/ai-review-editor/documents/{document_id}/versions/{version_id}/restore",
    response_model=EditorDocumentVersionRestoreResponse,
)
def restore_editor_document_version(
    site_id: int,
    document_id: int,
    version_id: int,
    payload: EditorDocumentVersionRestoreRequest,
    session: Session = Depends(get_db),
) -> EditorDocumentVersionRestoreResponse:
    del payload
    try:
        result = editor_document_version_service.restore_document_version(
            session,
            site_id,
            document_id,
            version_id,
        )
    except editor_document_version_service.EditorDocumentVersionServiceError as exc:
        _raise_http_for_ai_review_editor_error(exc)
    session.commit()
    return EditorDocumentVersionRestoreResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents/{document_id}/review-runs",
    response_model=EditorReviewRunListResponse,
)
def list_editor_review_runs(
    site_id: int,
    document_id: int,
    session: Session = Depends(get_db),
) -> EditorReviewRunListResponse:
    try:
        result = editor_review_run_service.list_review_runs(session, site_id, document_id)
    except (ai_review_editor_service.AiReviewEditorServiceError, editor_review_run_service.EditorReviewRunServiceError) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorReviewRunListResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents/{document_id}/review-runs/{review_run_id}",
    response_model=EditorReviewRunResponse,
)
def get_editor_review_run(
    site_id: int,
    document_id: int,
    review_run_id: int,
    session: Session = Depends(get_db),
) -> EditorReviewRunResponse:
    try:
        result = editor_review_run_service.get_review_run(session, site_id, document_id, review_run_id)
    except (ai_review_editor_service.AiReviewEditorServiceError, editor_review_run_service.EditorReviewRunServiceError) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorReviewRunResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents/{document_id}/issues",
    response_model=EditorReviewIssueListResponse,
)
def list_editor_document_review_issues(
    site_id: int,
    document_id: int,
    session: Session = Depends(get_db),
) -> EditorReviewIssueListResponse:
    try:
        result = editor_review_run_service.list_document_issues(session, site_id, document_id)
    except (ai_review_editor_service.AiReviewEditorServiceError, editor_review_run_service.EditorReviewRunServiceError) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorReviewIssueListResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents/{document_id}/review-runs/{review_run_id}/issues",
    response_model=EditorReviewIssueListResponse,
)
def list_editor_review_run_issues(
    site_id: int,
    document_id: int,
    review_run_id: int,
    session: Session = Depends(get_db),
) -> EditorReviewIssueListResponse:
    try:
        result = editor_review_run_service.list_review_run_issues(
            session,
            site_id,
            document_id,
            review_run_id=review_run_id,
        )
    except (ai_review_editor_service.AiReviewEditorServiceError, editor_review_run_service.EditorReviewRunServiceError) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorReviewIssueListResponse.model_validate(result)


@router.post(
    "/{site_id}/ai-review-editor/documents/{document_id}/issues/{issue_id}/dismiss",
    response_model=EditorReviewIssueResponse,
)
def dismiss_editor_review_issue(
    site_id: int,
    document_id: int,
    issue_id: int,
    payload: EditorReviewIssueDismissRequest,
    session: Session = Depends(get_db),
) -> EditorReviewIssueResponse:
    try:
        result = editor_rewrite_service.dismiss_issue(
            session,
            site_id,
            document_id,
            issue_id,
            dismiss_reason=payload.dismiss_reason,
        )
    except (
        ai_review_editor_service.AiReviewEditorServiceError,
        editor_review_run_service.EditorReviewRunServiceError,
        editor_rewrite_service.EditorRewriteServiceError,
    ) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    session.commit()
    return EditorReviewIssueResponse.model_validate(result)


@router.post(
    "/{site_id}/ai-review-editor/documents/{document_id}/issues/{issue_id}/resolve-manual",
    response_model=EditorReviewIssueResponse,
)
def resolve_editor_review_issue_manually(
    site_id: int,
    document_id: int,
    issue_id: int,
    payload: EditorReviewIssueManualResolveRequest,
    session: Session = Depends(get_db),
) -> EditorReviewIssueResponse:
    try:
        result = editor_rewrite_service.resolve_issue_manually(
            session,
            site_id,
            document_id,
            issue_id,
            resolution_note=payload.resolution_note,
        )
    except (
        ai_review_editor_service.AiReviewEditorServiceError,
        editor_review_run_service.EditorReviewRunServiceError,
        editor_rewrite_service.EditorRewriteServiceError,
    ) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    session.commit()
    return EditorReviewIssueResponse.model_validate(result)


@router.post(
    "/{site_id}/ai-review-editor/documents/{document_id}/issues/{issue_id}/rewrite-runs",
    response_model=EditorRewriteRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_editor_issue_rewrite(
    site_id: int,
    document_id: int,
    issue_id: int,
    payload: EditorRewriteRunCreateRequest,
    session: Session = Depends(get_db),
) -> EditorRewriteRunResponse:
    del payload
    try:
        result = editor_rewrite_service.request_issue_rewrite(
            session,
            site_id,
            document_id,
            issue_id,
        )
    except (
        ai_review_editor_service.AiReviewEditorServiceError,
        editor_review_run_service.EditorReviewRunServiceError,
        editor_rewrite_service.EditorRewriteServiceError,
    ) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    session.commit()
    return EditorRewriteRunResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents/{document_id}/issues/{issue_id}/rewrite-runs",
    response_model=EditorRewriteRunListResponse,
)
def list_editor_issue_rewrite_runs(
    site_id: int,
    document_id: int,
    issue_id: int,
    session: Session = Depends(get_db),
) -> EditorRewriteRunListResponse:
    try:
        result = editor_rewrite_service.list_issue_rewrite_runs(
            session,
            site_id,
            document_id,
            issue_id,
        )
    except (
        ai_review_editor_service.AiReviewEditorServiceError,
        editor_review_run_service.EditorReviewRunServiceError,
        editor_rewrite_service.EditorRewriteServiceError,
    ) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorRewriteRunListResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents/{document_id}/rewrite-runs/{rewrite_run_id}",
    response_model=EditorRewriteRunResponse,
)
def get_editor_rewrite_run(
    site_id: int,
    document_id: int,
    rewrite_run_id: int,
    session: Session = Depends(get_db),
) -> EditorRewriteRunResponse:
    try:
        result = editor_rewrite_service.get_rewrite_run(
            session,
            site_id,
            document_id,
            rewrite_run_id,
        )
    except (
        ai_review_editor_service.AiReviewEditorServiceError,
        editor_review_run_service.EditorReviewRunServiceError,
        editor_rewrite_service.EditorRewriteServiceError,
    ) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorRewriteRunResponse.model_validate(result)


@router.post(
    "/{site_id}/ai-review-editor/documents/{document_id}/rewrite-runs/{rewrite_run_id}/apply",
    response_model=EditorRewriteApplyResponse,
)
def apply_editor_rewrite_run(
    site_id: int,
    document_id: int,
    rewrite_run_id: int,
    payload: EditorRewriteApplyRequest,
    session: Session = Depends(get_db),
) -> EditorRewriteApplyResponse:
    del payload
    try:
        result = editor_rewrite_service.apply_rewrite_run(
            session,
            site_id,
            document_id,
            rewrite_run_id,
        )
    except (
        ai_review_editor_service.AiReviewEditorServiceError,
        editor_review_run_service.EditorReviewRunServiceError,
        editor_rewrite_service.EditorRewriteServiceError,
    ) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    session.commit()
    return EditorRewriteApplyResponse.model_validate(result)


@router.get(
    "/{site_id}/ai-review-editor/documents/{document_id}/review-summary",
    response_model=EditorReviewSummaryResponse,
)
def get_editor_review_summary(
    site_id: int,
    document_id: int,
    session: Session = Depends(get_db),
) -> EditorReviewSummaryResponse:
    try:
        result = editor_review_run_service.get_review_summary(session, site_id, document_id)
    except (ai_review_editor_service.AiReviewEditorServiceError, editor_review_run_service.EditorReviewRunServiceError) as exc:
        _raise_http_for_ai_review_editor_error(exc)
    return EditorReviewSummaryResponse.model_validate(result)
