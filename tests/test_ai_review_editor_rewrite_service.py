from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.db.models import EditorDocument, EditorDocumentBlock, EditorReviewIssue, EditorRewriteRun, Site
import app.services.ai_review_editor_service as ai_review_editor_service
import app.services.editor_document_block_service as editor_document_block_service
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


def _seed_reviewed_document(session_factory) -> dict[str, int]:
    with session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com")
        session.add(site)
        session.flush()

        document = ai_review_editor_service.create_document(
            session,
            int(site.id),
            title="AI Review Rewrite Draft",
            document_type="article",
            source_format="html",
            source_content="""
                <h1>Overview section</h1>
                <p>TODO: Replace this draft with final copy after product review and approval.</p>
                <p>Lorem ipsum dolor sit amet, placeholder text for the final example paragraph.</p>
                <p>This paragraph is descriptive enough to stay clean.</p>
            """,
            topic_brief_json={"primary_topic": "local SEO services"},
            facts_context_json={"brand": "Example", "services": ["Local SEO", "SEO Audit"]},
        )
        document_id = int(document["id"])
        ai_review_editor_service.parse_document_into_blocks(session, int(site.id), document_id)
        review_run = editor_review_run_service.create_review_run(
            session,
            int(site.id),
            document_id,
            review_mode="standard",
            engine_mode="mock",
        )
        session.commit()

    with session_factory() as session:
        issues = session.scalars(
            select(EditorReviewIssue)
            .where(EditorReviewIssue.document_id == document_id)
            .order_by(EditorReviewIssue.id.asc())
        ).all()

    return {
        "site_id": int(site.id),
        "document_id": document_id,
        "review_run_id": int(review_run["id"]),
        "issue_id_heading": int(next(issue.id for issue in issues if issue.issue_type == "generic_heading")),
        "issue_id_todo": int(next(issue.id for issue in issues if issue.issue_type == "todo_marker")),
        "issue_id_placeholder": int(next(issue.id for issue in issues if issue.issue_type == "placeholder_text")),
    }


def test_dismiss_issue_updates_status_and_reason(sqlite_session_factory) -> None:
    ids = _seed_reviewed_document(sqlite_session_factory)

    with sqlite_session_factory() as session:
        payload = editor_rewrite_service.dismiss_issue(
            session,
            ids["site_id"],
            ids["document_id"],
            ids["issue_id_heading"],
            dismiss_reason="Heading will be handled in a later edit pass.",
        )
        session.commit()

    with sqlite_session_factory() as session:
        issue = session.get(EditorReviewIssue, ids["issue_id_heading"])

    assert payload["status"] == "dismissed"
    assert payload["dismiss_reason"] == "Heading will be handled in a later edit pass."
    assert issue is not None
    assert issue.status == "dismissed"
    assert issue.dismiss_reason == "Heading will be handled in a later edit pass."
    assert issue.resolution_note is None


def test_manual_resolve_sets_resolved_manual_and_does_not_create_rewrite_run(sqlite_session_factory) -> None:
    ids = _seed_reviewed_document(sqlite_session_factory)

    with sqlite_session_factory() as session:
        payload = editor_rewrite_service.resolve_issue_manually(
            session,
            ids["site_id"],
            ids["document_id"],
            ids["issue_id_todo"],
            resolution_note="The TODO paragraph was replaced manually in the editor.",
        )
        session.commit()

        rewrite_runs = session.scalars(
            select(EditorRewriteRun).where(EditorRewriteRun.review_issue_id == ids["issue_id_todo"])
        ).all()

    assert payload["status"] == "resolved_manual"
    assert payload["resolution_note"] == "The TODO paragraph was replaced manually in the editor."
    assert rewrite_runs == []


def test_issue_actions_require_current_review_state(sqlite_session_factory) -> None:
    ids = _seed_reviewed_document(sqlite_session_factory)

    with sqlite_session_factory() as session:
        active_blocks = session.scalars(
            select(EditorDocumentBlock)
            .where(
                EditorDocumentBlock.document_id == ids["document_id"],
                EditorDocumentBlock.is_active.is_(True),
            )
            .order_by(EditorDocumentBlock.position_index.asc(), EditorDocumentBlock.id.asc())
        ).all()
        todo_block = next(block for block in active_blocks if block.block_key == "P-002")
        editor_document_block_service.update_document_block(
            session,
            ids["site_id"],
            ids["document_id"],
            todo_block.block_key,
            text_content="Verified offer details replace the old TODO paragraph.",
            expected_content_hash=todo_block.content_hash,
        )
        session.commit()

    with sqlite_session_factory() as session:
        with pytest.raises(editor_rewrite_service.EditorRewriteServiceError) as dismiss_exc:
            editor_rewrite_service.dismiss_issue(
                session,
                ids["site_id"],
                ids["document_id"],
                ids["issue_id_heading"],
            )
        with pytest.raises(editor_rewrite_service.EditorRewriteServiceError) as resolve_exc:
            editor_rewrite_service.resolve_issue_manually(
                session,
                ids["site_id"],
                ids["document_id"],
                ids["issue_id_todo"],
            )
        with pytest.raises(editor_rewrite_service.EditorRewriteServiceError) as rewrite_exc:
            editor_rewrite_service.request_issue_rewrite(
                session,
                ids["site_id"],
                ids["document_id"],
                ids["issue_id_placeholder"],
                client=_RecordingRewriteClient(
                    [
                        {
                            "block_key": "P-003",
                            "rewritten_text": "Should never be generated for a stale review issue.",
                        }
                    ]
                ),
            )

    assert dismiss_exc.value.code == "issue_review_stale"
    assert resolve_exc.value.code == "issue_review_stale"
    assert rewrite_exc.value.code == "issue_review_stale"


def test_request_issue_rewrite_creates_completed_run_and_marks_issue_ready(sqlite_session_factory) -> None:
    ids = _seed_reviewed_document(sqlite_session_factory)
    fake_client = _RecordingRewriteClient(
        [
            {
                "block_key": "P-003",
                "rewritten_text": "This section describes the local SEO service using only verified offer details.",
            }
        ]
    )

    with sqlite_session_factory() as session:
        rewrite_run = editor_rewrite_service.request_issue_rewrite(
            session,
            ids["site_id"],
            ids["document_id"],
            ids["issue_id_placeholder"],
            client=fake_client,
        )
        rewrite_runs_payload = editor_rewrite_service.list_issue_rewrite_runs(
            session,
            ids["site_id"],
            ids["document_id"],
            ids["issue_id_placeholder"],
        )
        session.commit()

    with sqlite_session_factory() as session:
        issue = session.get(EditorReviewIssue, ids["issue_id_placeholder"])
        persisted_run = session.get(EditorRewriteRun, int(rewrite_run["id"]))

    assert rewrite_run["status"] == "completed"
    assert rewrite_run["review_issue_id"] == ids["issue_id_placeholder"]
    assert rewrite_run["block_key"] == "P-003"
    assert rewrite_run["result_text"] == "This section describes the local SEO service using only verified offer details."
    assert rewrite_runs_payload["items"][0]["id"] == rewrite_run["id"]
    assert issue is not None
    assert issue.status == "rewrite_ready"
    assert persisted_run is not None
    assert persisted_run.status == "completed"
    assert fake_client.user_payloads[0]["issue"]["issue_type"] == "placeholder_text"


def test_apply_rewrite_updates_only_target_block_and_marks_issue_applied(sqlite_session_factory) -> None:
    ids = _seed_reviewed_document(sqlite_session_factory)
    fake_client = _RecordingRewriteClient(
        [
            {
                "block_key": "P-003",
                "rewritten_text": "This section explains the local SEO service scope with verified offer details.",
            }
        ]
    )

    with sqlite_session_factory() as session:
        rewrite_run = editor_rewrite_service.request_issue_rewrite(
            session,
            ids["site_id"],
            ids["document_id"],
            ids["issue_id_placeholder"],
            client=fake_client,
        )
        session.commit()

    with sqlite_session_factory() as session:
        blocks_before = session.scalars(
            select(EditorDocumentBlock)
            .where(
                EditorDocumentBlock.document_id == ids["document_id"],
                EditorDocumentBlock.is_active.is_(True),
            )
            .order_by(EditorDocumentBlock.position_index.asc(), EditorDocumentBlock.id.asc())
        ).all()
        apply_payload = editor_rewrite_service.apply_rewrite_run(
            session,
            ids["site_id"],
            ids["document_id"],
            int(rewrite_run["id"]),
        )
        session.commit()

    with sqlite_session_factory() as session:
        document = session.get(EditorDocument, ids["document_id"])
        issue = session.get(EditorReviewIssue, ids["issue_id_placeholder"])
        applied_run = session.get(EditorRewriteRun, int(rewrite_run["id"]))
        active_blocks_after = session.scalars(
            select(EditorDocumentBlock)
            .where(
                EditorDocumentBlock.document_id == ids["document_id"],
                EditorDocumentBlock.is_active.is_(True),
            )
            .order_by(EditorDocumentBlock.position_index.asc(), EditorDocumentBlock.id.asc())
        ).all()

    before_map = {block.block_key: block.text_content for block in blocks_before}
    after_map = {block.block_key: block.text_content for block in active_blocks_after}

    assert apply_payload["issue"]["status"] == "applied"
    assert apply_payload["rewrite_run"]["status"] == "applied"
    assert issue is not None
    assert issue.status == "applied"
    assert applied_run is not None
    assert applied_run.status == "applied"
    assert len(active_blocks_after) == len(blocks_before)
    assert before_map["H1-001"] == after_map["H1-001"]
    assert before_map["P-002"] == after_map["P-002"]
    assert before_map["P-003"] != after_map["P-003"]
    assert after_map["P-003"] == "This section explains the local SEO service scope with verified offer details."
    assert document is not None
    assert "This section explains the local SEO service scope with verified offer details." in document.source_content
    assert "Lorem ipsum" not in document.source_content


def test_apply_rewrite_rejects_document_change_after_rewrite_generation(sqlite_session_factory) -> None:
    ids = _seed_reviewed_document(sqlite_session_factory)
    fake_client = _RecordingRewriteClient(
        [
            {
                "block_key": "P-003",
                "rewritten_text": "This section explains the local SEO service scope with verified offer details.",
            }
        ]
    )

    with sqlite_session_factory() as session:
        rewrite_run = editor_rewrite_service.request_issue_rewrite(
            session,
            ids["site_id"],
            ids["document_id"],
            ids["issue_id_placeholder"],
            client=fake_client,
        )
        session.commit()

    with sqlite_session_factory() as session:
        editor_document_block_service.insert_document_block(
            session,
            ids["site_id"],
            ids["document_id"],
            target_block_key="P-003",
            position="after",
            block_type="paragraph",
            text_content="A later document edit changes the current block set.",
        )
        session.commit()

    with sqlite_session_factory() as session:
        rewrite_runs_payload = editor_rewrite_service.list_issue_rewrite_runs(
            session,
            ids["site_id"],
            ids["document_id"],
            ids["issue_id_placeholder"],
        )
        with pytest.raises(editor_rewrite_service.EditorRewriteServiceError) as exc_info:
            editor_rewrite_service.apply_rewrite_run(
                session,
                ids["site_id"],
                ids["document_id"],
                int(rewrite_run["id"]),
            )

    assert rewrite_runs_payload["items"][0]["matches_current_document"] is False
    assert rewrite_runs_payload["items"][0]["is_stale"] is True
    assert exc_info.value.code == "rewrite_input_mismatch"


def test_apply_rewrite_rejects_failed_run_and_wrong_document_issue_guard(sqlite_session_factory) -> None:
    ids = _seed_reviewed_document(sqlite_session_factory)
    invalid_client = _RecordingRewriteClient(
        [
            {
                "block_key": "P-999",
                "rewritten_text": "This output should make the rewrite run fail.",
            }
        ]
    )

    with sqlite_session_factory() as session:
        failed_run = editor_rewrite_service.request_issue_rewrite(
            session,
            ids["site_id"],
            ids["document_id"],
            ids["issue_id_placeholder"],
            client=invalid_client,
        )
        session.commit()

    with sqlite_session_factory() as session:
        with pytest.raises(editor_rewrite_service.EditorRewriteServiceError) as apply_exc:
            editor_rewrite_service.apply_rewrite_run(
                session,
                ids["site_id"],
                ids["document_id"],
                int(failed_run["id"]),
            )
        with pytest.raises(editor_rewrite_service.EditorRewriteServiceError) as wrong_doc_exc:
            editor_rewrite_service.request_issue_rewrite(
                session,
                ids["site_id"],
                ids["document_id"] + 999,
                ids["issue_id_placeholder"],
                client=_RecordingRewriteClient(
                    [
                        {
                            "block_key": "P-003",
                            "rewritten_text": "Should never be used.",
                        }
                    ]
                ),
            )

    assert failed_run["status"] == "failed"
    assert apply_exc.value.code == "rewrite_not_ready"
    assert wrong_doc_exc.value.code == "not_found"
