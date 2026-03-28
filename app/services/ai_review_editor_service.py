from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import EditorDocument, EditorDocumentBlock, Site
from app.services import editor_block_parser_service
import app.services.editor_document_version_service as editor_document_version_service


class AiReviewEditorServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "ai_review_editor_error") -> None:
        super().__init__(message)
        self.code = code


def create_document(
    session: Session,
    site_id: int,
    *,
    title: str,
    document_type: str,
    source_format: str,
    source_content: str,
    topic_brief_json: dict[str, Any] | None,
    facts_context_json: dict[str, Any] | None,
) -> dict[str, Any]:
    _get_site_or_raise(session, site_id)
    try:
        normalized_source_format = editor_document_version_service.ensure_supported_source_format(source_format)
    except editor_document_version_service.EditorDocumentVersionServiceError as exc:
        raise AiReviewEditorServiceError(str(exc), code=exc.code) from exc
    document = EditorDocument(
        site_id=site_id,
        title=title.strip(),
        document_type=document_type.strip(),
        source_format=normalized_source_format,
        source_content=source_content,
        normalized_content=None,
        topic_brief_json=topic_brief_json,
        facts_context_json=facts_context_json,
        status="draft",
    )
    session.add(document)
    session.flush()
    return _serialize_document(session, document)


def list_documents(session: Session, site_id: int) -> dict[str, Any]:
    _get_site_or_raise(session, site_id)
    documents = session.scalars(
        select(EditorDocument)
        .where(EditorDocument.site_id == site_id)
        .order_by(EditorDocument.updated_at.desc(), EditorDocument.id.desc())
    ).all()
    block_counts = _get_active_block_counts(session, [document.id for document in documents])
    return {
        "site_id": site_id,
        "items": [_serialize_document_list_item(document, block_counts) for document in documents],
    }


def get_document(session: Session, site_id: int, document_id: int) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)
    return _serialize_document(session, document)


def update_document(
    session: Session,
    site_id: int,
    document_id: int,
    *,
    title: str | None = None,
    document_type: str | None = None,
    source_format: str | None = None,
    source_content: str | None = None,
    topic_brief_json: dict[str, Any] | None = None,
    facts_context_json: dict[str, Any] | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)

    if all(
        value is None
        for value in [title, document_type, source_format, source_content, topic_brief_json, facts_context_json, status]
    ):
        raise AiReviewEditorServiceError("At least one document field must be provided for update.", code="invalid_request")

    changed_fields: list[str] = []
    content_changed = False
    if title is not None:
        normalized_title = title.strip()
        if normalized_title != document.title:
            changed_fields.append("title")
            document.title = normalized_title
    if document_type is not None:
        normalized_document_type = document_type.strip()
        if normalized_document_type != document.document_type:
            changed_fields.append("document_type")
            document.document_type = normalized_document_type
    if source_format is not None:
        try:
            normalized_source_format = editor_document_version_service.ensure_supported_source_format(source_format)
        except editor_document_version_service.EditorDocumentVersionServiceError as exc:
            raise AiReviewEditorServiceError(str(exc), code=exc.code) from exc
        if normalized_source_format != document.source_format:
            content_changed = True
            changed_fields.append("source_format")
        document.source_format = normalized_source_format
    if source_content is not None:
        if source_content != document.source_content:
            content_changed = True
            changed_fields.append("source_content")
        document.source_content = source_content
    if topic_brief_json is not None:
        if topic_brief_json != document.topic_brief_json:
            changed_fields.append("topic_brief_json")
            document.topic_brief_json = topic_brief_json
    if facts_context_json is not None:
        if facts_context_json != document.facts_context_json:
            changed_fields.append("facts_context_json")
            document.facts_context_json = facts_context_json
    if status is not None:
        normalized_status = status.strip().lower()
        if normalized_status != document.status:
            changed_fields.append("status")
            document.status = normalized_status

    if content_changed:
        parsed_blocks = editor_block_parser_service.parse_html_document_into_blocks(document.source_content)
        replaced_block_count, active_blocks = _replace_active_blocks_with_parsed_blocks(session, document, parsed_blocks)
        editor_document_version_service.capture_document_version(
            session,
            document,
            source_of_change="document_update",
            metadata_json={
                "changed_fields": changed_fields,
                "blocks_created_count": len(active_blocks),
                "replaced_block_count": replaced_block_count,
            },
            active_blocks=active_blocks,
        )
    elif changed_fields and _count_active_blocks(session, document.id) > 0:
        active_blocks = editor_document_version_service.load_active_blocks(session, document.id)
        editor_document_version_service.sync_document_representations_from_blocks(
            document,
            active_blocks,
            set_status=False,
        )
        editor_document_version_service.capture_document_version(
            session,
            document,
            source_of_change="document_update",
            metadata_json={"changed_fields": changed_fields},
            active_blocks=active_blocks,
        )

    session.flush()
    return _serialize_document(session, document)


def parse_document_into_blocks(session: Session, site_id: int, document_id: int) -> dict[str, Any]:
    document = _get_document_or_raise(session, site_id, document_id)
    try:
        editor_document_version_service.ensure_supported_source_format(document.source_format)
    except editor_document_version_service.EditorDocumentVersionServiceError as exc:
        raise AiReviewEditorServiceError(str(exc), code=exc.code) from exc

    parsed_blocks = editor_block_parser_service.parse_html_document_into_blocks(document.source_content)
    replaced_block_count, active_blocks = _replace_active_blocks_with_parsed_blocks(session, document, parsed_blocks)
    editor_document_version_service.capture_document_version(
        session,
        document,
        source_of_change="document_parse",
        metadata_json={
            "blocks_created_count": len(active_blocks),
            "replaced_block_count": replaced_block_count,
        },
        active_blocks=active_blocks,
    )
    session.flush()

    return {
        "document": _serialize_document(session, document),
        "blocks_created_count": len(active_blocks),
        "replaced_block_count": replaced_block_count,
    }


def list_document_blocks(session: Session, site_id: int, document_id: int) -> dict[str, Any]:
    _get_document_or_raise(session, site_id, document_id)
    blocks = session.scalars(
        select(EditorDocumentBlock)
        .where(
            EditorDocumentBlock.document_id == document_id,
            EditorDocumentBlock.is_active.is_(True),
        )
        .order_by(EditorDocumentBlock.position_index.asc(), EditorDocumentBlock.id.asc())
    ).all()
    return {
        "document_id": document_id,
        "items": [_serialize_block(block) for block in blocks],
    }


def _get_site_or_raise(session: Session, site_id: int) -> Site:
    site = session.get(Site, site_id)
    if site is None:
        raise AiReviewEditorServiceError(f"Site {site_id} not found.", code="not_found")
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
        raise AiReviewEditorServiceError(
            f"Editor document {document_id} for site {site_id} not found.",
            code="not_found",
        )
    return document


def _deactivate_active_blocks(session: Session, document_id: int) -> None:
    editor_document_version_service.deactivate_active_blocks(session, document_id)


def _count_active_blocks(session: Session, document_id: int) -> int:
    count = session.scalar(
        select(func.count(EditorDocumentBlock.id)).where(
            EditorDocumentBlock.document_id == document_id,
            EditorDocumentBlock.is_active.is_(True),
        )
    )
    return int(count or 0)


def _replace_active_blocks_with_parsed_blocks(
    session: Session,
    document: EditorDocument,
    parsed_blocks: list[editor_block_parser_service.ParsedEditorBlock],
) -> tuple[int, list[EditorDocumentBlock]]:
    replaced_block_count = _count_active_blocks(session, document.id)
    _deactivate_active_blocks(session, document.id)

    for block in parsed_blocks:
        session.add(
            EditorDocumentBlock(
                document_id=document.id,
                block_key=block.block_key,
                block_type=block.block_type,
                block_level=block.block_level,
                parent_block_key=block.parent_block_key,
                position_index=block.position_index,
                text_content=block.text_content,
                html_content=block.html_content,
                context_path=block.context_path,
                content_hash=block.content_hash,
                is_active=True,
            )
        )

    session.flush()
    active_blocks = editor_document_version_service.load_active_blocks(session, document.id)
    editor_document_version_service.sync_document_representations_from_blocks(document, active_blocks)
    return replaced_block_count, active_blocks


def _get_active_block_counts(session: Session, document_ids: list[int]) -> dict[int, int]:
    if not document_ids:
        return {}
    rows = session.execute(
        select(
            EditorDocumentBlock.document_id,
            func.count(EditorDocumentBlock.id),
        )
        .where(
            EditorDocumentBlock.document_id.in_(document_ids),
            EditorDocumentBlock.is_active.is_(True),
        )
        .group_by(EditorDocumentBlock.document_id)
    ).all()
    return {int(document_id): int(count or 0) for document_id, count in rows}


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


def _serialize_document_list_item(document: EditorDocument, block_counts: dict[int, int]) -> dict[str, Any]:
    return {
        "id": document.id,
        "site_id": document.site_id,
        "title": document.title,
        "document_type": document.document_type,
        "source_format": document.source_format,
        "status": document.status,
        "active_block_count": int(block_counts.get(document.id, 0)),
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
