from __future__ import annotations

from pathlib import Path
import re

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings


def test_ai_review_editor_migration_creates_stage1_tables(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "ai-review-editor-stage1.sqlite3"
    database_url = f"sqlite+pysqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(alembic_config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)

    table_names = set(inspector.get_table_names())
    assert {
        "editor_documents",
        "editor_document_blocks",
        "editor_document_versions",
        "editor_review_runs",
        "editor_review_issues",
        "editor_rewrite_runs",
    }.issubset(table_names)

    document_columns = {column["name"] for column in inspector.get_columns("editor_documents")}
    block_columns = {column["name"] for column in inspector.get_columns("editor_document_blocks")}
    version_columns = {column["name"] for column in inspector.get_columns("editor_document_versions")}
    review_run_columns = {column["name"] for column in inspector.get_columns("editor_review_runs")}
    review_issue_columns = {column["name"] for column in inspector.get_columns("editor_review_issues")}
    rewrite_run_columns = {column["name"] for column in inspector.get_columns("editor_rewrite_runs")}
    version_constraints = inspector.get_check_constraints("editor_document_versions")
    review_issue_constraints = inspector.get_check_constraints("editor_review_issues")

    assert {
        "site_id",
        "title",
        "document_type",
        "source_format",
        "source_content",
        "normalized_content",
        "topic_brief_json",
        "facts_context_json",
        "status",
    }.issubset(document_columns)
    assert {
        "document_id",
        "block_key",
        "block_type",
        "position_index",
        "text_content",
        "context_path",
        "content_hash",
        "is_active",
    }.issubset(block_columns)
    assert {
        "document_id",
        "version_no",
        "source_of_change",
        "version_hash",
        "snapshot_json",
        "metadata_json",
    }.issubset(version_columns)
    assert {
        "document_id",
        "document_version_hash",
        "review_mode",
        "status",
        "model_name",
        "prompt_version",
        "schema_version",
        "input_hash",
    }.issubset(review_run_columns)
    assert {
        "dismiss_reason",
        "resolution_note",
        "replacement_candidate_text",
        "resolved_at",
    }.issubset(review_issue_columns)
    assert {
        "review_issue_id",
        "block_key",
        "source_block_content_hash",
        "schema_version",
        "result_text",
        "applied_at",
        "error_code",
        "error_message",
    }.issubset(rewrite_run_columns)
    assert any(
        "manual_block_edit" in str(constraint.get("sqltext") or "")
        and "block_insert" in str(constraint.get("sqltext") or "")
        and "block_delete" in str(constraint.get("sqltext") or "")
        for constraint in version_constraints
    )
    status_sql = next(
        str(constraint.get("sqltext") or "")
        for constraint in review_issue_constraints
        if constraint.get("name") == "ck_editor_review_issues_status"
    )
    status_tokens = set(re.findall(r"'([^']+)'", status_sql))
    assert "resolved_manual" in status_tokens
    assert "resolved" not in status_tokens

    engine.dispose()
    get_settings.cache_clear()
