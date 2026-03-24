"""Lean competitive gap persistent store for hot-path reads.

Revision ID: 0017_competitive_gap_lean_v1
Revises: 0016_competitive_gap_quality_v1
Create Date: 2026-03-19 12:40:00
"""

from __future__ import annotations

from collections.abc import Sequence
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0017_competitive_gap_lean_v1"
down_revision: str | None = "0016_competitive_gap_quality_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "site_competitor_pages",
        sa.Column("fetch_diagnostics_json", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "site_competitor_semantic_candidates",
        sa.Column("normalized_terms_json", sa.JSON(), nullable=False, server_default="[]"),
    )

    bind = op.get_bind()
    _backfill_fetch_diagnostics(bind)
    _backfill_normalized_terms(bind)
    _normalize_semantic_run_summaries(bind)
    _trim_empty_chunk_summaries(bind)

    with op.batch_alter_table("site_competitor_pages") as batch_op:
        batch_op.drop_column("robots_meta")
        batch_op.drop_column("x_robots_tag")
        batch_op.drop_column("word_count")
        batch_op.drop_column("visible_text_chars")
        batch_op.drop_column("visible_text_truncated")
        batch_op.drop_column("schema_present")
        batch_op.drop_column("schema_count")
        batch_op.drop_column("schema_types_json")
        batch_op.drop_column("page_type_version")
        batch_op.drop_column("page_type_rationale")
        batch_op.drop_column("was_rendered")
        batch_op.drop_column("render_attempted")
        batch_op.drop_column("fetch_mode_used")
        batch_op.drop_column("js_heavy_like")
        batch_op.drop_column("render_reason")
        batch_op.drop_column("render_error_message")

    with op.batch_alter_table("site_competitor_page_extractions") as batch_op:
        batch_op.drop_column("secondary_topics_json")
        batch_op.drop_column("entities_json")
        batch_op.drop_column("raw_json")

    with op.batch_alter_table("site_competitor_semantic_candidates") as batch_op:
        batch_op.drop_column("primary_tokens_json")
        batch_op.drop_column("secondary_tokens_json")
        batch_op.drop_column("match_terms_json")


def downgrade() -> None:
    op.add_column(
        "site_competitor_pages",
        sa.Column("robots_meta", sa.Text(), nullable=True),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("x_robots_tag", sa.Text(), nullable=True),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("word_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("visible_text_chars", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("visible_text_truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("schema_present", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("schema_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("schema_types_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("page_type_version", sa.String(length=64), nullable=False, server_default="unclassified"),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("page_type_rationale", sa.Text(), nullable=True),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("was_rendered", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("render_attempted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("fetch_mode_used", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("js_heavy_like", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("render_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "site_competitor_pages",
        sa.Column("render_error_message", sa.Text(), nullable=True),
    )

    op.add_column(
        "site_competitor_page_extractions",
        sa.Column("secondary_topics_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "site_competitor_page_extractions",
        sa.Column("entities_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "site_competitor_page_extractions",
        sa.Column("raw_json", sa.JSON(), nullable=True),
    )

    op.add_column(
        "site_competitor_semantic_candidates",
        sa.Column("primary_tokens_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "site_competitor_semantic_candidates",
        sa.Column("secondary_tokens_json", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "site_competitor_semantic_candidates",
        sa.Column("match_terms_json", sa.JSON(), nullable=False, server_default="[]"),
    )

    bind = op.get_bind()
    _restore_page_columns(bind)
    _restore_extraction_duplicates(bind)
    _restore_candidate_term_columns(bind)
    _restore_semantic_run_summary_ids(bind)

    with op.batch_alter_table("site_competitor_pages") as batch_op:
        batch_op.drop_column("fetch_diagnostics_json")

    with op.batch_alter_table("site_competitor_semantic_candidates") as batch_op:
        batch_op.drop_column("normalized_terms_json")


def _backfill_fetch_diagnostics(bind) -> None:
    pages = sa.table(
        "site_competitor_pages",
        sa.column("id", sa.Integer()),
        sa.column("robots_meta", sa.Text()),
        sa.column("x_robots_tag", sa.Text()),
        sa.column("visible_text_truncated", sa.Boolean()),
        sa.column("schema_count", sa.Integer()),
        sa.column("schema_types_json", sa.JSON()),
        sa.column("was_rendered", sa.Boolean()),
        sa.column("render_attempted", sa.Boolean()),
        sa.column("fetch_mode_used", sa.String()),
        sa.column("js_heavy_like", sa.Boolean()),
        sa.column("render_reason", sa.Text()),
        sa.column("render_error_message", sa.Text()),
        sa.column("fetch_diagnostics_json", sa.JSON()),
    )
    rows = bind.execute(
        sa.select(
            pages.c.id,
            pages.c.robots_meta,
            pages.c.x_robots_tag,
            pages.c.visible_text_truncated,
            pages.c.schema_count,
            pages.c.schema_types_json,
            pages.c.was_rendered,
            pages.c.render_attempted,
            pages.c.fetch_mode_used,
            pages.c.js_heavy_like,
            pages.c.render_reason,
            pages.c.render_error_message,
        )
    ).mappings()

    updates: list[dict[str, object]] = []
    for row in rows:
        schema_types = _json_list(row["schema_types_json"])
        payload: dict[str, object] = {
            "was_rendered": bool(row["was_rendered"]),
            "render_attempted": bool(row["render_attempted"]),
            "js_heavy_like": bool(row["js_heavy_like"]),
            "visible_text_truncated": bool(row["visible_text_truncated"]),
        }
        if row["fetch_mode_used"]:
            payload["fetch_mode_used"] = str(row["fetch_mode_used"])
        if row["render_reason"]:
            payload["render_reason"] = str(row["render_reason"])
        if row["render_error_message"]:
            payload["render_error_message"] = str(row["render_error_message"])
        if row["robots_meta"]:
            payload["robots_meta"] = str(row["robots_meta"])
        if row["x_robots_tag"]:
            payload["x_robots_tag"] = str(row["x_robots_tag"])
        if row["schema_count"] is not None:
            payload["schema_count"] = max(0, int(row["schema_count"]))
        elif schema_types:
            payload["schema_count"] = len(schema_types)
        if schema_types:
            payload["schema_types"] = schema_types
        updates.append(
            {
                "row_id": int(row["id"]),
                "fetch_diagnostics_json": payload,
            }
        )
    if updates:
        bind.execute(
            pages.update()
            .where(pages.c.id == sa.bindparam("row_id"))
            .values(fetch_diagnostics_json=sa.bindparam("fetch_diagnostics_json")),
            updates,
        )


def _backfill_normalized_terms(bind) -> None:
    candidates = sa.table(
        "site_competitor_semantic_candidates",
        sa.column("id", sa.Integer()),
        sa.column("primary_tokens_json", sa.JSON()),
        sa.column("secondary_tokens_json", sa.JSON()),
        sa.column("match_terms_json", sa.JSON()),
        sa.column("normalized_terms_json", sa.JSON()),
    )
    rows = bind.execute(
        sa.select(
            candidates.c.id,
            candidates.c.primary_tokens_json,
            candidates.c.secondary_tokens_json,
            candidates.c.match_terms_json,
        )
    ).mappings()

    updates: list[dict[str, object]] = []
    for row in rows:
        normalized_terms = _normalize_terms(row["match_terms_json"])
        if not normalized_terms:
            normalized_terms = _normalize_terms(row["primary_tokens_json"]) + [
                term
                for term in _normalize_terms(row["secondary_tokens_json"])
                if term not in normalized_terms
            ]
        updates.append(
            {
                "row_id": int(row["id"]),
                "normalized_terms_json": _dedupe_preserve_order(normalized_terms),
            }
        )
    if updates:
        bind.execute(
            candidates.update()
            .where(candidates.c.id == sa.bindparam("row_id"))
            .values(normalized_terms_json=sa.bindparam("normalized_terms_json")),
            updates,
        )


def _normalize_semantic_run_summaries(bind) -> None:
    runs = sa.table(
        "site_competitor_semantic_runs",
        sa.column("id", sa.Integer()),
        sa.column("summary_json", sa.JSON()),
    )
    rows = bind.execute(
        sa.select(runs.c.id, runs.c.summary_json)
    ).mappings()

    updates: list[dict[str, object]] = []
    for row in rows:
        summary = _json_dict(row["summary_json"])
        if "source_candidate_ids" not in summary:
            continue
        summary.pop("source_candidate_ids", None)
        updates.append(
            {
                "row_id": int(row["id"]),
                "summary_json": summary,
            }
        )
    if updates:
        bind.execute(
            runs.update()
            .where(runs.c.id == sa.bindparam("row_id"))
            .values(summary_json=sa.bindparam("summary_json")),
            updates,
        )


def _trim_empty_chunk_summaries(bind) -> None:
    extractions = sa.table(
        "site_competitor_page_extractions",
        sa.column("id", sa.Integer()),
        sa.column("chunk_summary_json", sa.JSON()),
    )
    rows = bind.execute(
        sa.select(extractions.c.id, extractions.c.chunk_summary_json)
    ).mappings()

    updates: list[dict[str, object]] = []
    for row in rows:
        chunk_summary = _json_dict(row["chunk_summary_json"])
        if not chunk_summary:
            continue
        chunk_cards = chunk_summary.get("chunk_cards")
        chunk_count = chunk_summary.get("chunk_count")
        if (not chunk_cards) and int(chunk_count or 0) <= 0:
            updates.append(
                {
                    "row_id": int(row["id"]),
                    "chunk_summary_json": None,
                }
            )
    if updates:
        bind.execute(
            extractions.update()
            .where(extractions.c.id == sa.bindparam("row_id"))
            .values(chunk_summary_json=sa.bindparam("chunk_summary_json")),
            updates,
        )


def _restore_page_columns(bind) -> None:
    pages = sa.table(
        "site_competitor_pages",
        sa.column("id", sa.Integer()),
        sa.column("visible_text", sa.Text()),
        sa.column("fetch_diagnostics_json", sa.JSON()),
        sa.column("robots_meta", sa.Text()),
        sa.column("x_robots_tag", sa.Text()),
        sa.column("word_count", sa.Integer()),
        sa.column("visible_text_chars", sa.Integer()),
        sa.column("visible_text_truncated", sa.Boolean()),
        sa.column("schema_present", sa.Boolean()),
        sa.column("schema_count", sa.Integer()),
        sa.column("schema_types_json", sa.JSON()),
        sa.column("page_type_version", sa.String()),
        sa.column("page_type_rationale", sa.Text()),
        sa.column("was_rendered", sa.Boolean()),
        sa.column("render_attempted", sa.Boolean()),
        sa.column("fetch_mode_used", sa.String()),
        sa.column("js_heavy_like", sa.Boolean()),
        sa.column("render_reason", sa.Text()),
        sa.column("render_error_message", sa.Text()),
    )
    rows = bind.execute(
        sa.select(
            pages.c.id,
            pages.c.visible_text,
            pages.c.fetch_diagnostics_json,
        )
    ).mappings()

    updates: list[dict[str, object]] = []
    for row in rows:
        diagnostics = _json_dict(row["fetch_diagnostics_json"])
        visible_text = _collapse_whitespace(row["visible_text"])
        schema_types = _json_list(diagnostics.get("schema_types"))
        schema_count = diagnostics.get("schema_count")
        resolved_schema_count = int(schema_count or 0) if schema_count is not None else len(schema_types)
        updates.append(
            {
                "row_id": int(row["id"]),
                "robots_meta": _optional_str(diagnostics.get("robots_meta")),
                "x_robots_tag": _optional_str(diagnostics.get("x_robots_tag")),
                "word_count": len(visible_text.split()) if visible_text else 0,
                "visible_text_chars": len(visible_text),
                "visible_text_truncated": bool(diagnostics.get("visible_text_truncated")),
                "schema_present": bool(resolved_schema_count > 0 or schema_types),
                "schema_count": resolved_schema_count,
                "schema_types_json": schema_types,
                "page_type_version": "lean_v1",
                "page_type_rationale": None,
                "was_rendered": bool(diagnostics.get("was_rendered")),
                "render_attempted": bool(diagnostics.get("render_attempted")),
                "fetch_mode_used": _optional_str(diagnostics.get("fetch_mode_used")),
                "js_heavy_like": bool(diagnostics.get("js_heavy_like")),
                "render_reason": _optional_str(diagnostics.get("render_reason")),
                "render_error_message": _optional_str(diagnostics.get("render_error_message")),
            }
        )
    if updates:
        bind.execute(
            pages.update()
            .where(pages.c.id == sa.bindparam("row_id"))
            .values(
                robots_meta=sa.bindparam("robots_meta"),
                x_robots_tag=sa.bindparam("x_robots_tag"),
                word_count=sa.bindparam("word_count"),
                visible_text_chars=sa.bindparam("visible_text_chars"),
                visible_text_truncated=sa.bindparam("visible_text_truncated"),
                schema_present=sa.bindparam("schema_present"),
                schema_count=sa.bindparam("schema_count"),
                schema_types_json=sa.bindparam("schema_types_json"),
                page_type_version=sa.bindparam("page_type_version"),
                page_type_rationale=sa.bindparam("page_type_rationale"),
                was_rendered=sa.bindparam("was_rendered"),
                render_attempted=sa.bindparam("render_attempted"),
                fetch_mode_used=sa.bindparam("fetch_mode_used"),
                js_heavy_like=sa.bindparam("js_heavy_like"),
                render_reason=sa.bindparam("render_reason"),
                render_error_message=sa.bindparam("render_error_message"),
            ),
            updates,
        )


def _restore_extraction_duplicates(bind) -> None:
    extractions = sa.table(
        "site_competitor_page_extractions",
        sa.column("id", sa.Integer()),
        sa.column("schema_version", sa.String()),
        sa.column("semantic_card_json", sa.JSON()),
        sa.column("chunk_summary_json", sa.JSON()),
        sa.column("secondary_topics_json", sa.JSON()),
        sa.column("entities_json", sa.JSON()),
        sa.column("raw_json", sa.JSON()),
    )
    rows = bind.execute(
        sa.select(
            extractions.c.id,
            extractions.c.schema_version,
            extractions.c.semantic_card_json,
            extractions.c.chunk_summary_json,
        )
    ).mappings()

    updates: list[dict[str, object]] = []
    for row in rows:
        semantic_card = _json_dict(row["semantic_card_json"])
        chunk_summary = row["chunk_summary_json"]
        updates.append(
            {
                "row_id": int(row["id"]),
                "secondary_topics_json": _json_list(semantic_card.get("supporting_subtopics")),
                "entities_json": _json_list(semantic_card.get("entities")),
                "raw_json": {
                    "schema_version": _optional_str(row["schema_version"]),
                    "semantic_card": semantic_card,
                    "chunk_summary": chunk_summary,
                },
            }
        )
    if updates:
        bind.execute(
            extractions.update()
            .where(extractions.c.id == sa.bindparam("row_id"))
            .values(
                secondary_topics_json=sa.bindparam("secondary_topics_json"),
                entities_json=sa.bindparam("entities_json"),
                raw_json=sa.bindparam("raw_json"),
            ),
            updates,
        )


def _restore_candidate_term_columns(bind) -> None:
    candidates = sa.table(
        "site_competitor_semantic_candidates",
        sa.column("id", sa.Integer()),
        sa.column("normalized_terms_json", sa.JSON()),
        sa.column("primary_tokens_json", sa.JSON()),
        sa.column("secondary_tokens_json", sa.JSON()),
        sa.column("match_terms_json", sa.JSON()),
    )
    rows = bind.execute(
        sa.select(
            candidates.c.id,
            candidates.c.normalized_terms_json,
        )
    ).mappings()

    updates: list[dict[str, object]] = []
    for row in rows:
        terms = _normalize_terms(row["normalized_terms_json"])
        primary_terms = terms[:4]
        secondary_terms = terms[4:10]
        updates.append(
            {
                "row_id": int(row["id"]),
                "primary_tokens_json": primary_terms,
                "secondary_tokens_json": secondary_terms,
                "match_terms_json": terms,
            }
        )
    if updates:
        bind.execute(
            candidates.update()
            .where(candidates.c.id == sa.bindparam("row_id"))
            .values(
                primary_tokens_json=sa.bindparam("primary_tokens_json"),
                secondary_tokens_json=sa.bindparam("secondary_tokens_json"),
                match_terms_json=sa.bindparam("match_terms_json"),
            ),
            updates,
        )


def _restore_semantic_run_summary_ids(bind) -> None:
    runs = sa.table(
        "site_competitor_semantic_runs",
        sa.column("id", sa.Integer()),
        sa.column("source_candidate_ids_json", sa.JSON()),
        sa.column("summary_json", sa.JSON()),
    )
    rows = bind.execute(
        sa.select(
            runs.c.id,
            runs.c.source_candidate_ids_json,
            runs.c.summary_json,
        )
    ).mappings()

    updates: list[dict[str, object]] = []
    for row in rows:
        summary = _json_dict(row["summary_json"])
        summary["source_candidate_ids"] = _json_int_list(row["source_candidate_ids_json"])
        updates.append(
            {
                "row_id": int(row["id"]),
                "summary_json": summary,
            }
        )
    if updates:
        bind.execute(
            runs.update()
            .where(runs.c.id == sa.bindparam("row_id"))
            .values(summary_json=sa.bindparam("summary_json")),
            updates,
        )


def _json_dict(value) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _json_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [value.strip()]
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return []


def _json_int_list(value) -> list[int]:
    items = _json_list(value)
    result: list[int] = []
    for item in items:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _normalize_terms(value) -> list[str]:
    return _dedupe_preserve_order(
        str(item).strip().lower().replace(" ", "-")
        for item in _json_list(value)
        if str(item).strip()
    )


def _dedupe_preserve_order(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _collapse_whitespace(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _optional_str(value) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None
