from __future__ import annotations

import json

from sqlalchemy import select

from app.db.models import EditorReviewIssue, EditorReviewRun, Site
import app.services.ai_review_editor_service as ai_review_editor_service
import app.services.editor_review_run_service as editor_review_run_service


class _RecordingLlmClient:
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
            raise AssertionError("No fake LLM payload configured for editor review.")
        return response_format.model_validate(self._payloads.pop(0))


def _seed_site(session_factory) -> int:
    with session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com")
        session.add(site)
        session.commit()
        return int(site.id)


def _seed_parsed_document(session_factory, site_id: int) -> int:
    with session_factory() as session:
        created = ai_review_editor_service.create_document(
            session,
            site_id,
            title="AI Review Draft",
            document_type="article",
            source_format="html",
            source_content="""
                <h1>Overview section</h1>
                <h2>Plan</h2>
                <p>TODO: Replace this draft with final copy after product review and approval.</p>
                <p>Lorem ipsum dolor sit amet, placeholder text for the final example paragraph.</p>
                <p>Too short.</p>
                <p>This paragraph is descriptive enough to stay clean and should not create an issue.</p>
            """,
            topic_brief_json=None,
            facts_context_json=None,
        )
        document_id = int(created["id"])
        ai_review_editor_service.parse_document_into_blocks(session, site_id, document_id)
        session.commit()
        return document_id


def test_create_review_run_persists_issues_and_preserves_history(sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)
    document_id = _seed_parsed_document(sqlite_session_factory, site_id)

    with sqlite_session_factory() as session:
        first_run = editor_review_run_service.create_review_run(
            session,
            site_id,
            document_id,
            review_mode="standard",
            engine_mode="mock",
        )
        session.commit()
        second_run = editor_review_run_service.create_review_run(
            session,
            site_id,
            document_id,
            review_mode="strict",
            engine_mode="mock",
        )
        session.commit()

        runs_payload = editor_review_run_service.list_review_runs(session, site_id, document_id)
        latest_run_payload = editor_review_run_service.get_review_run(session, site_id, document_id, int(second_run["id"]))
        document_issues_payload = editor_review_run_service.list_document_issues(session, site_id, document_id)
        first_run_issues_payload = editor_review_run_service.list_review_run_issues(
            session,
            site_id,
            document_id,
            review_run_id=int(first_run["id"]),
        )
        summary_payload = editor_review_run_service.get_review_summary(session, site_id, document_id)

        persisted_runs = session.scalars(
            select(EditorReviewRun)
            .where(EditorReviewRun.document_id == document_id)
            .order_by(EditorReviewRun.id.asc())
        ).all()
        persisted_issues = session.scalars(
            select(EditorReviewIssue)
            .where(EditorReviewIssue.document_id == document_id)
            .order_by(EditorReviewIssue.id.asc())
        ).all()

    assert first_run["status"] == "completed"
    assert first_run["review_mode"] == "standard"
    assert first_run["issue_count"] == 5
    assert first_run["issue_block_count"] == 5
    assert first_run["severity_counts"] == {"low": 0, "medium": 3, "high": 2}
    assert first_run["document_version_hash"] == second_run["document_version_hash"]

    assert second_run["status"] == "completed"
    assert second_run["review_mode"] == "strict"
    assert second_run["issue_count"] >= first_run["issue_count"]

    assert [item["id"] for item in runs_payload["items"]] == [int(second_run["id"]), int(first_run["id"])]
    assert latest_run_payload["id"] == second_run["id"]
    assert document_issues_payload["review_run_id"] == second_run["id"]
    assert len(document_issues_payload["items"]) == second_run["issue_count"]
    assert first_run_issues_payload["review_run_id"] == first_run["id"]
    assert len(first_run_issues_payload["items"]) == first_run["issue_count"]

    assert summary_payload["review_run_count"] == 2
    assert summary_payload["latest_review_run_id"] == second_run["id"]
    assert summary_payload["latest_review_run_status"] == "completed"
    assert summary_payload["issue_count"] == second_run["issue_count"]
    assert summary_payload["issue_block_count"] == second_run["issue_block_count"]
    assert summary_payload["severity_counts"] == second_run["severity_counts"]

    assert len(persisted_runs) == 2
    assert len(persisted_issues) == first_run["issue_count"] + second_run["issue_count"]
    assert {issue.review_run_id for issue in persisted_issues} == {int(first_run["id"]), int(second_run["id"])}


def test_create_review_run_without_active_blocks_creates_failed_run(sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        created = ai_review_editor_service.create_document(
            session,
            site_id,
            title="Unparsed Draft",
            document_type="article",
            source_format="html",
            source_content="<h1>Pending</h1><p>No parsed blocks yet.</p>",
            topic_brief_json=None,
            facts_context_json=None,
        )
        document_id = int(created["id"])
        session.commit()

        failed_run = editor_review_run_service.create_review_run(
            session,
            site_id,
            document_id,
            review_mode="standard",
            engine_mode="mock",
        )
        session.commit()
        runs_payload = editor_review_run_service.list_review_runs(session, site_id, document_id)
        issues_payload = editor_review_run_service.list_document_issues(session, site_id, document_id)
        summary_payload = editor_review_run_service.get_review_summary(session, site_id, document_id)

    assert failed_run["status"] == "failed"
    assert failed_run["error_code"] == "no_active_blocks"
    assert failed_run["issue_count"] == 0
    assert runs_payload["items"][0]["status"] == "failed"
    assert issues_payload["review_run_id"] == failed_run["id"]
    assert issues_payload["items"] == []
    assert summary_payload["review_run_count"] == 1
    assert summary_payload["latest_review_run_status"] == "failed"
    assert summary_payload["issue_count"] == 0


def test_create_review_run_with_llm_completes_and_keeps_run_history(sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)
    document_id = _seed_parsed_document(sqlite_session_factory, site_id)

    first_client = _RecordingLlmClient(
        [
            {
                "document_issues": [],
                "block_issues": [
                    {
                        "block_key": "H1-001",
                        "issue_type": "weak_heading",
                        "severity": "medium",
                        "confidence": 0.82,
                        "message": "Heading is too generic for the topic brief.",
                        "reason": "The heading only says overview instead of naming the actual topic.",
                    },
                    {
                        "block_key": "P-003",
                        "issue_type": "unsupported_claim",
                        "severity": "high",
                        "confidence": 0.93,
                        "message": "The TODO paragraph contains a claim that is not grounded in the provided context.",
                        "reason": "The block promises a reviewed final copy, but the facts context is empty.",
                        "replacement_instruction": "Replace the claim with verified copy only.",
                    },
                    {
                        "block_key": "P-999",
                        "issue_type": "unsupported_claim",
                        "severity": "medium",
                        "message": "Unknown block key should be filtered out.",
                    },
                ],
            }
        ]
    )
    second_client = _RecordingLlmClient(
        [
            {
                "document_issues": [],
                "block_issues": [
                    {
                        "block_key": "H1-001",
                        "issue_type": "weak_heading",
                        "severity": "medium",
                        "confidence": 0.8,
                        "message": "Heading still needs more specificity.",
                    },
                    {
                        "block_key": "P-004",
                        "issue_type": "product_hallucination",
                        "severity": "high",
                        "confidence": 0.96,
                        "message": "Placeholder copy introduces unsupported product details.",
                        "reason": "Lorem ipsum text cannot be verified against the brief or facts context.",
                    },
                    {
                        "block_key": "P-005",
                        "issue_type": "unclear",
                        "severity": "medium",
                        "confidence": 0.74,
                        "message": "The paragraph is too vague to be actionable for the reader.",
                    },
                ],
            }
        ]
    )

    with sqlite_session_factory() as session:
        first_run = editor_review_run_service.create_review_run(
            session,
            site_id,
            document_id,
            review_mode="standard",
            engine_mode="llm",
            client=first_client,
        )
        session.commit()
        second_run = editor_review_run_service.create_review_run(
            session,
            site_id,
            document_id,
            review_mode="strict",
            engine_mode="llm",
            client=second_client,
        )
        session.commit()

        runs_payload = editor_review_run_service.list_review_runs(session, site_id, document_id)
        latest_issues_payload = editor_review_run_service.list_document_issues(session, site_id, document_id)
        first_run_issues_payload = editor_review_run_service.list_review_run_issues(
            session,
            site_id,
            document_id,
            review_run_id=int(first_run["id"]),
        )

        persisted_issues = session.scalars(
            select(EditorReviewIssue)
            .where(EditorReviewIssue.document_id == document_id)
            .order_by(EditorReviewIssue.id.asc())
        ).all()

    assert first_run["status"] == "completed"
    assert first_run["model_name"] == "gpt-5.4"
    assert first_run["issue_count"] == 2
    assert second_run["status"] == "completed"
    assert second_run["issue_count"] == 3
    assert [item["id"] for item in runs_payload["items"]] == [int(second_run["id"]), int(first_run["id"])]
    assert latest_issues_payload["review_run_id"] == second_run["id"]
    assert len(latest_issues_payload["items"]) == 3
    assert len(first_run_issues_payload["items"]) == 2
    assert {issue.review_run_id for issue in persisted_issues} == {int(first_run["id"]), int(second_run["id"])}
    assert first_client.user_payloads[0]["review_mode"] == "standard"
    assert second_client.user_payloads[0]["review_mode"] == "strict"


def test_create_review_run_with_llm_marks_run_failed_for_unusable_output(sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)
    document_id = _seed_parsed_document(sqlite_session_factory, site_id)
    fake_client = _RecordingLlmClient(
        [
            {
                "document_issues": [],
                "block_issues": [
                    {
                        "block_key": "P-999",
                        "issue_type": "unsupported_claim",
                        "severity": "medium",
                        "message": "This block key does not exist in the document.",
                    }
                ],
            }
        ]
    )

    with sqlite_session_factory() as session:
        failed_run = editor_review_run_service.create_review_run(
            session,
            site_id,
            document_id,
            review_mode="standard",
            engine_mode="llm",
            client=fake_client,
        )
        session.commit()
        persisted_issues = session.scalars(
            select(EditorReviewIssue).where(EditorReviewIssue.review_run_id == int(failed_run["id"]))
        ).all()

    assert failed_run["status"] == "failed"
    assert failed_run["error_code"] == "review_output_invalid"
    assert failed_run["issue_count"] == 0
    assert persisted_issues == []
