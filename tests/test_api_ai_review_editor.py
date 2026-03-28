from __future__ import annotations

import json

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import EditorDocument, EditorDocumentBlock, EditorReviewIssue, EditorReviewRun, EditorRewriteRun, Site
import app.services.editor_rewrite_llm_service as editor_rewrite_llm_service
import app.services.editor_review_llm_service as editor_review_llm_service


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
            raise AssertionError("No fake LLM payload configured for API test.")
        return response_format.model_validate(self._payloads.pop(0))


def _force_mock_review_engine(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "editor_review_engine_mode", "mock")


def _force_rewrite_llm(monkeypatch, fake_client: _RecordingLlmClient) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_llm_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(editor_rewrite_llm_service, "OpenAiLlmClient", lambda: fake_client)


def _seed_site(sqlite_session_factory) -> int:
    with sqlite_session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com")
        session.add(site)
        session.commit()
        return int(site.id)


def _create_and_parse_document(
    api_client,
    site_id: int,
    *,
    source_content: str,
    topic_brief_json: dict | None = None,
    facts_context_json: dict | None = None,
) -> int:
    create_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents",
        json={
            "title": "Review Draft",
            "document_type": "article",
            "source_format": "html",
            "source_content": source_content,
            "topic_brief_json": topic_brief_json,
            "facts_context_json": facts_context_json,
        },
    )
    assert create_response.status_code == 201
    document_id = create_response.json()["id"]
    parse_response = api_client.post(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/parse")
    assert parse_response.status_code == 200
    return int(document_id)


def test_editor_document_crud_endpoints(api_client, sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)

    create_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents",
        json={
            "title": "Local SEO Landing Page",
            "document_type": "money_page",
            "source_format": "html",
            "source_content": "<h1>Local SEO</h1><p>Draft page.</p>",
            "topic_brief_json": {"topic": "local seo"},
            "facts_context_json": {"brand": "Example"},
        },
    )
    assert create_response.status_code == 201
    created_payload = create_response.json()
    document_id = created_payload["id"]
    assert created_payload["status"] == "draft"
    assert created_payload["active_block_count"] == 0
    assert created_payload["topic_brief_json"] == {"topic": "local seo"}

    get_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Local SEO Landing Page"

    update_response = api_client.put(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}",
        json={
            "title": "Updated Local SEO Landing Page",
            "facts_context_json": {"brand": "Example", "market": "PL"},
        },
    )
    assert update_response.status_code == 200
    updated_payload = update_response.json()
    assert updated_payload["title"] == "Updated Local SEO Landing Page"
    assert updated_payload["facts_context_json"] == {"brand": "Example", "market": "PL"}


def test_editor_document_list_endpoint_returns_documents_for_site(api_client, sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)
    first_document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="<h1>First</h1><p>Document one.</p>",
    )
    second_document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="<h1>Second</h1><p>Document two.</p>",
    )

    list_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["site_id"] == site_id
    assert [item["id"] for item in payload["items"]] == [second_document_id, first_document_id]
    assert payload["items"][0]["title"] == "Review Draft"
    assert payload["items"][0]["document_type"] == "article"
    assert payload["items"][0]["status"] == "parsed"
    assert payload["items"][0]["active_block_count"] == 2


def test_parse_document_endpoint_persists_blocks_and_list_endpoint_returns_them(
    api_client,
    sqlite_session_factory,
) -> None:
    site_id = _seed_site(sqlite_session_factory)
    create_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents",
        json={
            "title": "Internal Linking Draft",
            "document_type": "article",
            "source_format": "html",
            "source_content": """
                <h1>Internal Linking</h1>
                <p>Start from your strongest pages.</p>
                <h2>Implementation</h2>
                <p>Use descriptive anchors.</p>
                <ul><li>Add one link per paragraph cluster.</li></ul>
            """,
        },
    )
    document_id = create_response.json()["id"]

    parse_response = api_client.post(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/parse")
    assert parse_response.status_code == 200
    parse_payload = parse_response.json()
    assert parse_payload["blocks_created_count"] == 5
    assert parse_payload["replaced_block_count"] == 0
    assert parse_payload["document"]["status"] == "parsed"
    assert "Internal Linking" in (parse_payload["document"]["normalized_content"] or "")

    list_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks")
    assert list_response.status_code == 200
    blocks_payload = list_response.json()
    assert [item["block_key"] for item in blocks_payload["items"]] == [
        "H1-001",
        "P-002",
        "H2-003",
        "P-004",
        "LI-005",
    ]
    assert [item["position_index"] for item in blocks_payload["items"]] == [1, 2, 3, 4, 5]
    assert blocks_payload["items"][2]["context_path"] == "Internal Linking > Implementation"
    assert blocks_payload["items"][4]["text_content"] == "Add one link per paragraph cluster."

    with sqlite_session_factory() as session:
        document = session.get(EditorDocument, document_id)
        persisted_blocks = session.scalars(
            select(EditorDocumentBlock)
            .where(
                EditorDocumentBlock.document_id == document_id,
                EditorDocumentBlock.is_active.is_(True),
            )
            .order_by(EditorDocumentBlock.position_index.asc())
        ).all()

    assert document is not None
    assert document.status == "parsed"
    assert len(persisted_blocks) == 5
    assert persisted_blocks[0].block_key == "H1-001"


def test_updating_source_content_reparses_blocks_and_keeps_document_current(api_client, sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)
    create_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents",
        json={
            "title": "Draft",
            "document_type": "article",
            "source_format": "html",
            "source_content": "<h1>Before</h1><p>Old block.</p>",
        },
    )
    document_id = create_response.json()["id"]
    parse_response = api_client.post(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/parse")
    assert parse_response.status_code == 200
    assert parse_response.json()["blocks_created_count"] == 2

    update_response = api_client.put(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}",
        json={"source_content": "<h1>After</h1><p>Fresh block.</p>"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "parsed"
    assert update_response.json()["active_block_count"] == 2
    assert update_response.json()["normalized_content"] == "After\n\nFresh block."

    blocks_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks")
    assert blocks_response.status_code == 200
    assert [item["text_content"] for item in blocks_response.json()["items"]] == ["After", "Fresh block."]

    with sqlite_session_factory() as session:
        blocks = session.scalars(
            select(EditorDocumentBlock)
            .where(EditorDocumentBlock.document_id == document_id)
            .order_by(EditorDocumentBlock.id.asc())
        ).all()

    assert len(blocks) == 4
    assert [block.is_active for block in blocks] == [False, False, True, True]


def test_manual_block_update_endpoint_updates_one_block_and_creates_manual_edit_version(
    api_client,
    sqlite_session_factory,
) -> None:
    site_id = _seed_site(sqlite_session_factory)
    document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Pricing guide</h1>
            <p>TODO add verified pricing details.</p>
            <p>All subscriptions renew monthly.</p>
        """,
    )

    blocks_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks")
    assert blocks_response.status_code == 200
    target_block = next(item for item in blocks_response.json()["items"] if item["block_key"] == "P-002")

    update_block_response = api_client.put(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks/P-002",
        json={
            "text_content": "Verified pricing details are summarized below.",
            "expected_content_hash": target_block["content_hash"],
        },
    )
    assert update_block_response.status_code == 200
    update_payload = update_block_response.json()
    assert update_payload["changed"] is True
    assert update_payload["updated_block"]["block_key"] == "P-002"
    assert update_payload["updated_block"]["text_content"] == "Verified pricing details are summarized below."
    assert update_payload["current_version"]["source_of_change"] == "manual_block_edit"
    assert update_payload["current_version"]["version_no"] == 2
    assert update_payload["document"]["normalized_content"] == (
        "Pricing guide\n\nVerified pricing details are summarized below.\n\nAll subscriptions renew monthly."
    )

    refreshed_blocks_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks")
    assert refreshed_blocks_response.status_code == 200
    assert [item["text_content"] for item in refreshed_blocks_response.json()["items"]] == [
        "Pricing guide",
        "Verified pricing details are summarized below.",
        "All subscriptions renew monthly.",
    ]

    versions_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/versions")
    assert versions_response.status_code == 200
    versions_payload = versions_response.json()
    assert versions_payload["items"][0]["source_of_change"] == "manual_block_edit"
    assert versions_payload["items"][1]["source_of_change"] == "document_parse"


def test_manual_block_update_endpoint_returns_conflict_for_stale_hash(api_client, sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)
    document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Pricing guide</h1>
            <p>TODO add verified pricing details.</p>
            <p>All subscriptions renew monthly.</p>
        """,
    )

    blocks_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks")
    assert blocks_response.status_code == 200
    target_block = next(item for item in blocks_response.json()["items"] if item["block_key"] == "P-002")

    first_update_response = api_client.put(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks/P-002",
        json={
            "text_content": "Verified pricing details are summarized below.",
            "expected_content_hash": target_block["content_hash"],
        },
    )
    assert first_update_response.status_code == 200

    conflict_response = api_client.put(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks/P-002",
        json={
            "text_content": "Another update that should conflict.",
            "expected_content_hash": target_block["content_hash"],
        },
    )
    assert conflict_response.status_code == 409
    assert "changed after the editor loaded it" in conflict_response.json()["detail"]


def test_block_insert_endpoints_support_before_and_after_and_create_versions(api_client, sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)
    document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Pricing guide</h1>
            <p>TODO add verified pricing details.</p>
            <p>All subscriptions renew monthly.</p>
        """,
    )

    insert_before_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks",
        json={
            "target_block_key": "P-003",
            "position": "before",
            "block_type": "paragraph",
            "text_content": "Key pricing variables include seats and usage volume.",
        },
    )
    assert insert_before_response.status_code == 201
    insert_before_payload = insert_before_response.json()
    assert insert_before_payload["inserted_block"]["block_key"] == "P-004"
    assert insert_before_payload["inserted_block"]["position_index"] == 3
    assert insert_before_payload["current_version"]["source_of_change"] == "block_insert"

    insert_after_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks",
        json={
            "target_block_key": "P-002",
            "position": "after",
            "block_type": "heading",
            "block_level": 2,
            "text_content": "Plan details",
        },
    )
    assert insert_after_response.status_code == 201
    insert_after_payload = insert_after_response.json()
    assert insert_after_payload["inserted_block"]["block_key"] == "H2-005"
    assert insert_after_payload["inserted_block"]["context_path"] == "Pricing guide > Plan details"
    assert insert_after_payload["current_version"]["source_of_change"] == "block_insert"
    assert insert_after_payload["current_version"]["version_no"] == 3

    blocks_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks")
    assert blocks_response.status_code == 200
    assert [item["block_key"] for item in blocks_response.json()["items"]] == [
        "H1-001",
        "P-002",
        "H2-005",
        "P-004",
        "P-003",
    ]

    versions_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/versions")
    assert versions_response.status_code == 200
    assert [item["source_of_change"] for item in versions_response.json()["items"]] == [
        "block_insert",
        "block_insert",
        "document_parse",
    ]


def test_block_delete_endpoint_removes_one_block_and_rejects_last_block_delete(api_client, sqlite_session_factory) -> None:
    site_id = _seed_site(sqlite_session_factory)
    document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Pricing guide</h1>
            <p>TODO add verified pricing details.</p>
            <p>All subscriptions renew monthly.</p>
        """,
    )

    delete_response = api_client.delete(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks/P-002",
    )
    assert delete_response.status_code == 200
    delete_payload = delete_response.json()
    assert delete_payload["deleted_block_key"] == "P-002"
    assert delete_payload["remaining_block_count"] == 2
    assert delete_payload["current_version"]["source_of_change"] == "block_delete"

    blocks_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks")
    assert blocks_response.status_code == 200
    assert [item["block_key"] for item in blocks_response.json()["items"]] == ["H1-001", "P-003"]

    versions_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/versions")
    assert versions_response.status_code == 200
    assert [item["source_of_change"] for item in versions_response.json()["items"]] == [
        "block_delete",
        "document_parse",
    ]

    single_block_document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="<h1>Only block</h1>",
    )
    last_block_delete_response = api_client.delete(
        f"/sites/{site_id}/ai-review-editor/documents/{single_block_document_id}/blocks/H1-001",
    )
    assert last_block_delete_response.status_code == 400
    assert "last active block cannot be deleted" in last_block_delete_response.json()["detail"].lower()

def test_review_run_endpoints_create_run_persist_issues_and_expose_summary(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    _force_mock_review_engine(monkeypatch)
    site_id = _seed_site(sqlite_session_factory)
    document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Overview section</h1>
            <h2>Plan</h2>
            <p>TODO: Replace this draft with final copy after product review and approval.</p>
            <p>Lorem ipsum dolor sit amet, placeholder text for the final example paragraph.</p>
            <p>Too short.</p>
            <p>This paragraph is descriptive enough to stay clean and should not create an issue.</p>
        """,
    )

    create_run_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs",
        json={"review_mode": "standard"},
    )
    assert create_run_response.status_code == 201
    run_payload = create_run_response.json()
    review_run_id = int(run_payload["id"])
    assert run_payload["status"] == "completed"
    assert run_payload["review_mode"] == "standard"
    assert run_payload["issue_count"] == 5
    assert run_payload["issue_block_count"] == 5
    assert run_payload["severity_counts"] == {"low": 0, "medium": 3, "high": 2}
    assert len(run_payload["document_version_hash"]) == 64
    assert len(run_payload["input_hash"]) == 64

    list_runs_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs")
    assert list_runs_response.status_code == 200
    list_runs_payload = list_runs_response.json()
    assert list_runs_payload["document_id"] == document_id
    assert [item["id"] for item in list_runs_payload["items"]] == [review_run_id]

    get_run_response = api_client.get(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs/{review_run_id}"
    )
    assert get_run_response.status_code == 200
    assert get_run_response.json()["id"] == review_run_id

    document_issues_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues")
    assert document_issues_response.status_code == 200
    document_issues_payload = document_issues_response.json()
    assert document_issues_payload["review_run_id"] == review_run_id
    assert document_issues_payload["review_matches_current_document"] is True
    assert [item["issue_type"] for item in document_issues_payload["items"]] == [
        "generic_heading",
        "weak_heading",
        "todo_marker",
        "placeholder_text",
        "short_paragraph",
    ]

    run_issues_response = api_client.get(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs/{review_run_id}/issues"
    )
    assert run_issues_response.status_code == 200
    assert run_issues_response.json()["review_run_id"] == review_run_id
    assert len(run_issues_response.json()["items"]) == 5

    summary_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-summary")
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["document_id"] == document_id
    assert summary_payload["review_run_count"] == 1
    assert summary_payload["latest_review_run_id"] == review_run_id
    assert summary_payload["latest_review_run_status"] == "completed"
    assert summary_payload["latest_review_run_finished_at"].startswith(run_payload["finished_at"].rstrip("Z"))
    assert summary_payload["latest_review_matches_current_document"] is True
    assert summary_payload["issue_count"] == 5
    assert summary_payload["issue_block_count"] == 5
    assert summary_payload["severity_counts"] == {"low": 0, "medium": 3, "high": 2}

    with sqlite_session_factory() as session:
        persisted_run = session.get(EditorReviewRun, review_run_id)
        persisted_issues = session.scalars(
            select(EditorReviewIssue)
            .where(EditorReviewIssue.review_run_id == review_run_id)
            .order_by(EditorReviewIssue.id.asc())
        ).all()

    assert persisted_run is not None
    assert persisted_run.status == "completed"
    assert [issue.block_key for issue in persisted_issues] == ["H1-001", "H2-002", "P-003", "P-004", "P-005"]


def test_second_review_run_preserves_history_and_document_issues_follow_latest_run(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    _force_mock_review_engine(monkeypatch)
    site_id = _seed_site(sqlite_session_factory)
    document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Overview section</h1>
            <h2>Plan</h2>
            <p>TODO: Replace this draft with final copy after product review and approval.</p>
            <p>Lorem ipsum dolor sit amet, placeholder text for the final example paragraph.</p>
            <p>Too short.</p>
        """,
    )

    first_run_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs",
        json={"review_mode": "standard"},
    )
    second_run_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs",
        json={"review_mode": "strict"},
    )
    first_run_id = int(first_run_response.json()["id"])
    second_run_id = int(second_run_response.json()["id"])

    list_runs_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs")
    assert list_runs_response.status_code == 200
    assert [item["id"] for item in list_runs_response.json()["items"]] == [second_run_id, first_run_id]

    document_issues_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues")
    assert document_issues_response.status_code == 200
    assert document_issues_response.json()["review_run_id"] == second_run_id

    first_run_issues_response = api_client.get(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs/{first_run_id}/issues"
    )
    second_run_issues_response = api_client.get(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs/{second_run_id}/issues"
    )
    assert first_run_issues_response.status_code == 200
    assert second_run_issues_response.status_code == 200
    assert len(second_run_issues_response.json()["items"]) >= len(first_run_issues_response.json()["items"])

    summary_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["review_run_count"] == 2
    assert summary_response.json()["latest_review_run_id"] == second_run_id

    with sqlite_session_factory() as session:
        review_runs = session.scalars(
            select(EditorReviewRun)
            .where(EditorReviewRun.document_id == document_id)
            .order_by(EditorReviewRun.id.asc())
        ).all()
        review_issues = session.scalars(
            select(EditorReviewIssue)
            .where(EditorReviewIssue.document_id == document_id)
            .order_by(EditorReviewIssue.id.asc())
        ).all()

    assert len(review_runs) == 2
    assert {issue.review_run_id for issue in review_issues} == {first_run_id, second_run_id}


def test_review_run_creation_for_unparsed_document_returns_failed_run(api_client, sqlite_session_factory, monkeypatch) -> None:
    _force_mock_review_engine(monkeypatch)
    site_id = _seed_site(sqlite_session_factory)
    create_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents",
        json={
            "title": "Unparsed Draft",
            "document_type": "article",
            "source_format": "html",
            "source_content": "<h1>Pending</h1><p>No parsed blocks yet.</p>",
        },
    )
    assert create_response.status_code == 201
    document_id = int(create_response.json()["id"])

    create_run_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs",
        json={"review_mode": "standard"},
    )
    assert create_run_response.status_code == 201
    run_payload = create_run_response.json()
    assert run_payload["status"] == "failed"
    assert run_payload["error_code"] == "no_active_blocks"
    assert run_payload["issue_count"] == 0

    issues_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues")
    assert issues_response.status_code == 200
    assert issues_response.json()["review_run_id"] == run_payload["id"]
    assert issues_response.json()["items"] == []

    summary_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["review_run_count"] == 1
    assert summary_response.json()["latest_review_run_status"] == "failed"


def test_review_run_endpoints_can_use_llm_flow_with_filtered_output(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    site_id = _seed_site(sqlite_session_factory)
    document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Overview</h1>
            <p>Example Analytics Pro is included in every local SEO package.</p>
            <p>This paragraph is properly supported by the provided brief.</p>
        """,
        topic_brief_json={"primary_topic": "local SEO services"},
        facts_context_json={"brand": "Example", "services": ["Local SEO", "SEO Audit"]},
    )

    fake_client = _RecordingLlmClient(
        [
            {
                "document_issues": [],
                "block_issues": [
                    {
                        "block_key": "P-002",
                        "issue_type": "product_hallucination",
                        "severity": "high",
                        "confidence": 0.95,
                        "message": "The paragraph names a product that is not grounded in the provided facts context.",
                        "reason": "Facts context lists services but does not mention Example Analytics Pro.",
                        "replacement_instruction": "Replace the product reference with a supported service statement.",
                    },
                    {
                        "block_key": "P-999",
                        "issue_type": "unsupported_claim",
                        "severity": "medium",
                        "message": "Unknown block key should be discarded.",
                    },
                    {
                        "block_key": "P-002",
                        "issue_type": "not_allowed",
                        "severity": "medium",
                        "message": "Unknown issue type should be discarded.",
                    },
                ],
            }
        ]
    )
    settings = get_settings()
    monkeypatch.setattr(settings, "editor_review_engine_mode", "llm")
    monkeypatch.setattr(settings, "openai_llm_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(editor_review_llm_service, "OpenAiLlmClient", lambda: fake_client)

    create_run_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs",
        json={"review_mode": "standard"},
    )
    assert create_run_response.status_code == 201
    run_payload = create_run_response.json()
    review_run_id = int(run_payload["id"])
    assert run_payload["status"] == "completed"
    assert run_payload["model_name"] == "gpt-5.4"
    assert run_payload["issue_count"] == 1
    assert run_payload["severity_counts"] == {"low": 0, "medium": 0, "high": 1}

    issues_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues")
    assert issues_response.status_code == 200
    issues_payload = issues_response.json()
    assert issues_payload["review_run_id"] == review_run_id
    assert len(issues_payload["items"]) == 1
    assert issues_payload["items"][0]["issue_type"] == "product_hallucination"
    assert issues_payload["items"][0]["block_key"] == "P-002"

    summary_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["issue_count"] == 1
    assert fake_client.user_payloads[0]["facts_context_json"] == {
        "brand": "Example",
        "services": ["Local SEO", "SEO Audit"],
    }


def test_review_run_endpoint_returns_failed_run_when_llm_output_is_unusable(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    site_id = _seed_site(sqlite_session_factory)
    document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Overview</h1>
            <p>Claim with unsupported detail.</p>
        """,
    )

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
    settings = get_settings()
    monkeypatch.setattr(settings, "editor_review_engine_mode", "llm")
    monkeypatch.setattr(settings, "openai_llm_enabled", True)
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(editor_review_llm_service, "OpenAiLlmClient", lambda: fake_client)

    create_run_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs",
        json={"review_mode": "standard"},
    )
    assert create_run_response.status_code == 201
    run_payload = create_run_response.json()
    assert run_payload["status"] == "failed"
    assert run_payload["error_code"] == "review_output_invalid"
    assert run_payload["issue_count"] == 0

    issues_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues")
    assert issues_response.status_code == 200
    assert issues_response.json()["review_run_id"] == run_payload["id"]
    assert issues_response.json()["items"] == []

    summary_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["latest_review_run_status"] == "failed"


def test_issue_decision_and_rewrite_endpoints_cover_dismiss_manual_and_apply(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    _force_mock_review_engine(monkeypatch)
    site_id = _seed_site(sqlite_session_factory)
    document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Overview</h1>
            <p>TODO: Replace this draft with final copy.</p>
            <p>This paragraph should stay untouched.</p>
        """,
        topic_brief_json={"primary_topic": "local SEO services"},
        facts_context_json={"brand": "Example", "services": ["Local SEO", "SEO Audit"]},
    )

    create_run_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs",
        json={"review_mode": "standard"},
    )
    assert create_run_response.status_code == 201
    issues_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues")
    assert issues_response.status_code == 200
    issues_payload = issues_response.json()
    heading_issue_id = next(item["id"] for item in issues_payload["items"] if item["block_key"] == "H1-001")
    todo_issue_id = next(item["id"] for item in issues_payload["items"] if item["block_key"] == "P-002")

    dismiss_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues/{heading_issue_id}/dismiss",
        json={"dismiss_reason": "Heading is acceptable for now."},
    )
    assert dismiss_response.status_code == 200
    assert dismiss_response.json()["status"] == "dismissed"
    assert dismiss_response.json()["dismiss_reason"] == "Heading is acceptable for now."

    manual_issue_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues/{todo_issue_id}/resolve-manual",
        json={"resolution_note": "User updated the block manually in the editor."},
    )
    assert manual_issue_response.status_code == 200
    assert manual_issue_response.json()["status"] == "resolved_manual"
    assert manual_issue_response.json()["resolution_note"] == "User updated the block manually in the editor."

    with sqlite_session_factory() as session:
        rewrite_runs = session.scalars(
            select(EditorRewriteRun).where(EditorRewriteRun.review_issue_id == todo_issue_id)
        ).all()
    assert rewrite_runs == []

    second_document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Overview</h1>
            <p>TODO: Replace this draft with final copy.</p>
            <p>This paragraph should stay untouched.</p>
        """,
        topic_brief_json={"primary_topic": "local SEO services"},
        facts_context_json={"brand": "Example", "services": ["Local SEO", "SEO Audit"]},
    )
    create_run_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{second_document_id}/review-runs",
        json={"review_mode": "standard"},
    )
    assert create_run_response.status_code == 201
    second_issues_payload = api_client.get(
        f"/sites/{site_id}/ai-review-editor/documents/{second_document_id}/issues"
    ).json()
    rewrite_issue_id = next(item["id"] for item in second_issues_payload["items"] if item["block_key"] == "P-002")

    fake_client = _RecordingLlmClient(
        [
            {
                "block_key": "P-002",
                "rewritten_text": "Use verified local SEO service copy only.",
            }
        ]
    )
    _force_rewrite_llm(monkeypatch, fake_client)

    request_rewrite_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{second_document_id}/issues/{rewrite_issue_id}/rewrite-runs",
        json={},
    )
    assert request_rewrite_response.status_code == 201
    rewrite_run_payload = request_rewrite_response.json()
    rewrite_run_id = int(rewrite_run_payload["id"])
    assert rewrite_run_payload["status"] == "completed"
    assert rewrite_run_payload["block_key"] == "P-002"
    assert rewrite_run_payload["matches_current_document"] is True
    assert rewrite_run_payload["matches_current_block"] is True
    assert rewrite_run_payload["is_stale"] is False

    list_rewrite_runs_response = api_client.get(
        f"/sites/{site_id}/ai-review-editor/documents/{second_document_id}/issues/{rewrite_issue_id}/rewrite-runs"
    )
    assert list_rewrite_runs_response.status_code == 200
    rewrite_runs_payload = list_rewrite_runs_response.json()
    assert [item["id"] for item in rewrite_runs_payload["items"]] == [rewrite_run_id]
    assert rewrite_runs_payload["items"][0]["matches_current_document"] is True
    assert rewrite_runs_payload["items"][0]["is_stale"] is False

    get_rewrite_run_response = api_client.get(
        f"/sites/{site_id}/ai-review-editor/documents/{second_document_id}/rewrite-runs/{rewrite_run_id}"
    )
    assert get_rewrite_run_response.status_code == 200
    assert get_rewrite_run_response.json()["result_text"] == "Use verified local SEO service copy only."

    apply_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{second_document_id}/rewrite-runs/{rewrite_run_id}/apply",
        json={},
    )
    assert apply_response.status_code == 200
    apply_payload = apply_response.json()
    assert apply_payload["issue"]["status"] == "applied"
    assert apply_payload["rewrite_run"]["status"] == "applied"
    assert apply_payload["updated_block"]["block_key"] == "P-002"
    assert apply_payload["updated_block"]["text_content"] == "Use verified local SEO service copy only."

    issues_after_apply = api_client.get(
        f"/sites/{site_id}/ai-review-editor/documents/{second_document_id}/issues"
    ).json()
    rewritten_issue = next(item for item in issues_after_apply["items"] if item["id"] == rewrite_issue_id)
    assert rewritten_issue["status"] == "applied"
    assert rewritten_issue["replacement_candidate_text"] == "Use verified local SEO service copy only."
    assert fake_client.user_payloads[0]["block"]["block_key"] == "P-002"


def test_stale_review_issue_actions_return_conflict(api_client, sqlite_session_factory, monkeypatch) -> None:
    _force_mock_review_engine(monkeypatch)
    site_id = _seed_site(sqlite_session_factory)
    document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Overview</h1>
            <p>TODO: Replace this draft with final copy.</p>
            <p>This paragraph should stay untouched.</p>
        """,
    )

    create_run_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs",
        json={"review_mode": "standard"},
    )
    assert create_run_response.status_code == 201
    issues_payload = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues").json()
    heading_issue_id = next(item["id"] for item in issues_payload["items"] if item["block_key"] == "H1-001")

    blocks_payload = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks").json()
    todo_block = next(item for item in blocks_payload["items"] if item["block_key"] == "P-002")
    update_response = api_client.put(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks/P-002",
        json={
            "text_content": "Verified final copy replaces the old TODO paragraph.",
            "expected_content_hash": todo_block["content_hash"],
        },
    )
    assert update_response.status_code == 200

    stale_issues_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues")
    assert stale_issues_response.status_code == 200
    assert stale_issues_response.json()["review_matches_current_document"] is False

    dismiss_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues/{heading_issue_id}/dismiss",
        json={},
    )
    assert dismiss_response.status_code == 409
    assert "stale review" in dismiss_response.json()["detail"].lower()


def test_rewrite_run_list_marks_stale_after_later_document_change(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    _force_mock_review_engine(monkeypatch)
    site_id = _seed_site(sqlite_session_factory)
    document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Overview</h1>
            <p>TODO: Replace this draft with final copy.</p>
            <p>This paragraph should stay untouched.</p>
        """,
        topic_brief_json={"primary_topic": "local SEO services"},
        facts_context_json={"brand": "Example", "services": ["Local SEO", "SEO Audit"]},
    )

    create_run_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs",
        json={"review_mode": "standard"},
    )
    assert create_run_response.status_code == 201
    issues_payload = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues").json()
    rewrite_issue_id = next(item["id"] for item in issues_payload["items"] if item["block_key"] == "P-002")

    fake_client = _RecordingLlmClient(
        [
            {
                "block_key": "P-002",
                "rewritten_text": "Use verified local SEO service copy only.",
            }
        ]
    )
    _force_rewrite_llm(monkeypatch, fake_client)

    request_rewrite_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues/{rewrite_issue_id}/rewrite-runs",
        json={},
    )
    assert request_rewrite_response.status_code == 201
    rewrite_run_id = int(request_rewrite_response.json()["id"])

    insert_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks",
        json={
            "target_block_key": "P-002",
            "position": "after",
            "block_type": "paragraph",
            "text_content": "A later edit changes the current active block set.",
        },
    )
    assert insert_response.status_code == 201

    rewrite_runs_response = api_client.get(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues/{rewrite_issue_id}/rewrite-runs"
    )
    assert rewrite_runs_response.status_code == 200
    rewrite_runs_payload = rewrite_runs_response.json()
    assert rewrite_runs_payload["items"][0]["id"] == rewrite_run_id
    assert rewrite_runs_payload["items"][0]["matches_current_document"] is False
    assert rewrite_runs_payload["items"][0]["matches_current_block"] is True
    assert rewrite_runs_payload["items"][0]["is_stale"] is True

    apply_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/rewrite-runs/{rewrite_run_id}/apply",
        json={},
    )
    assert apply_response.status_code == 409
    assert "no longer matches" in apply_response.json()["detail"].lower()


def test_rewrite_apply_endpoint_rejects_failed_run_and_issue_from_other_document(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    _force_mock_review_engine(monkeypatch)
    site_id = _seed_site(sqlite_session_factory)
    first_document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Overview</h1>
            <p>TODO: Replace this draft with final copy.</p>
        """,
    )
    second_document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Overview</h1>
            <p>TODO: Replace this draft with final copy.</p>
        """,
    )

    first_run_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{first_document_id}/review-runs",
        json={"review_mode": "standard"},
    )
    second_run_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{second_document_id}/review-runs",
        json={"review_mode": "standard"},
    )
    assert first_run_response.status_code == 201
    assert second_run_response.status_code == 201
    first_issue_id = next(
        item["id"]
        for item in api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{first_document_id}/issues").json()[
            "items"
        ]
        if item["block_key"] == "P-002"
    )
    second_issue_id = next(
        item["id"]
        for item in api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{second_document_id}/issues").json()[
            "items"
        ]
        if item["block_key"] == "P-002"
    )

    wrong_document_rewrite_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{first_document_id}/issues/{second_issue_id}/rewrite-runs",
        json={},
    )
    assert wrong_document_rewrite_response.status_code == 404

    fake_client = _RecordingLlmClient(
        [
            {
                "block_key": "P-002",
                "rewritten_text": "Use verified local SEO copy only.",
            }
        ]
    )
    _force_rewrite_llm(monkeypatch, fake_client)
    rewrite_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{first_document_id}/issues/{first_issue_id}/rewrite-runs",
        json={},
    )
    assert rewrite_response.status_code == 201
    rewrite_run_id = int(rewrite_response.json()["id"])

    with sqlite_session_factory() as session:
        rewrite_run = session.get(EditorRewriteRun, rewrite_run_id)
        assert rewrite_run is not None
        rewrite_run.status = "failed"
        rewrite_run.error_code = "forced_failure"
        session.commit()

    failed_apply_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{first_document_id}/rewrite-runs/{rewrite_run_id}/apply",
        json={},
    )
    assert failed_apply_response.status_code == 409
    assert "must be completed before apply" in failed_apply_response.json()["detail"].lower()


def test_document_version_endpoints_list_preview_diff_and_restore(
    api_client,
    sqlite_session_factory,
    monkeypatch,
) -> None:
    _force_mock_review_engine(monkeypatch)
    site_id = _seed_site(sqlite_session_factory)
    document_id = _create_and_parse_document(
        api_client,
        site_id,
        source_content="""
            <h1>Overview</h1>
            <p>TODO: Replace this draft with final copy.</p>
            <p>This paragraph should stay untouched.</p>
        """,
        topic_brief_json={"primary_topic": "local SEO services"},
        facts_context_json={"brand": "Example", "services": ["Local SEO", "SEO Audit"]},
    )

    issues_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/review-runs",
        json={"review_mode": "standard"},
    )
    assert issues_response.status_code == 201
    issues_payload = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues").json()
    rewrite_issue_id = next(item["id"] for item in issues_payload["items"] if item["block_key"] == "P-002")

    fake_client = _RecordingLlmClient(
        [
            {
                "block_key": "P-002",
                "rewritten_text": "Use verified local SEO copy only.",
            }
        ]
    )
    _force_rewrite_llm(monkeypatch, fake_client)
    rewrite_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/issues/{rewrite_issue_id}/rewrite-runs",
        json={},
    )
    assert rewrite_response.status_code == 201
    rewrite_run_id = int(rewrite_response.json()["id"])

    apply_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/rewrite-runs/{rewrite_run_id}/apply",
        json={},
    )
    assert apply_response.status_code == 200

    versions_response = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/versions")
    assert versions_response.status_code == 200
    versions_payload = versions_response.json()
    assert versions_payload["current_version_id"] == versions_payload["items"][0]["id"]
    assert [item["source_of_change"] for item in versions_payload["items"]] == ["rewrite_apply", "document_parse"]

    latest_version_id = int(versions_payload["items"][0]["id"])
    first_version_id = int(versions_payload["items"][1]["id"])
    version_detail_response = api_client.get(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/versions/{latest_version_id}"
    )
    assert version_detail_response.status_code == 200
    assert version_detail_response.json()["snapshot"]["blocks"][1]["text_content"] == "Use verified local SEO copy only."

    diff_response = api_client.get(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/versions/{first_version_id}/diff",
        params={"compare_to_version_id": latest_version_id},
    )
    assert diff_response.status_code == 200
    diff_payload = diff_response.json()
    assert diff_payload["summary"]["changed_blocks"] == 1
    assert diff_payload["summary"]["removed_blocks"] == 0
    assert [item["block_key"] for item in diff_payload["block_changes"]] == ["P-002"]
    assert diff_payload["block_changes"][0]["before_text"] == "Use verified local SEO copy only."
    assert diff_payload["block_changes"][0]["after_text"] == "TODO: Replace this draft with final copy."

    restore_response = api_client.post(
        f"/sites/{site_id}/ai-review-editor/documents/{document_id}/versions/{first_version_id}/restore",
        json={},
    )
    assert restore_response.status_code == 200
    restore_payload = restore_response.json()
    assert restore_payload["current_version"]["source_of_change"] == "rollback"
    assert restore_payload["restored_from_version"]["version_no"] == 1
    assert restore_payload["document"]["normalized_content"].startswith("Overview\n\nTODO:")

    blocks_after_restore = api_client.get(f"/sites/{site_id}/ai-review-editor/documents/{document_id}/blocks")
    assert blocks_after_restore.status_code == 200
    assert [item["text_content"] for item in blocks_after_restore.json()["items"]] == [
        "Overview",
        "TODO: Replace this draft with final copy.",
        "This paragraph should stay untouched.",
    ]
