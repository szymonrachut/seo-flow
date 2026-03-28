from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


EditorReviewMode = Literal["light", "standard", "strict"]
EditorReviewEngineMode = Literal["auto", "mock", "llm"]
EditorDocumentVersionSource = Literal[
    "document_parse",
    "document_update",
    "manual_block_edit",
    "block_insert",
    "block_delete",
    "rewrite_apply",
    "rollback",
]
EditorDocumentBlockInsertPosition = Literal["before", "after", "end"]
EditorDocumentVersionBlockChangeType = Literal["added", "removed", "changed"]
EditorReviewIssueSeverity = Literal["low", "medium", "high"]
EditorReviewIssueStatus = Literal[
    "open",
    "dismissed",
    "rewrite_requested",
    "rewrite_ready",
    "applied",
    "resolved_manual",
]
EditorReviewRunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
EditorRewriteRunStatus = Literal["queued", "running", "completed", "failed", "cancelled", "applied"]
EditorReviewKnownIssueType = Literal[
    "weak_heading",
    "short_paragraph",
    "placeholder_text",
    "todo_marker",
    "generic_heading",
    "factuality",
    "off_topic",
    "unsupported_claim",
    "irrelevant_entity",
    "brand_mismatch",
    "product_hallucination",
    "unclear",
    "terminology_inconsistency",
]


class EditorDocumentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    document_type: str = Field(min_length=1, max_length=64)
    source_format: str = Field(min_length=1, max_length=32)
    source_content: str = Field(min_length=1)
    topic_brief_json: dict[str, Any] | None = None
    facts_context_json: dict[str, Any] | None = None


class EditorDocumentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    document_type: str | None = Field(default=None, min_length=1, max_length=64)
    source_format: str | None = Field(default=None, min_length=1, max_length=32)
    source_content: str | None = Field(default=None, min_length=1)
    topic_brief_json: dict[str, Any] | None = None
    facts_context_json: dict[str, Any] | None = None
    status: str | None = Field(default=None, min_length=1, max_length=32)


class EditorDocumentResponse(BaseModel):
    id: int
    site_id: int
    title: str
    document_type: str
    source_format: str
    source_content: str
    normalized_content: str | None = None
    topic_brief_json: dict[str, Any] | None = None
    facts_context_json: dict[str, Any] | None = None
    status: str
    active_block_count: int = 0
    created_at: datetime
    updated_at: datetime


class EditorDocumentListItemResponse(BaseModel):
    id: int
    site_id: int
    title: str
    document_type: str
    source_format: str
    status: str
    active_block_count: int = 0
    created_at: datetime
    updated_at: datetime


class EditorDocumentListResponse(BaseModel):
    site_id: int
    items: list[EditorDocumentListItemResponse] = Field(default_factory=list)


class EditorDocumentBlockResponse(BaseModel):
    id: int
    document_id: int
    block_key: str
    block_type: str
    block_level: int | None = None
    parent_block_key: str | None = None
    position_index: int
    text_content: str
    html_content: str | None = None
    context_path: str | None = None
    content_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EditorDocumentBlockListResponse(BaseModel):
    document_id: int
    items: list[EditorDocumentBlockResponse] = Field(default_factory=list)


class EditorDocumentBlockUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text_content: str = Field(min_length=1, max_length=12000)
    expected_content_hash: str | None = Field(default=None, min_length=1, max_length=64)


class EditorDocumentBlockInsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_block_key: str | None = Field(default=None, min_length=1, max_length=32)
    position: EditorDocumentBlockInsertPosition = "after"
    block_type: str = Field(min_length=1, max_length=32)
    block_level: int | None = Field(default=None, ge=1, le=6)
    text_content: str = Field(min_length=1, max_length=12000)


class EditorDocumentParseResponse(BaseModel):
    document: EditorDocumentResponse
    blocks_created_count: int
    replaced_block_count: int


class EditorDocumentVersionBlockSnapshotResponse(BaseModel):
    block_key: str
    block_type: str
    block_level: int | None = None
    parent_block_key: str | None = None
    position_index: int
    text_content: str
    html_content: str | None = None
    context_path: str | None = None
    content_hash: str


class EditorDocumentVersionSnapshotResponse(BaseModel):
    title: str
    document_type: str
    source_format: str
    source_content: str
    normalized_content: str | None = None
    topic_brief_json: dict[str, Any] | None = None
    facts_context_json: dict[str, Any] | None = None
    status: str
    blocks: list[EditorDocumentVersionBlockSnapshotResponse] = Field(default_factory=list)


class EditorDocumentVersionResponse(BaseModel):
    id: int
    document_id: int
    version_no: int
    source_of_change: EditorDocumentVersionSource
    source_description: str | None = None
    version_hash: str
    block_count: int = 0
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    is_current: bool = False
    snapshot: EditorDocumentVersionSnapshotResponse | None = None


class EditorDocumentVersionListResponse(BaseModel):
    document_id: int
    current_version_id: int | None = None
    items: list[EditorDocumentVersionResponse] = Field(default_factory=list)


class EditorDocumentVersionDocumentFieldDiffResponse(BaseModel):
    field: str
    before_value: Any | None = None
    after_value: Any | None = None


class EditorDocumentVersionBlockDiffResponse(BaseModel):
    block_key: str
    change_type: EditorDocumentVersionBlockChangeType
    block_type: str | None = None
    before_context_path: str | None = None
    after_context_path: str | None = None
    before_text: str | None = None
    after_text: str | None = None


class EditorDocumentVersionDiffSummaryResponse(BaseModel):
    added_blocks: int = 0
    removed_blocks: int = 0
    changed_blocks: int = 0
    changed_fields: int = 0


class EditorDocumentVersionDiffResponse(BaseModel):
    document_id: int
    base_version: EditorDocumentVersionResponse | None = None
    target_version: EditorDocumentVersionResponse
    summary: EditorDocumentVersionDiffSummaryResponse
    document_changes: list[EditorDocumentVersionDocumentFieldDiffResponse] = Field(default_factory=list)
    block_changes: list[EditorDocumentVersionBlockDiffResponse] = Field(default_factory=list)


class EditorDocumentVersionRestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EditorDocumentVersionRestoreResponse(BaseModel):
    document: EditorDocumentResponse
    restored_from_version: EditorDocumentVersionResponse
    current_version: EditorDocumentVersionResponse
    blocks_restored_count: int


class EditorDocumentBlockUpdateResponse(BaseModel):
    changed: bool = True
    document: EditorDocumentResponse
    updated_block: EditorDocumentBlockResponse
    current_version: EditorDocumentVersionResponse


class EditorDocumentBlockInsertResponse(BaseModel):
    document: EditorDocumentResponse
    inserted_block: EditorDocumentBlockResponse
    current_version: EditorDocumentVersionResponse


class EditorDocumentBlockDeleteResponse(BaseModel):
    document: EditorDocumentResponse
    deleted_block_key: str
    remaining_block_count: int
    current_version: EditorDocumentVersionResponse


class EditorReviewRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_mode: str = Field(default="standard", min_length=1, max_length=32)


class EditorReviewSeverityCountsResponse(BaseModel):
    low: int = 0
    medium: int = 0
    high: int = 0


class EditorReviewRunResponse(BaseModel):
    id: int
    document_id: int
    document_version_hash: str
    review_mode: str
    status: EditorReviewRunStatus
    model_name: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    input_hash: str | None = None
    issue_count: int = 0
    issue_block_count: int = 0
    severity_counts: EditorReviewSeverityCountsResponse = Field(default_factory=EditorReviewSeverityCountsResponse)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    matches_current_document: bool = False
    created_at: datetime
    updated_at: datetime


class EditorReviewIssueResponse(BaseModel):
    id: int
    review_run_id: int
    document_id: int
    block_key: str
    issue_type: str
    severity: EditorReviewIssueSeverity
    confidence: float | None = None
    message: str
    reason: str | None = None
    replacement_instruction: str | None = None
    replacement_candidate_text: str | None = None
    status: EditorReviewIssueStatus
    dismiss_reason: str | None = None
    resolution_note: str | None = None
    matches_current_block: bool = False
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class EditorReviewRunListResponse(BaseModel):
    document_id: int
    items: list[EditorReviewRunResponse] = Field(default_factory=list)


class EditorReviewIssueListResponse(BaseModel):
    document_id: int
    review_run_id: int | None = None
    review_run_status: EditorReviewRunStatus | None = None
    review_mode: str | None = None
    review_matches_current_document: bool | None = None
    items: list[EditorReviewIssueResponse] = Field(default_factory=list)


class EditorReviewSummaryResponse(BaseModel):
    document_id: int
    review_run_count: int = 0
    latest_review_run_id: int | None = None
    latest_review_run_status: EditorReviewRunStatus | None = None
    latest_review_run_finished_at: datetime | None = None
    latest_review_matches_current_document: bool | None = None
    issue_count: int = 0
    issue_block_count: int = 0
    severity_counts: EditorReviewSeverityCountsResponse = Field(default_factory=EditorReviewSeverityCountsResponse)


class EditorReviewIssueDismissRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dismiss_reason: str | None = Field(default=None, max_length=1000)


class EditorReviewIssueManualResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution_note: str | None = Field(default=None, max_length=1000)


class EditorRewriteRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EditorRewriteApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EditorRewriteRunResponse(BaseModel):
    id: int
    document_id: int
    review_issue_id: int | None = None
    block_key: str
    status: EditorRewriteRunStatus
    model_name: str | None = None
    prompt_version: str | None = None
    schema_version: str | None = None
    input_hash: str | None = None
    source_block_content_hash: str | None = None
    result_text: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    applied_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    matches_current_document: bool = False
    matches_current_block: bool = False
    is_stale: bool = False
    created_at: datetime
    updated_at: datetime


class EditorRewriteRunListResponse(BaseModel):
    document_id: int
    review_issue_id: int | None = None
    items: list[EditorRewriteRunResponse] = Field(default_factory=list)


class EditorRewriteApplyResponse(BaseModel):
    document: EditorDocumentResponse
    issue: EditorReviewIssueResponse
    rewrite_run: EditorRewriteRunResponse
    updated_block: EditorDocumentBlockResponse


class EditorReviewBlockInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_key: str = Field(min_length=1, max_length=32)
    block_type: str = Field(min_length=1, max_length=32)
    block_level: int | None = Field(default=None, ge=1, le=6)
    context_path: str | None = Field(default=None, max_length=2000)
    text_content: str = Field(min_length=1, max_length=12000)


class EditorReviewPromptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_version: str = Field(min_length=1, max_length=64)
    task: str = Field(min_length=1, max_length=64)
    review_mode: EditorReviewMode
    allowed_issue_types: list[EditorReviewKnownIssueType] = Field(default_factory=list, max_length=16)
    allowed_severities: list[EditorReviewIssueSeverity] = Field(default_factory=list, max_length=8)
    document: dict[str, Any]
    topic_brief_json: dict[str, Any] | None = None
    facts_context_json: dict[str, Any] | None = None
    blocks: list[EditorReviewBlockInput] = Field(default_factory=list, max_length=200)


class EditorReviewDocumentIssueOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_type: str | None = Field(default=None, max_length=64)
    severity: str | None = Field(default=None, max_length=32)
    message: str | None = Field(default=None, max_length=1000)
    reason: str | None = Field(default=None, max_length=2000)


class EditorReviewBlockIssueOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_key: str | None = Field(default=None, max_length=32)
    issue_type: str | None = Field(default=None, max_length=64)
    severity: str | None = Field(default=None, max_length=32)
    confidence: float | int | str | None = None
    message: str | None = Field(default=None, max_length=1000)
    reason: str | None = Field(default=None, max_length=2000)
    replacement_instruction: str | None = Field(default=None, max_length=2000)


class EditorReviewLlmOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_issues: list[EditorReviewDocumentIssueOutput] = Field(default_factory=list, max_length=32)
    block_issues: list[EditorReviewBlockIssueOutput] = Field(default_factory=list, max_length=200)


class EditorRewriteNeighborBlockInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: Literal["previous", "next"]
    block_key: str = Field(min_length=1, max_length=32)
    block_type: str = Field(min_length=1, max_length=32)
    block_level: int | None = Field(default=None, ge=1, le=6)
    text_content: str = Field(min_length=1, max_length=2000)


class EditorRewritePromptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_version: str = Field(min_length=1, max_length=64)
    task: str = Field(min_length=1, max_length=64)
    document: dict[str, Any]
    issue: dict[str, Any]
    block: EditorReviewBlockInput
    neighbor_blocks: list[EditorRewriteNeighborBlockInput] = Field(default_factory=list, max_length=2)
    topic_brief_json: dict[str, Any] | None = None
    facts_context_json: dict[str, Any] | None = None


class EditorRewriteLlmOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_key: str | None = Field(default=None, max_length=32)
    rewritten_text: str | None = Field(default=None, max_length=12000)
