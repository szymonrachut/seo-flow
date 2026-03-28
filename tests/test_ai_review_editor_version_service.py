from __future__ import annotations

import json

from sqlalchemy import select

from app.db.models import EditorDocument, EditorDocumentBlock, EditorDocumentVersion, Site
import app.services.ai_review_editor_service as ai_review_editor_service
import app.services.editor_document_version_service as editor_document_version_service
import app.services.editor_rewrite_service as editor_rewrite_service
import app.services.editor_review_run_service as editor_review_run_service


class _RecordingRewriteClient:
    provider_name = "openai-test"

    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = list(payloads)
        self.user_payloads: list[dict] = []

    def is_available(self) -> bool:
        return True

    def parse_chat_completion(
        self,
        *,
        user_prompt: str,
        response_format,
        **_: object,
    ):
        self.user_payloads.append(json.loads(user_prompt))
        if not self._payloads:
            raise AssertionError("No fake rewrite payload configured.")
        return response_format.model_validate(self._payloads.pop(0))


def _seed_site(session_factory) -> int:
    with session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com")
        session.add(site)
        session.commit()
        return int(site.id)


def test_parse_apply_and_rollback_create_versions_and_restore_snapshot(sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)
    with sqlite_session_factory() as session:
        document = ai_review_editor_service.create_document(
            session,
            site_id,
            title="Versioned document",
            document_type="article",
            source_format="html",
            source_content="""
                <h1>Pricing guide</h1>
                <p>TODO: Replace this placeholder paragraph.</p>
                <p>Verified support paragraph.</p>
            """,
            topic_brief_json={"topic": "pricing"},
            facts_context_json={"brand": "Example"},
        )
        document_id = int(document["id"])
        parse_payload = ai_review_editor_service.parse_document_into_blocks(session, site_id, document_id)
        review_run = editor_review_run_service.create_review_run(
            session,
            site_id,
            document_id,
            review_mode="standard",
            engine_mode="mock",
        )
        issue_id = next(
            issue["id"]
            for issue in editor_review_run_service.list_document_issues(session, site_id, document_id)["items"]
            if issue["block_key"] == "P-002"
        )
        rewrite_run = editor_rewrite_service.request_issue_rewrite(
            session,
            site_id,
            document_id,
            issue_id,
            client=_RecordingRewriteClient(
                [
                    {
                        "block_key": "P-002",
                        "rewritten_text": "This paragraph now contains verified pricing guidance only.",
                    }
                ]
            ),
        )
        apply_payload = editor_rewrite_service.apply_rewrite_run(session, site_id, document_id, int(rewrite_run["id"]))
        versions_after_apply = editor_document_version_service.list_document_versions(session, site_id, document_id)
        rollback_payload = editor_document_version_service.restore_document_version(
            session,
            site_id,
            document_id,
            int(versions_after_apply["items"][-1]["id"]),
        )
        session.commit()

    assert parse_payload["blocks_created_count"] == 3
    assert review_run["status"] == "completed"
    assert apply_payload["rewrite_run"]["status"] == "applied"
    assert versions_after_apply["current_version_id"] == versions_after_apply["items"][0]["id"]
    assert [item["version_no"] for item in versions_after_apply["items"]] == [2, 1]
    assert versions_after_apply["items"][0]["source_of_change"] == "rewrite_apply"
    assert versions_after_apply["items"][1]["source_of_change"] == "document_parse"
    assert rollback_payload["current_version"]["version_no"] == 3
    assert rollback_payload["current_version"]["source_of_change"] == "rollback"
    assert rollback_payload["restored_from_version"]["version_no"] == 1
    assert rollback_payload["blocks_restored_count"] == 3

    with sqlite_session_factory() as session:
        document = session.get(EditorDocument, document_id)
        active_blocks = session.scalars(
            select(EditorDocumentBlock)
            .where(
                EditorDocumentBlock.document_id == document_id,
                EditorDocumentBlock.is_active.is_(True),
            )
            .order_by(EditorDocumentBlock.position_index.asc(), EditorDocumentBlock.id.asc())
        ).all()
        versions = session.scalars(
            select(EditorDocumentVersion)
            .where(EditorDocumentVersion.document_id == document_id)
            .order_by(EditorDocumentVersion.version_no.asc())
        ).all()

    assert document is not None
    assert [block.text_content for block in active_blocks] == [
        "Pricing guide",
        "TODO: Replace this placeholder paragraph.",
        "Verified support paragraph.",
    ]
    assert document.source_content == (
        "<h1>Pricing guide</h1>\n"
        "<p>TODO: Replace this placeholder paragraph.</p>\n"
        "<p>Verified support paragraph.</p>"
    )
    assert document.normalized_content == (
        "Pricing guide\n\nTODO: Replace this placeholder paragraph.\n\nVerified support paragraph."
    )
    assert [version.version_no for version in versions] == [1, 2, 3]


def test_update_document_auto_reparses_and_diff_reports_changed_added_and_removed_blocks(sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        created = ai_review_editor_service.create_document(
            session,
            site_id,
            title="Diffable document",
            document_type="article",
            source_format="html",
            source_content="""
                <h1>Original heading</h1>
                <p>Original paragraph.</p>
            """,
            topic_brief_json={"topic": "original"},
            facts_context_json={"brand": "Example"},
        )
        document_id = int(created["id"])
        ai_review_editor_service.parse_document_into_blocks(session, site_id, document_id)
        first_versions = editor_document_version_service.list_document_versions(session, site_id, document_id)
        update_payload = ai_review_editor_service.update_document(
            session,
            site_id,
            document_id,
            title="Updated heading brief",
            topic_brief_json={"topic": "updated"},
            source_content="""
                <h1>Updated heading</h1>
                <p>Original paragraph with refined detail.</p>
                <p>New support paragraph.</p>
            """,
        )
        second_versions = editor_document_version_service.list_document_versions(session, site_id, document_id)
        forward_diff = editor_document_version_service.get_document_version_diff(
            session,
            site_id,
            document_id,
            int(second_versions["items"][0]["id"]),
            compare_to_version_id=int(first_versions["items"][0]["id"]),
        )
        rollback_preview_diff = editor_document_version_service.get_document_version_diff(
            session,
            site_id,
            document_id,
            int(first_versions["items"][0]["id"]),
            compare_to_version_id=int(second_versions["items"][0]["id"]),
        )
        session.commit()

    assert update_payload["status"] == "parsed"
    assert update_payload["active_block_count"] == 3
    assert second_versions["items"][0]["version_no"] == 2
    assert second_versions["items"][0]["source_of_change"] == "document_update"
    assert forward_diff["summary"] == {
        "added_blocks": 1,
        "removed_blocks": 0,
        "changed_blocks": 2,
        "changed_fields": 2,
    }
    assert [change["field"] for change in forward_diff["document_changes"]] == ["title", "topic_brief_json"]
    assert [change["block_key"] for change in forward_diff["block_changes"]] == ["H1-001", "P-002", "P-003"]
    assert [change["change_type"] for change in forward_diff["block_changes"]] == ["changed", "changed", "added"]
    assert rollback_preview_diff["summary"]["removed_blocks"] == 1
    assert rollback_preview_diff["block_changes"][-1]["block_key"] == "P-003"
    assert rollback_preview_diff["block_changes"][-1]["change_type"] == "removed"

    with sqlite_session_factory() as session:
        document = session.get(EditorDocument, document_id)
        active_blocks = session.scalars(
            select(EditorDocumentBlock)
            .where(
                EditorDocumentBlock.document_id == document_id,
                EditorDocumentBlock.is_active.is_(True),
            )
            .order_by(EditorDocumentBlock.position_index.asc(), EditorDocumentBlock.id.asc())
        ).all()

    assert document is not None
    assert [block.block_key for block in active_blocks] == ["H1-001", "P-002", "P-003"]
    assert [block.text_content for block in active_blocks] == [
        "Updated heading",
        "Original paragraph with refined detail.",
        "New support paragraph.",
    ]
    assert document.source_content == (
        "<h1>Updated heading</h1>\n"
        "<p>Original paragraph with refined detail.</p>\n"
        "<p>New support paragraph.</p>"
    )
    assert document.normalized_content == (
        "Updated heading\n\nOriginal paragraph with refined detail.\n\nNew support paragraph."
    )
