from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.text_processing import collapse_whitespace
from app.db.models import EditorDocument, EditorDocumentBlock, Site, utcnow
from app.services.editor_block_parser_service import build_editor_block_content_hash, build_editor_block_html
import app.services.editor_document_version_service as editor_document_version_service


SUPPORTED_EDITOR_BLOCK_TYPES = {"heading", "paragraph", "list_item"}
SUPPORTED_BLOCK_INSERT_POSITIONS = {"before", "after", "end"}
_BLOCK_KEY_ORDINAL_RE = re.compile(r"-(\d+)$")
_INSERT_TEMP_POSITION_BASE = 1_000_000
_REINDEX_TEMP_POSITION_BASE = 2_000_000


class EditorDocumentBlockServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "editor_document_block_error") -> None:
        super().__init__(message)
        self.code = code


def update_document_block(
    session: Session,
    site_id: int,
    document_id: int,
    block_key: str,
    *,
    text_content: str,
    expected_content_hash: str | None = None,
) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)
    active_blocks = editor_document_version_service.load_active_blocks(session, document.id)
    target_block = _get_active_block_or_raise(active_blocks, block_key)
    normalized_text = _normalize_block_text_or_raise(text_content)

    if expected_content_hash and collapse_whitespace(expected_content_hash) != target_block.content_hash:
        raise EditorDocumentBlockServiceError(
            "The block changed after the editor loaded it. Refresh the document and try again.",
            code="block_conflict",
        )

    current_version = _get_current_version_payload(session, site_id, document.id)
    if normalized_text == collapse_whitespace(target_block.text_content):
        return {
            "changed": False,
            "document": _serialize_document(document, active_blocks),
            "updated_block": _serialize_block(target_block),
            "current_version": current_version,
        }

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
        text_content=normalized_text,
        html_content=_build_block_html(
            block_type=target_block.block_type,
            block_level=target_block.block_level,
            text_content=normalized_text,
        ),
        context_path=target_block.context_path,
        content_hash=build_editor_block_content_hash(
            block_type=target_block.block_type,
            block_level=target_block.block_level,
            text_content=normalized_text,
            context_path=target_block.context_path,
        ),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(updated_block)
    session.flush()

    active_blocks, current_version = _finalize_active_block_state(
        session,
        document,
        active_blocks=None,
        source_of_change="manual_block_edit",
        metadata_json={
            "block_key": updated_block.block_key,
            "previous_content_hash": target_block.content_hash,
            "updated_content_hash": updated_block.content_hash,
        },
        site_id=site_id,
    )
    session.refresh(updated_block)

    return {
        "changed": True,
        "document": _serialize_document(document, active_blocks),
        "updated_block": _serialize_block(updated_block),
        "current_version": current_version,
    }


def insert_document_block(
    session: Session,
    site_id: int,
    document_id: int,
    *,
    target_block_key: str | None,
    position: str,
    block_type: str,
    text_content: str,
    block_level: int | None = None,
) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)
    active_blocks = editor_document_version_service.load_active_blocks(session, document.id)
    normalized_position = _normalize_insert_position(position)
    normalized_block_type, normalized_block_level = _normalize_block_definition(block_type, block_level)
    normalized_text = _normalize_block_text_or_raise(text_content)

    insertion_index = len(active_blocks)
    anchor_block: EditorDocumentBlock | None = None
    if normalized_position == "end":
        if target_block_key is not None:
            raise EditorDocumentBlockServiceError(
                "target_block_key must be omitted when inserting at the end of the document.",
                code="invalid_insert_anchor",
            )
    else:
        if not collapse_whitespace(target_block_key or ""):
            raise EditorDocumentBlockServiceError(
                "target_block_key is required for before/after insert operations.",
                code="invalid_insert_anchor",
            )
        anchor_block = _get_active_block_or_raise(active_blocks, target_block_key or "")
        anchor_index = next(
            index
            for index, block in enumerate(active_blocks)
            if block.block_key == anchor_block.block_key
        )
        insertion_index = anchor_index if normalized_position == "before" else anchor_index + 1

    now = utcnow()
    inserted_block = EditorDocumentBlock(
        document_id=document.id,
        block_key=_generate_next_block_key(
            session,
            document.id,
            block_type=normalized_block_type,
            block_level=normalized_block_level,
        ),
        block_type=normalized_block_type,
        block_level=normalized_block_level,
        parent_block_key=None,
        position_index=_INSERT_TEMP_POSITION_BASE + len(active_blocks) + 1,
        text_content=normalized_text,
        html_content=_build_block_html(
            block_type=normalized_block_type,
            block_level=normalized_block_level,
            text_content=normalized_text,
        ),
        context_path=None,
        content_hash=build_editor_block_content_hash(
            block_type=normalized_block_type,
            block_level=normalized_block_level,
            text_content=normalized_text,
            context_path=None,
        ),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(inserted_block)
    active_blocks.insert(insertion_index, inserted_block)
    session.flush()

    active_blocks, current_version = _finalize_active_block_state(
        session,
        document,
        active_blocks=active_blocks,
        source_of_change="block_insert",
        metadata_json={
            "block_key": inserted_block.block_key,
            "position": normalized_position,
            "anchor_block_key": anchor_block.block_key if anchor_block is not None else None,
            "block_type": normalized_block_type,
            "block_level": normalized_block_level,
        },
        site_id=site_id,
    )
    session.refresh(inserted_block)

    return {
        "document": _serialize_document(document, active_blocks),
        "inserted_block": _serialize_block(inserted_block),
        "current_version": current_version,
    }


def delete_document_block(
    session: Session,
    site_id: int,
    document_id: int,
    block_key: str,
) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)
    active_blocks = editor_document_version_service.load_active_blocks(session, document.id)
    target_block = _get_active_block_or_raise(active_blocks, block_key)

    if len(active_blocks) <= 1:
        raise EditorDocumentBlockServiceError(
            "The last active block cannot be deleted. Keep at least one block in the document.",
            code="last_block_delete_forbidden",
        )

    target_block.is_active = False
    target_block.updated_at = utcnow()
    remaining_blocks = [block for block in active_blocks if block.block_key != target_block.block_key]

    active_blocks, current_version = _finalize_active_block_state(
        session,
        document,
        active_blocks=remaining_blocks,
        source_of_change="block_delete",
        metadata_json={
            "block_key": target_block.block_key,
            "block_type": target_block.block_type,
            "block_level": target_block.block_level,
            "position_index": target_block.position_index,
        },
        site_id=site_id,
    )

    return {
        "document": _serialize_document(document, active_blocks),
        "deleted_block_key": target_block.block_key,
        "remaining_block_count": len(active_blocks),
        "current_version": current_version,
    }


def _finalize_active_block_state(
    session: Session,
    document: EditorDocument,
    *,
    active_blocks: list[EditorDocumentBlock] | None,
    source_of_change: str,
    metadata_json: dict[str, Any] | None,
    site_id: int,
) -> tuple[list[EditorDocumentBlock], dict[str, Any]]:
    target_blocks = list(active_blocks) if active_blocks is not None else editor_document_version_service.load_active_blocks(session, document.id)
    _reindex_active_blocks(session, target_blocks)
    editor_document_version_service.refresh_active_block_contexts(session, document.id)
    session.flush()

    refreshed_active_blocks = editor_document_version_service.load_active_blocks(session, document.id)
    editor_document_version_service.sync_document_representations_from_blocks(document, refreshed_active_blocks)
    editor_document_version_service.capture_document_version(
        session,
        document,
        source_of_change=source_of_change,
        metadata_json=metadata_json,
        active_blocks=refreshed_active_blocks,
    )
    session.flush()
    current_version = _get_current_version_payload(session, site_id, document.id)
    return refreshed_active_blocks, current_version


def _reindex_active_blocks(session: Session, active_blocks: list[EditorDocumentBlock]) -> None:
    provisional_now = utcnow()
    for index, block in enumerate(active_blocks, start=1):
        provisional_position = _REINDEX_TEMP_POSITION_BASE + index
        if block.position_index != provisional_position:
            block.position_index = provisional_position
            block.updated_at = provisional_now
    session.flush()

    final_now = utcnow()
    for index, block in enumerate(active_blocks, start=1):
        if block.position_index != index:
            block.position_index = index
            block.updated_at = final_now
    session.flush()


def _generate_next_block_key(
    session: Session,
    document_id: int,
    *,
    block_type: str,
    block_level: int | None,
) -> str:
    existing_block_keys = {
        str(block_key)
        for block_key in session.scalars(
            select(EditorDocumentBlock.block_key).where(EditorDocumentBlock.document_id == document_id)
        ).all()
    }
    next_ordinal = 1
    for block_key in existing_block_keys:
        match = _BLOCK_KEY_ORDINAL_RE.search(block_key)
        if match:
            next_ordinal = max(next_ordinal, int(match.group(1)) + 1)

    block_prefix = _build_block_prefix(block_type=block_type, block_level=block_level)
    candidate_block_key = f"{block_prefix}-{next_ordinal:03d}"
    while candidate_block_key in existing_block_keys:
        next_ordinal += 1
        candidate_block_key = f"{block_prefix}-{next_ordinal:03d}"
    return candidate_block_key


def _build_block_prefix(*, block_type: str, block_level: int | None) -> str:
    if block_type == "heading":
        return f"H{int(block_level or 2)}"
    if block_type == "paragraph":
        return "P"
    return "LI"


def _get_site_or_raise(session: Session, site_id: int) -> Site:
    site = session.get(Site, site_id)
    if site is None:
        raise EditorDocumentBlockServiceError(f"Site {site_id} not found.", code="not_found")
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
        raise EditorDocumentBlockServiceError(
            f"Editor document {document_id} for site {site_id} not found.",
            code="not_found",
        )
    return document


def _get_active_block_or_raise(active_blocks: list[EditorDocumentBlock], block_key: str) -> EditorDocumentBlock:
    normalized_block_key = collapse_whitespace(block_key)
    for block in active_blocks:
        if block.block_key == normalized_block_key:
            return block
    raise EditorDocumentBlockServiceError(
        f"Active block {normalized_block_key} was not found in the current document state.",
        code="active_block_not_found",
    )


def _normalize_block_text_or_raise(text_content: str) -> str:
    normalized_text = collapse_whitespace(text_content)
    if not normalized_text:
        raise EditorDocumentBlockServiceError(
            "Edited block text cannot be empty.",
            code="invalid_block_text",
        )
    return normalized_text


def _normalize_insert_position(position: str) -> str:
    normalized_position = collapse_whitespace(position).lower()
    if normalized_position not in SUPPORTED_BLOCK_INSERT_POSITIONS:
        raise EditorDocumentBlockServiceError(
            f"Unsupported block insert position {position!r}.",
            code="invalid_insert_position",
        )
    return normalized_position


def _normalize_block_definition(block_type: str, block_level: int | None) -> tuple[str, int | None]:
    normalized_block_type = collapse_whitespace(block_type).lower()
    if normalized_block_type not in SUPPORTED_EDITOR_BLOCK_TYPES:
        raise EditorDocumentBlockServiceError(
            f"Unsupported editor block type {block_type!r}.",
            code="unsupported_block_type",
        )

    if normalized_block_type == "heading":
        normalized_block_level = int(block_level or 2)
        if normalized_block_level < 1 or normalized_block_level > 6:
            raise EditorDocumentBlockServiceError(
                "Heading level must be between 1 and 6.",
                code="invalid_block_level",
            )
        return normalized_block_type, normalized_block_level

    if block_level is not None:
        raise EditorDocumentBlockServiceError(
            "Only heading blocks can define block_level.",
            code="invalid_block_level",
        )
    return normalized_block_type, None


def _build_block_html(*, block_type: str, block_level: int | None, text_content: str) -> str:
    try:
        return build_editor_block_html(
            block_type=block_type,
            block_level=block_level,
            text_content=text_content,
        )
    except ValueError as exc:  # pragma: no cover - defensive fallback
        raise EditorDocumentBlockServiceError(str(exc), code="unsupported_block_type") from exc


def _get_current_version_payload(session: Session, site_id: int, document_id: int) -> dict[str, Any]:
    versions_payload = editor_document_version_service.list_document_versions(session, site_id, document_id)
    if not versions_payload["items"]:
        raise EditorDocumentBlockServiceError(
            "The document has no captured versions yet.",
            code="version_not_found",
        )
    return dict(versions_payload["items"][0])


def _serialize_document(document: EditorDocument, active_blocks: list[EditorDocumentBlock]) -> dict[str, Any]:
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
        "active_block_count": len(active_blocks),
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
