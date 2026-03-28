from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.text_processing import collapse_whitespace
from app.db.models import EditorDocument, EditorDocumentBlock, EditorDocumentVersion, Site, utcnow
from app.services.editor_block_parser_service import build_editor_block_content_hash, build_editor_block_html


SUPPORTED_EDITOR_DOCUMENT_SOURCE_FORMATS = {"html"}
EDITOR_DOCUMENT_VERSION_SOURCES = {
    "document_parse",
    "document_update",
    "manual_block_edit",
    "block_insert",
    "block_delete",
    "rewrite_apply",
    "rollback",
}


class EditorDocumentVersionServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "editor_document_version_error") -> None:
        super().__init__(message)
        self.code = code


def ensure_supported_source_format(source_format: str | None) -> str:
    normalized_source_format = collapse_whitespace(source_format or "").lower()
    if normalized_source_format not in SUPPORTED_EDITOR_DOCUMENT_SOURCE_FORMATS:
        raise EditorDocumentVersionServiceError(
            f"Unsupported editor document source format {source_format!r}. Only 'html' is supported.",
            code="unsupported_source_format",
        )
    return normalized_source_format


def load_active_blocks(session: Session, document_id: int) -> list[EditorDocumentBlock]:
    return session.scalars(
        select(EditorDocumentBlock)
        .where(
            EditorDocumentBlock.document_id == document_id,
            EditorDocumentBlock.is_active.is_(True),
        )
        .order_by(EditorDocumentBlock.position_index.asc(), EditorDocumentBlock.id.asc())
    ).all()


def deactivate_active_blocks(session: Session, document_id: int) -> None:
    session.execute(
        update(EditorDocumentBlock)
        .where(
            EditorDocumentBlock.document_id == document_id,
            EditorDocumentBlock.is_active.is_(True),
        )
        .values(is_active=False)
    )


def refresh_active_block_contexts(session: Session, document_id: int) -> None:
    active_blocks = load_active_blocks(session, document_id)
    heading_stack: list[dict[str, Any]] = []
    now = utcnow()

    for block in active_blocks:
        if block.block_type == "heading":
            block_level = int(block.block_level or 1)
            while heading_stack and int(heading_stack[-1]["level"]) >= block_level:
                heading_stack.pop()
            parent_block_key = str(heading_stack[-1]["block_key"]) if heading_stack else None
            context_titles = [str(item["text"]) for item in heading_stack] + [block.text_content]
            context_path = " > ".join(title for title in context_titles if title) or None
            heading_stack.append(
                {
                    "block_key": block.block_key,
                    "level": block_level,
                    "text": block.text_content,
                }
            )
        else:
            parent_block_key = str(heading_stack[-1]["block_key"]) if heading_stack else None
            context_titles = [str(item["text"]) for item in heading_stack]
            context_path = " > ".join(title for title in context_titles if title) or None

        content_hash = build_editor_block_content_hash(
            block_type=block.block_type,
            block_level=block.block_level,
            text_content=block.text_content,
            context_path=context_path,
        )
        if (
            block.parent_block_key != parent_block_key
            or block.context_path != context_path
            or block.content_hash != content_hash
        ):
            block.parent_block_key = parent_block_key
            block.context_path = context_path
            block.content_hash = content_hash
            block.updated_at = now


def sync_document_representations_from_blocks(
    document: EditorDocument,
    active_blocks: list[EditorDocumentBlock],
    *,
    set_status: bool = True,
) -> None:
    document.source_content = render_blocks_to_source_content(active_blocks)
    document.normalized_content = build_normalized_content_from_blocks(active_blocks)
    if set_status:
        document.status = "parsed"
    document.updated_at = utcnow()


def build_current_document_version_hash(
    document: EditorDocument,
    *,
    active_blocks: list[EditorDocumentBlock] | None = None,
) -> str:
    snapshot = build_document_snapshot(
        document,
        active_blocks=active_blocks,
    )
    return _build_snapshot_hash(snapshot)


def capture_document_version(
    session: Session,
    document: EditorDocument,
    *,
    source_of_change: str,
    metadata_json: dict[str, Any] | None = None,
    active_blocks: list[EditorDocumentBlock] | None = None,
    allow_duplicate_hash: bool = False,
) -> EditorDocumentVersion | None:
    normalized_source = _normalize_source_of_change(source_of_change)
    blocks = list(active_blocks) if active_blocks is not None else load_active_blocks(session, document.id)
    snapshot = build_document_snapshot(document, active_blocks=blocks)
    version_hash = _build_snapshot_hash(snapshot)
    latest_version = get_latest_document_version(session, document.id)
    if (
        latest_version is not None
        and latest_version.version_hash == version_hash
        and not allow_duplicate_hash
    ):
        return latest_version

    next_version_no = int(latest_version.version_no + 1) if latest_version is not None else 1
    version = EditorDocumentVersion(
        document_id=document.id,
        version_no=next_version_no,
        source_of_change=normalized_source,
        version_hash=version_hash,
        snapshot_json=snapshot,
        metadata_json=metadata_json or None,
        created_at=utcnow(),
    )
    session.add(version)
    session.flush()
    return version


def list_document_versions(session: Session, site_id: int, document_id: int) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)
    versions = _load_versions(session, document.id)
    current_version_id = int(versions[0].id) if versions else None
    return {
        "document_id": document.id,
        "current_version_id": current_version_id,
        "items": [
            _serialize_version(
                version,
                current_version_id=current_version_id,
                include_snapshot=False,
            )
            for version in versions
        ],
    }


def get_document_version(session: Session, site_id: int, document_id: int, version_id: int) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)
    version = _get_version_or_raise(session, document.id, version_id)
    versions = _load_versions(session, document.id)
    current_version_id = int(versions[0].id) if versions else None
    return _serialize_version(version, current_version_id=current_version_id, include_snapshot=True)


def get_document_version_diff(
    session: Session,
    site_id: int,
    document_id: int,
    version_id: int,
    *,
    compare_to_version_id: int | None = None,
) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)
    target_version = _get_version_or_raise(session, document.id, version_id)
    latest_version = get_latest_document_version(session, document.id)

    if compare_to_version_id is not None:
        base_version = _get_version_or_raise(session, document.id, compare_to_version_id)
    elif latest_version is None:
        base_version = None
    elif latest_version.id == target_version.id:
        base_version = get_previous_document_version(session, document.id, target_version.version_no)
    else:
        base_version = latest_version

    diff_payload = _build_diff(
        base_snapshot=base_version.snapshot_json if base_version is not None else None,
        target_snapshot=target_version.snapshot_json,
    )
    current_version_id = int(latest_version.id) if latest_version is not None else None
    return {
        "document_id": document.id,
        "base_version": (
            _serialize_version(base_version, current_version_id=current_version_id, include_snapshot=False)
            if base_version is not None
            else None
        ),
        "target_version": _serialize_version(
            target_version,
            current_version_id=current_version_id,
            include_snapshot=False,
        ),
        "summary": diff_payload["summary"],
        "document_changes": diff_payload["document_changes"],
        "block_changes": diff_payload["block_changes"],
    }


def restore_document_version(
    session: Session,
    site_id: int,
    document_id: int,
    version_id: int,
) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)
    target_version = _get_version_or_raise(session, document.id, version_id)
    target_snapshot = dict(target_version.snapshot_json or {})
    target_hash = str(target_version.version_hash or "")
    current_hash = build_current_document_version_hash(document)
    if target_hash and target_hash == current_hash:
        raise EditorDocumentVersionServiceError(
            f"Document {document.id} is already at version {target_version.version_no}.",
            code="already_current_version",
        )

    blocks_snapshot = list(target_snapshot.get("blocks") or [])
    document_snapshot = dict(target_snapshot.get("document") or {})
    if not blocks_snapshot:
        raise EditorDocumentVersionServiceError(
            f"Version {version_id} does not contain a restorable block snapshot.",
            code="version_snapshot_invalid",
        )

    now = utcnow()
    deactivate_active_blocks(session, document.id)
    for block_payload in blocks_snapshot:
        session.add(
            EditorDocumentBlock(
                document_id=document.id,
                block_key=str(block_payload.get("block_key") or ""),
                block_type=str(block_payload.get("block_type") or ""),
                block_level=_coerce_optional_int(block_payload.get("block_level")),
                parent_block_key=_coerce_optional_str(block_payload.get("parent_block_key")),
                position_index=int(block_payload.get("position_index") or 0),
                text_content=str(block_payload.get("text_content") or ""),
                html_content=_coerce_optional_str(block_payload.get("html_content")),
                context_path=_coerce_optional_str(block_payload.get("context_path")),
                content_hash=str(block_payload.get("content_hash") or ""),
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
    session.flush()

    document.title = str(document_snapshot.get("title") or document.title)
    document.document_type = str(document_snapshot.get("document_type") or document.document_type)
    document.source_format = ensure_supported_source_format(str(document_snapshot.get("source_format") or document.source_format))
    document.topic_brief_json = _coerce_optional_dict(document_snapshot.get("topic_brief_json"))
    document.facts_context_json = _coerce_optional_dict(document_snapshot.get("facts_context_json"))

    active_blocks = load_active_blocks(session, document.id)
    sync_document_representations_from_blocks(document, active_blocks)
    session.flush()

    current_version = capture_document_version(
        session,
        document,
        source_of_change="rollback",
        metadata_json={
            "restored_from_version_id": target_version.id,
            "restored_from_version_no": target_version.version_no,
            "blocks_restored_count": len(active_blocks),
        },
        active_blocks=active_blocks,
        allow_duplicate_hash=True,
    )
    session.flush()
    if current_version is None:  # pragma: no cover - defensive fallback
        raise EditorDocumentVersionServiceError(
            "Rollback failed to create a new current document version.",
            code="version_capture_failed",
        )

    current_version_id = int(current_version.id)
    return {
        "document": _serialize_document(document, active_blocks),
        "restored_from_version": _serialize_version(
            target_version,
            current_version_id=current_version_id,
            include_snapshot=False,
        ),
        "current_version": _serialize_version(
            current_version,
            current_version_id=current_version_id,
            include_snapshot=False,
        ),
        "blocks_restored_count": len(active_blocks),
    }


def build_document_snapshot(
    document: EditorDocument,
    *,
    active_blocks: list[EditorDocumentBlock] | None = None,
) -> dict[str, Any]:
    blocks = (
        list(active_blocks)
        if active_blocks is not None
        else [block for block in list(getattr(document, "blocks", []) or []) if bool(block.is_active)]
    )
    rendered_source_content = render_blocks_to_source_content(blocks)
    normalized_content = build_normalized_content_from_blocks(blocks)
    return {
        "document": {
            "title": document.title,
            "document_type": document.document_type,
            "source_format": ensure_supported_source_format(document.source_format),
            "source_content": rendered_source_content,
            "normalized_content": normalized_content,
            "topic_brief_json": _clone_json_value(document.topic_brief_json),
            "facts_context_json": _clone_json_value(document.facts_context_json),
            "status": "parsed" if blocks else document.status,
        },
        "blocks": [_serialize_block_snapshot(block) for block in blocks],
    }


def render_blocks_to_source_content(blocks: list[EditorDocumentBlock]) -> str:
    if not blocks:
        return ""

    fragments: list[str] = []
    list_item_fragments: list[str] = []

    def flush_list_items() -> None:
        if not list_item_fragments:
            return
        fragments.append(f"<ul>{''.join(list_item_fragments)}</ul>")
        list_item_fragments.clear()

    for block in blocks:
        rendered_html = _resolve_block_html(block)
        if block.block_type == "list_item":
            list_item_fragments.append(rendered_html)
            continue
        flush_list_items()
        fragments.append(rendered_html)

    flush_list_items()
    return "\n".join(fragment for fragment in fragments if fragment)


def build_normalized_content_from_blocks(blocks: list[EditorDocumentBlock]) -> str | None:
    normalized_texts = [collapse_whitespace(block.text_content) for block in blocks if collapse_whitespace(block.text_content)]
    return "\n\n".join(normalized_texts) or None


def get_latest_document_version(session: Session, document_id: int) -> EditorDocumentVersion | None:
    return session.scalar(
        select(EditorDocumentVersion)
        .where(EditorDocumentVersion.document_id == document_id)
        .order_by(EditorDocumentVersion.version_no.desc(), EditorDocumentVersion.id.desc())
        .limit(1)
    )


def get_previous_document_version(session: Session, document_id: int, version_no: int) -> EditorDocumentVersion | None:
    return session.scalar(
        select(EditorDocumentVersion)
        .where(
            EditorDocumentVersion.document_id == document_id,
            EditorDocumentVersion.version_no < version_no,
        )
        .order_by(EditorDocumentVersion.version_no.desc(), EditorDocumentVersion.id.desc())
        .limit(1)
    )


def _get_site_or_raise(session: Session, site_id: int) -> Site:
    site = session.get(Site, site_id)
    if site is None:
        raise EditorDocumentVersionServiceError(f"Site {site_id} not found.", code="not_found")
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
        raise EditorDocumentVersionServiceError(
            f"Editor document {document_id} for site {site_id} not found.",
            code="not_found",
        )
    return document


def _get_version_or_raise(session: Session, document_id: int, version_id: int) -> EditorDocumentVersion:
    version = session.scalar(
        select(EditorDocumentVersion)
        .where(
            EditorDocumentVersion.id == version_id,
            EditorDocumentVersion.document_id == document_id,
        )
        .limit(1)
    )
    if version is None:
        raise EditorDocumentVersionServiceError(
            f"Editor document version {version_id} for document {document_id} not found.",
            code="not_found",
        )
    return version


def _load_versions(session: Session, document_id: int) -> list[EditorDocumentVersion]:
    return session.scalars(
        select(EditorDocumentVersion)
        .where(EditorDocumentVersion.document_id == document_id)
        .order_by(EditorDocumentVersion.version_no.desc(), EditorDocumentVersion.id.desc())
    ).all()


def _build_snapshot_hash(snapshot: dict[str, Any]) -> str:
    serialized = json.dumps(snapshot, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_source_of_change(source_of_change: str) -> str:
    normalized_source = collapse_whitespace(source_of_change).lower().replace(" ", "_")
    if normalized_source not in EDITOR_DOCUMENT_VERSION_SOURCES:
        raise EditorDocumentVersionServiceError(
            f"Unsupported editor document version source {source_of_change!r}.",
            code="invalid_version_source",
        )
    return normalized_source


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


def _serialize_version(
    version: EditorDocumentVersion,
    *,
    current_version_id: int | None,
    include_snapshot: bool,
) -> dict[str, Any]:
    snapshot = dict(version.snapshot_json or {})
    blocks = list(snapshot.get("blocks") or [])
    payload = {
        "id": version.id,
        "document_id": version.document_id,
        "version_no": version.version_no,
        "source_of_change": version.source_of_change,
        "source_description": _build_source_description(version),
        "version_hash": version.version_hash,
        "block_count": len(blocks),
        "metadata_json": version.metadata_json,
        "created_at": version.created_at,
        "is_current": version.id == current_version_id,
    }
    if include_snapshot:
        payload["snapshot"] = {
            "title": str(snapshot.get("document", {}).get("title") or ""),
            "document_type": str(snapshot.get("document", {}).get("document_type") or ""),
            "source_format": str(snapshot.get("document", {}).get("source_format") or ""),
            "source_content": str(snapshot.get("document", {}).get("source_content") or ""),
            "normalized_content": _coerce_optional_str(snapshot.get("document", {}).get("normalized_content")),
            "topic_brief_json": _coerce_optional_dict(snapshot.get("document", {}).get("topic_brief_json")),
            "facts_context_json": _coerce_optional_dict(snapshot.get("document", {}).get("facts_context_json")),
            "status": str(snapshot.get("document", {}).get("status") or "parsed"),
            "blocks": blocks,
        }
    return payload


def _build_source_description(version: EditorDocumentVersion) -> str | None:
    metadata = dict(version.metadata_json or {})
    if version.source_of_change == "rewrite_apply":
        block_key = _coerce_optional_str(metadata.get("block_key"))
        return f"Applied AI rewrite{f' to {block_key}' if block_key else ''}."
    if version.source_of_change == "manual_block_edit":
        block_key = _coerce_optional_str(metadata.get("block_key"))
        return f"Edited block{f' {block_key}' if block_key else ''} manually."
    if version.source_of_change == "block_insert":
        block_key = _coerce_optional_str(metadata.get("block_key"))
        anchor_block_key = _coerce_optional_str(metadata.get("anchor_block_key"))
        position = _coerce_optional_str(metadata.get("position"))
        if block_key and anchor_block_key and position in {"before", "after"}:
            return f"Inserted block {block_key} {position} {anchor_block_key}."
        if block_key:
            return f"Inserted block {block_key}."
        return "Inserted a new block."
    if version.source_of_change == "block_delete":
        block_key = _coerce_optional_str(metadata.get("block_key"))
        return f"Deleted block{f' {block_key}' if block_key else ''}."
    if version.source_of_change == "rollback":
        restored_from_version_no = metadata.get("restored_from_version_no")
        if restored_from_version_no is not None:
            return f"Restored version {restored_from_version_no}."
        return "Restored an earlier version."
    if version.source_of_change == "document_parse":
        return "Created a parsed document snapshot."
    if version.source_of_change == "document_update":
        changed_fields = list(metadata.get("changed_fields") or [])
        if changed_fields:
            humanized = ", ".join(str(field) for field in changed_fields[:3])
            return f"Updated {humanized}."
        return "Updated the document content."
    return None


def _serialize_block_snapshot(block: EditorDocumentBlock) -> dict[str, Any]:
    return {
        "block_key": block.block_key,
        "block_type": block.block_type,
        "block_level": block.block_level,
        "parent_block_key": block.parent_block_key,
        "position_index": block.position_index,
        "text_content": collapse_whitespace(block.text_content),
        "html_content": _resolve_block_html(block),
        "context_path": _coerce_optional_str(block.context_path),
        "content_hash": block.content_hash,
    }


def _resolve_block_html(block: EditorDocumentBlock) -> str:
    if block.html_content:
        return block.html_content
    return build_editor_block_html(
        block_type=block.block_type,
        block_level=block.block_level,
        text_content=block.text_content,
    )


def _build_diff(
    *,
    base_snapshot: dict[str, Any] | None,
    target_snapshot: dict[str, Any],
) -> dict[str, Any]:
    base_document = dict((base_snapshot or {}).get("document") or {})
    target_document = dict(target_snapshot.get("document") or {})
    base_blocks = list((base_snapshot or {}).get("blocks") or [])
    target_blocks = list(target_snapshot.get("blocks") or [])
    base_blocks_by_key = {str(block.get("block_key") or ""): block for block in base_blocks}
    target_blocks_by_key = {str(block.get("block_key") or ""): block for block in target_blocks}
    block_order = sorted(
        set(base_blocks_by_key) | set(target_blocks_by_key),
        key=lambda block_key: (
            _coerce_sort_position(target_blocks_by_key.get(block_key))
            if block_key in target_blocks_by_key
            else _coerce_sort_position(base_blocks_by_key.get(block_key)),
            block_key,
        ),
    )

    block_changes: list[dict[str, Any]] = []
    for block_key in block_order:
        before_block = base_blocks_by_key.get(block_key)
        after_block = target_blocks_by_key.get(block_key)
        if before_block is None and after_block is not None:
            block_changes.append(
                {
                    "block_key": block_key,
                    "change_type": "added",
                    "block_type": _coerce_optional_str(after_block.get("block_type")),
                    "before_context_path": None,
                    "after_context_path": _coerce_optional_str(after_block.get("context_path")),
                    "before_text": None,
                    "after_text": _coerce_optional_str(after_block.get("text_content")),
                }
            )
            continue
        if before_block is not None and after_block is None:
            block_changes.append(
                {
                    "block_key": block_key,
                    "change_type": "removed",
                    "block_type": _coerce_optional_str(before_block.get("block_type")),
                    "before_context_path": _coerce_optional_str(before_block.get("context_path")),
                    "after_context_path": None,
                    "before_text": _coerce_optional_str(before_block.get("text_content")),
                    "after_text": None,
                }
            )
            continue
        if before_block is None or after_block is None:
            continue

        if _blocks_equal(before_block, after_block):
            continue
        block_changes.append(
            {
                "block_key": block_key,
                "change_type": "changed",
                "block_type": _coerce_optional_str(after_block.get("block_type"))
                or _coerce_optional_str(before_block.get("block_type")),
                "before_context_path": _coerce_optional_str(before_block.get("context_path")),
                "after_context_path": _coerce_optional_str(after_block.get("context_path")),
                "before_text": _coerce_optional_str(before_block.get("text_content")),
                "after_text": _coerce_optional_str(after_block.get("text_content")),
            }
        )

    document_changes = _build_document_changes(base_document, target_document)
    summary = {
        "added_blocks": sum(1 for change in block_changes if change["change_type"] == "added"),
        "removed_blocks": sum(1 for change in block_changes if change["change_type"] == "removed"),
        "changed_blocks": sum(1 for change in block_changes if change["change_type"] == "changed"),
        "changed_fields": len(document_changes),
    }
    return {
        "summary": summary,
        "document_changes": document_changes,
        "block_changes": block_changes,
    }


def _build_document_changes(base_document: dict[str, Any], target_document: dict[str, Any]) -> list[dict[str, Any]]:
    tracked_fields = [
        "title",
        "document_type",
        "source_format",
        "status",
        "topic_brief_json",
        "facts_context_json",
    ]
    changes: list[dict[str, Any]] = []
    for field_name in tracked_fields:
        before_value = base_document.get(field_name)
        after_value = target_document.get(field_name)
        if _json_fingerprint(before_value) == _json_fingerprint(after_value):
            continue
        changes.append(
            {
                "field": field_name,
                "before_value": before_value,
                "after_value": after_value,
            }
        )
    return changes


def _blocks_equal(before_block: dict[str, Any], after_block: dict[str, Any]) -> bool:
    tracked_fields = [
        "block_type",
        "block_level",
        "parent_block_key",
        "position_index",
        "text_content",
        "context_path",
        "content_hash",
    ]
    return all(
        _json_fingerprint(before_block.get(field_name)) == _json_fingerprint(after_block.get(field_name))
        for field_name in tracked_fields
    )


def _json_fingerprint(value: Any) -> str:
    serialized = json.dumps(_clone_json_value(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _clone_json_value(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _coerce_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized_value = collapse_whitespace(str(value))
    return normalized_value or None


def _coerce_optional_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    return None


def _coerce_sort_position(block_payload: dict[str, Any] | None) -> int:
    if not block_payload:
        return 10**9  # pragma: no cover - defensive fallback for incomplete payloads
    position = block_payload.get("position_index")
    return int(position) if position is not None else 0
