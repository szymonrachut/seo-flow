from __future__ import annotations

from sqlalchemy import select

from app.db.models import EditorDocument, EditorDocumentBlock, EditorDocumentVersion, Site
import app.services.ai_review_editor_service as ai_review_editor_service
import app.services.editor_document_block_service as editor_document_block_service
import app.services.editor_document_version_service as editor_document_version_service


def _seed_parsed_document(session_factory) -> dict[str, int]:
    with session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com")
        session.add(site)
        session.flush()

        document = ai_review_editor_service.create_document(
            session,
            int(site.id),
            title="Inline edit draft",
            document_type="article",
            source_format="html",
            source_content="""
                <h1>Pricing guide</h1>
                <p>TODO add verified pricing details.</p>
                <p>All subscriptions renew monthly.</p>
            """,
            topic_brief_json={"topic": "pricing"},
            facts_context_json={"brand": "Example"},
        )
        document_id = int(document["id"])
        ai_review_editor_service.parse_document_into_blocks(session, int(site.id), document_id)
        session.commit()

    return {
        "site_id": int(site.id),
        "document_id": document_id,
    }


def test_manual_block_update_replaces_only_target_block_and_creates_version(sqlite_session_factory) -> None:
    ids = _seed_parsed_document(sqlite_session_factory)

    with sqlite_session_factory() as session:
        before_blocks = editor_document_version_service.load_active_blocks(session, ids["document_id"])
        target_block = next(block for block in before_blocks if block.block_key == "P-002")
        payload = editor_document_block_service.update_document_block(
            session,
            ids["site_id"],
            ids["document_id"],
            "P-002",
            text_content="Verified pricing details are summarized below.",
            expected_content_hash=target_block.content_hash,
        )
        previous_version_id = int(editor_document_version_service.list_document_versions(session, ids["site_id"], ids["document_id"])["items"][-1]["id"])
        current_version_id = int(payload["current_version"]["id"])
        diff_payload = editor_document_version_service.get_document_version_diff(
            session,
            ids["site_id"],
            ids["document_id"],
            current_version_id,
            compare_to_version_id=previous_version_id,
        )
        session.commit()

    with sqlite_session_factory() as session:
        document = session.get(EditorDocument, ids["document_id"])
        active_blocks = session.scalars(
            select(EditorDocumentBlock)
            .where(
                EditorDocumentBlock.document_id == ids["document_id"],
                EditorDocumentBlock.is_active.is_(True),
            )
            .order_by(EditorDocumentBlock.position_index.asc(), EditorDocumentBlock.id.asc())
        ).all()
        versions = session.scalars(
            select(EditorDocumentVersion)
            .where(EditorDocumentVersion.document_id == ids["document_id"])
            .order_by(EditorDocumentVersion.version_no.asc())
        ).all()

    assert payload["changed"] is True
    assert payload["updated_block"]["block_key"] == "P-002"
    assert payload["updated_block"]["text_content"] == "Verified pricing details are summarized below."
    assert payload["current_version"]["source_of_change"] == "manual_block_edit"
    assert payload["current_version"]["version_no"] == 2
    assert diff_payload["summary"] == {
        "added_blocks": 0,
        "removed_blocks": 0,
        "changed_blocks": 1,
        "changed_fields": 0,
    }
    assert diff_payload["block_changes"] == [
        {
            "block_key": "P-002",
            "change_type": "changed",
            "block_type": "paragraph",
            "before_context_path": "Pricing guide",
            "after_context_path": "Pricing guide",
            "before_text": "TODO add verified pricing details.",
            "after_text": "Verified pricing details are summarized below.",
        }
    ]

    assert document is not None
    assert document.source_content == (
        "<h1>Pricing guide</h1>\n"
        "<p>Verified pricing details are summarized below.</p>\n"
        "<p>All subscriptions renew monthly.</p>"
    )
    assert document.normalized_content == (
        "Pricing guide\n\nVerified pricing details are summarized below.\n\nAll subscriptions renew monthly."
    )
    assert [block.block_key for block in active_blocks] == ["H1-001", "P-002", "P-003"]
    assert [block.text_content for block in active_blocks] == [
        "Pricing guide",
        "Verified pricing details are summarized below.",
        "All subscriptions renew monthly.",
    ]
    assert [version.source_of_change for version in versions] == ["document_parse", "manual_block_edit"]


def test_manual_block_update_noop_does_not_create_extra_version(sqlite_session_factory) -> None:
    ids = _seed_parsed_document(sqlite_session_factory)

    with sqlite_session_factory() as session:
        versions_before = editor_document_version_service.list_document_versions(session, ids["site_id"], ids["document_id"])
        target_block = next(
            block for block in editor_document_version_service.load_active_blocks(session, ids["document_id"]) if block.block_key == "P-002"
        )
        payload = editor_document_block_service.update_document_block(
            session,
            ids["site_id"],
            ids["document_id"],
            "P-002",
            text_content="TODO add verified pricing details.",
            expected_content_hash=target_block.content_hash,
        )
        versions_after = editor_document_version_service.list_document_versions(session, ids["site_id"], ids["document_id"])
        session.commit()

    assert payload["changed"] is False
    assert payload["updated_block"]["id"] == target_block.id
    assert versions_before["current_version_id"] == versions_after["current_version_id"]
    assert len(versions_before["items"]) == len(versions_after["items"]) == 1


def test_manual_block_update_rejects_invalid_text_and_hash_conflict(sqlite_session_factory) -> None:
    ids = _seed_parsed_document(sqlite_session_factory)

    with sqlite_session_factory() as session:
        target_block = next(
            block for block in editor_document_version_service.load_active_blocks(session, ids["document_id"]) if block.block_key == "P-002"
        )
        try:
            editor_document_block_service.update_document_block(
                session,
                ids["site_id"],
                ids["document_id"],
                "P-002",
                text_content="   ",
            )
        except editor_document_block_service.EditorDocumentBlockServiceError as exc:
            invalid_text_exc = exc
        else:  # pragma: no cover - defensive fallback
            raise AssertionError("Expected invalid block text error.")

        try:
            editor_document_block_service.update_document_block(
                session,
                ids["site_id"],
                ids["document_id"],
                "P-002",
                text_content="Updated text",
                expected_content_hash=f"{target_block.content_hash}-stale",
            )
        except editor_document_block_service.EditorDocumentBlockServiceError as exc:
            conflict_exc = exc
        else:  # pragma: no cover - defensive fallback
            raise AssertionError("Expected block conflict error.")

    assert invalid_text_exc.code == "invalid_block_text"
    assert conflict_exc.code == "block_conflict"


def test_manual_block_update_rejects_block_outside_document(sqlite_session_factory) -> None:
    ids = _seed_parsed_document(sqlite_session_factory)

    with sqlite_session_factory() as session:
        try:
            editor_document_block_service.update_document_block(
                session,
                ids["site_id"],
                ids["document_id"] + 999,
                "P-002",
                text_content="Updated text",
            )
        except editor_document_block_service.EditorDocumentBlockServiceError as exc:
            wrong_document_exc = exc
        else:  # pragma: no cover - defensive fallback
            raise AssertionError("Expected not found error for wrong document.")

        try:
            editor_document_block_service.update_document_block(
                session,
                ids["site_id"],
                ids["document_id"],
                "P-999",
                text_content="Updated text",
            )
        except editor_document_block_service.EditorDocumentBlockServiceError as exc:
            missing_block_exc = exc
        else:  # pragma: no cover - defensive fallback
            raise AssertionError("Expected active block not found error.")

    assert wrong_document_exc.code == "not_found"
    assert missing_block_exc.code == "active_block_not_found"


def test_manual_block_update_rollback_restores_previous_snapshot(sqlite_session_factory) -> None:
    ids = _seed_parsed_document(sqlite_session_factory)

    with sqlite_session_factory() as session:
        target_block = next(
            block for block in editor_document_version_service.load_active_blocks(session, ids["document_id"]) if block.block_key == "P-002"
        )
        editor_document_block_service.update_document_block(
            session,
            ids["site_id"],
            ids["document_id"],
            "P-002",
            text_content="Verified pricing details are summarized below.",
            expected_content_hash=target_block.content_hash,
        )
        versions_after_edit = editor_document_version_service.list_document_versions(session, ids["site_id"], ids["document_id"])
        rollback_payload = editor_document_version_service.restore_document_version(
            session,
            ids["site_id"],
            ids["document_id"],
            int(versions_after_edit["items"][-1]["id"]),
        )
        session.commit()

    with sqlite_session_factory() as session:
        active_blocks = editor_document_version_service.load_active_blocks(session, ids["document_id"])

    assert rollback_payload["current_version"]["source_of_change"] == "rollback"
    assert rollback_payload["current_version"]["version_no"] == 3
    assert rollback_payload["restored_from_version"]["version_no"] == 1
    assert [block.text_content for block in active_blocks] == [
        "Pricing guide",
        "TODO add verified pricing details.",
        "All subscriptions renew monthly.",
    ]


def test_insert_document_block_before_target_keeps_existing_block_keys_and_creates_version(sqlite_session_factory) -> None:
    ids = _seed_parsed_document(sqlite_session_factory)

    with sqlite_session_factory() as session:
        payload = editor_document_block_service.insert_document_block(
            session,
            ids["site_id"],
            ids["document_id"],
            target_block_key="P-003",
            position="before",
            block_type="paragraph",
            text_content="Key pricing variables include seats and usage volume.",
        )
        previous_version_id = int(
            editor_document_version_service.list_document_versions(session, ids["site_id"], ids["document_id"])["items"][-1]["id"]
        )
        current_version_id = int(payload["current_version"]["id"])
        diff_payload = editor_document_version_service.get_document_version_diff(
            session,
            ids["site_id"],
            ids["document_id"],
            current_version_id,
            compare_to_version_id=previous_version_id,
        )
        session.commit()

    with sqlite_session_factory() as session:
        document = session.get(EditorDocument, ids["document_id"])
        active_blocks = editor_document_version_service.load_active_blocks(session, ids["document_id"])

    assert payload["inserted_block"]["block_key"] == "P-004"
    assert payload["inserted_block"]["position_index"] == 3
    assert payload["inserted_block"]["text_content"] == "Key pricing variables include seats and usage volume."
    assert payload["current_version"]["source_of_change"] == "block_insert"
    assert payload["current_version"]["version_no"] == 2
    assert [block.block_key for block in active_blocks] == ["H1-001", "P-002", "P-004", "P-003"]
    assert [block.text_content for block in active_blocks] == [
        "Pricing guide",
        "TODO add verified pricing details.",
        "Key pricing variables include seats and usage volume.",
        "All subscriptions renew monthly.",
    ]
    assert diff_payload["summary"]["added_blocks"] == 1
    assert diff_payload["summary"]["removed_blocks"] == 0
    assert diff_payload["summary"]["changed_blocks"] == 1
    assert [change["block_key"] for change in diff_payload["block_changes"]] == ["P-004", "P-003"]
    assert document is not None
    assert document.source_content == (
        "<h1>Pricing guide</h1>\n"
        "<p>TODO add verified pricing details.</p>\n"
        "<p>Key pricing variables include seats and usage volume.</p>\n"
        "<p>All subscriptions renew monthly.</p>"
    )


def test_insert_document_block_after_target_recomputes_context_and_supports_rollback(sqlite_session_factory) -> None:
    ids = _seed_parsed_document(sqlite_session_factory)

    with sqlite_session_factory() as session:
        payload = editor_document_block_service.insert_document_block(
            session,
            ids["site_id"],
            ids["document_id"],
            target_block_key="P-002",
            position="after",
            block_type="heading",
            block_level=2,
            text_content="Plan details",
        )
        first_version_id = int(
            editor_document_version_service.list_document_versions(session, ids["site_id"], ids["document_id"])["items"][-1]["id"]
        )
        current_version_id = int(payload["current_version"]["id"])
        diff_payload = editor_document_version_service.get_document_version_diff(
            session,
            ids["site_id"],
            ids["document_id"],
            current_version_id,
            compare_to_version_id=first_version_id,
        )
        rollback_payload = editor_document_version_service.restore_document_version(
            session,
            ids["site_id"],
            ids["document_id"],
            first_version_id,
        )
        session.commit()

    with sqlite_session_factory() as session:
        active_blocks = editor_document_version_service.load_active_blocks(session, ids["document_id"])

    inserted_block = payload["inserted_block"]
    assert inserted_block["block_key"] == "H2-004"
    assert inserted_block["position_index"] == 3
    assert inserted_block["context_path"] == "Pricing guide > Plan details"
    assert diff_payload["summary"] == {
        "added_blocks": 1,
        "removed_blocks": 0,
        "changed_blocks": 1,
        "changed_fields": 0,
    }
    assert [change["block_key"] for change in diff_payload["block_changes"]] == ["H2-004", "P-003"]
    assert diff_payload["block_changes"][1]["before_context_path"] == "Pricing guide"
    assert diff_payload["block_changes"][1]["after_context_path"] == "Pricing guide > Plan details"
    assert rollback_payload["current_version"]["source_of_change"] == "rollback"
    assert rollback_payload["restored_from_version"]["version_no"] == 1
    assert [block.block_key for block in active_blocks] == ["H1-001", "P-002", "P-003"]
    assert [block.context_path for block in active_blocks] == ["Pricing guide", "Pricing guide", "Pricing guide"]


def test_delete_document_block_deactivates_target_and_creates_version(sqlite_session_factory) -> None:
    ids = _seed_parsed_document(sqlite_session_factory)

    with sqlite_session_factory() as session:
        payload = editor_document_block_service.delete_document_block(
            session,
            ids["site_id"],
            ids["document_id"],
            "P-002",
        )
        first_version_id = int(
            editor_document_version_service.list_document_versions(session, ids["site_id"], ids["document_id"])["items"][-1]["id"]
        )
        current_version_id = int(payload["current_version"]["id"])
        diff_payload = editor_document_version_service.get_document_version_diff(
            session,
            ids["site_id"],
            ids["document_id"],
            current_version_id,
            compare_to_version_id=first_version_id,
        )
        rollback_payload = editor_document_version_service.restore_document_version(
            session,
            ids["site_id"],
            ids["document_id"],
            first_version_id,
        )
        session.commit()

    with sqlite_session_factory() as session:
        active_blocks = editor_document_version_service.load_active_blocks(session, ids["document_id"])
        all_blocks = session.scalars(
            select(EditorDocumentBlock)
            .where(EditorDocumentBlock.document_id == ids["document_id"])
            .order_by(EditorDocumentBlock.id.asc())
        ).all()

    assert payload["deleted_block_key"] == "P-002"
    assert payload["remaining_block_count"] == 2
    assert payload["current_version"]["source_of_change"] == "block_delete"
    assert diff_payload["summary"] == {
        "added_blocks": 0,
        "removed_blocks": 1,
        "changed_blocks": 1,
        "changed_fields": 0,
    }
    assert [change["block_key"] for change in diff_payload["block_changes"]] == ["P-002", "P-003"]
    assert rollback_payload["current_version"]["source_of_change"] == "rollback"
    assert [block.block_key for block in active_blocks] == ["H1-001", "P-002", "P-003"]
    assert [block.is_active for block in all_blocks][-3:] == [True, True, True]


def test_insert_delete_block_guards_reject_invalid_payloads_and_last_block_delete(sqlite_session_factory) -> None:
    ids = _seed_parsed_document(sqlite_session_factory)

    with sqlite_session_factory() as session:
        try:
            editor_document_block_service.insert_document_block(
                session,
                ids["site_id"],
                ids["document_id"],
                target_block_key=None,
                position="before",
                block_type="paragraph",
                text_content="Inserted without anchor.",
            )
        except editor_document_block_service.EditorDocumentBlockServiceError as exc:
            missing_anchor_exc = exc
        else:  # pragma: no cover - defensive fallback
            raise AssertionError("Expected invalid insert anchor error.")

        try:
            editor_document_block_service.insert_document_block(
                session,
                ids["site_id"],
                ids["document_id"],
                target_block_key="P-002",
                position="after",
                block_type="paragraph",
                block_level=2,
                text_content="Paragraph blocks cannot carry heading level.",
            )
        except editor_document_block_service.EditorDocumentBlockServiceError as exc:
            invalid_level_exc = exc
        else:  # pragma: no cover - defensive fallback
            raise AssertionError("Expected invalid block level error.")

    with sqlite_session_factory() as session:
        site = Site(root_url="https://single.example.com", domain="single.example.com")
        session.add(site)
        session.flush()

        document = ai_review_editor_service.create_document(
            session,
            int(site.id),
            title="Single block doc",
            document_type="article",
            source_format="html",
            source_content="<h1>Only block</h1>",
            topic_brief_json=None,
            facts_context_json=None,
        )
        document_id = int(document["id"])
        ai_review_editor_service.parse_document_into_blocks(session, int(site.id), document_id)

        try:
            editor_document_block_service.delete_document_block(
                session,
                int(site.id),
                document_id,
                "H1-001",
            )
        except editor_document_block_service.EditorDocumentBlockServiceError as exc:
            last_block_exc = exc
        else:  # pragma: no cover - defensive fallback
            raise AssertionError("Expected last block delete guard.")

    assert missing_anchor_exc.code == "invalid_insert_anchor"
    assert invalid_level_exc.code == "invalid_block_level"
    assert last_block_exc.code == "last_block_delete_forbidden"
