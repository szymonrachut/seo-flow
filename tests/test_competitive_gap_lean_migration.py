from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


FIXED_TIME = datetime(2026, 3, 19, 12, 0, tzinfo=timezone.utc)


def test_competitive_gap_lean_migration_backfills_and_drops_legacy_columns(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "competitive-gap-lean.sqlite3"
    database_url = f"sqlite+pysqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(alembic_config, "0016_competitive_gap_quality_v1")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO sites (id, root_url, domain, created_at)
                VALUES (1, :root_url, :domain, :created_at)
                """
            ),
            {
                "root_url": "https://example.com",
                "domain": "example.com",
                "created_at": FIXED_TIME,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO crawl_jobs (
                    id, site_id, status, started_at, finished_at, created_at, settings_json, stats_json
                ) VALUES (
                    1, 1, 'finished', :started_at, :finished_at, :created_at, :settings_json, :stats_json
                )
                """
            ),
            {
                "started_at": FIXED_TIME,
                "finished_at": FIXED_TIME,
                "created_at": FIXED_TIME,
                "settings_json": "{}",
                "stats_json": "{}",
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO site_competitors (
                    id, site_id, label, root_url, domain, is_active, last_sync_run_id, last_sync_status,
                    last_sync_stage, last_sync_processed_urls, last_sync_url_limit,
                    last_sync_processed_extraction_pages, last_sync_total_extractable_pages,
                    last_sync_summary_json, created_at, updated_at
                ) VALUES (
                    1, 1, 'Competitor', :root_url, :domain, 1, 0, 'idle', 'idle', 0, 400, 0, 0, '{}',
                    :created_at, :updated_at
                )
                """
            ),
            {
                "root_url": "https://competitor.com",
                "domain": "competitor.com",
                "created_at": FIXED_TIME,
                "updated_at": FIXED_TIME,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO site_competitor_pages (
                    id, site_id, competitor_id, url, normalized_url, final_url, status_code, title,
                    meta_description, h1, canonical_url, content_type, word_count, content_text_hash,
                    visible_text, visible_text_chars, visible_text_truncated, schema_present, schema_count,
                    schema_types_json, page_type, page_bucket, page_type_confidence, page_type_version,
                    page_type_rationale, was_rendered, render_attempted, fetch_mode_used, js_heavy_like,
                    render_reason, render_error_message, fetched_at, created_at, updated_at,
                    robots_meta, x_robots_tag, semantic_eligible, semantic_exclusion_reason,
                    semantic_input_hash, semantic_last_evaluated_at
                ) VALUES (
                    1, 1, 1, :url, :normalized_url, :final_url, 200, 'Local SEO Services',
                    'Local SEO meta', 'Local SEO Services', :canonical_url, 'text/html', 240, 'content-hash',
                    :visible_text, 31, 1, 1, 1, :schema_types_json, 'service', 'commercial', 0.91,
                    '11.1-v1', 'seed rationale', 1, 1, 'rendered', 1, 'js detected', 'render warning',
                    :fetched_at, :created_at, :updated_at, 'index,follow', 'noarchive', 1, NULL,
                    'semantic-hash', :semantic_last_evaluated_at
                )
                """
            ),
            {
                "url": "https://competitor.com/local-seo",
                "normalized_url": "https://competitor.com/local-seo",
                "final_url": "https://competitor.com/local-seo",
                "canonical_url": "https://competitor.com/local-seo",
                "visible_text": "Local SEO services for growing businesses.",
                "schema_types_json": json.dumps(["Service"]),
                "fetched_at": FIXED_TIME,
                "created_at": FIXED_TIME,
                "updated_at": FIXED_TIME,
                "semantic_last_evaluated_at": FIXED_TIME,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO site_competitor_page_extractions (
                    id, site_id, competitor_id, competitor_page_id, content_hash_at_extraction, llm_provider,
                    llm_model, prompt_version, schema_version, topic_label, topic_key, search_intent,
                    content_format, page_role, secondary_topics_json, entities_json, evidence_snippets_json,
                    confidence, raw_json, extracted_at, semantic_version, semantic_input_hash,
                    semantic_card_json, chunk_summary_json
                ) VALUES (
                    1, 1, 1, 1, 'content-hash', 'openai', 'gpt-5-mini', 'prompt-v1',
                    'competitive_gap_competitor_extraction_v2', 'Local SEO', 'local-seo', 'commercial',
                    'service_page', 'money_page', :secondary_topics_json, :entities_json,
                    :evidence_snippets_json, 0.84, :raw_json, :extracted_at,
                    'competitive-gap-semantic-card-v1', 'semantic-hash', :semantic_card_json,
                    :chunk_summary_json
                )
                """
            ),
            {
                "secondary_topics_json": json.dumps(["google business profile"]),
                "entities_json": json.dumps(["Google Business Profile"]),
                "evidence_snippets_json": json.dumps(["Local SEO services for growing businesses."]),
                "raw_json": json.dumps({"topic_label": "Local SEO"}),
                "extracted_at": FIXED_TIME,
                "semantic_card_json": json.dumps(
                    {
                        "primary_topic": "Local SEO",
                        "topic_labels": ["Local SEO"],
                        "core_problem": "Local SEO",
                        "dominant_intent": "commercial",
                        "secondary_intents": [],
                        "page_role": "money_page",
                        "content_format": "service_page",
                        "target_audience": None,
                        "entities": ["Google Business Profile"],
                        "geo_scope": None,
                        "supporting_subtopics": ["google business profile"],
                        "what_this_page_is_about": "Local SEO",
                        "what_this_page_is_not_about": "Not another topic.",
                        "commerciality": "high",
                        "evidence_snippets": ["Local SEO services for growing businesses."],
                        "confidence": 0.84,
                        "semantic_version": "competitive-gap-semantic-card-v1",
                        "semantic_input_hash": "semantic-hash",
                    }
                ),
                "chunk_summary_json": json.dumps({"chunk_count": 0, "chunk_cards": []}),
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO site_competitor_semantic_candidates (
                    id, site_id, competitor_id, competitor_page_id, semantic_input_hash, raw_topic_key,
                    raw_topic_label, primary_tokens_json, secondary_tokens_json, match_terms_json,
                    page_type, page_bucket, quality_score, current, created_at, updated_at
                ) VALUES (
                    1, 1, 1, 1, 'semantic-hash', 'local-seo', 'Local SEO',
                    :primary_tokens_json, :secondary_tokens_json, :match_terms_json,
                    'service', 'commercial', 92, 1, :created_at, :updated_at
                )
                """
            ),
            {
                "primary_tokens_json": json.dumps(["local", "seo"]),
                "secondary_tokens_json": json.dumps(["google-business-profile"]),
                "match_terms_json": json.dumps(["local", "seo", "google-business-profile"]),
                "created_at": FIXED_TIME,
                "updated_at": FIXED_TIME,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO site_competitor_semantic_runs (
                    id, site_id, competitor_id, run_id, status, stage, trigger_source, mode, active_crawl_id,
                    started_at, finished_at, last_heartbeat_at, lease_expires_at, llm_provider, llm_model,
                    prompt_version, source_candidate_ids_json, summary_json, created_at, updated_at
                ) VALUES (
                    1, 1, 1, 1, 'completed', 'completed', 'manual_full', 'full', 1,
                    :started_at, :finished_at, :last_heartbeat_at, :lease_expires_at, 'openai', 'gpt-5-mini',
                    'competitive-gap-semantic-arbiter-v1', :source_candidate_ids_json, :summary_json,
                    :created_at, :updated_at
                )
                """
            ),
            {
                "started_at": FIXED_TIME,
                "finished_at": FIXED_TIME,
                "last_heartbeat_at": FIXED_TIME,
                "lease_expires_at": FIXED_TIME,
                "source_candidate_ids_json": json.dumps([1]),
                "summary_json": json.dumps(
                    {
                        "semantic_candidates_count": 1,
                        "semantic_llm_jobs_count": 1,
                        "semantic_resolved_count": 1,
                        "semantic_cache_hits": 0,
                        "semantic_fallback_count": 0,
                        "merge_pairs_count": 1,
                        "own_match_pairs_count": 1,
                        "source_candidate_ids": [1],
                    }
                ),
                "created_at": FIXED_TIME,
                "updated_at": FIXED_TIME,
            },
        )

    engine.dispose()
    command.upgrade(alembic_config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    page_columns = {column["name"] for column in inspector.get_columns("site_competitor_pages")}
    extraction_columns = {column["name"] for column in inspector.get_columns("site_competitor_page_extractions")}
    candidate_columns = {column["name"] for column in inspector.get_columns("site_competitor_semantic_candidates")}

    assert "fetch_diagnostics_json" in page_columns
    assert "robots_meta" not in page_columns
    assert "visible_text_chars" not in page_columns
    assert "schema_types_json" not in page_columns
    assert "page_type_rationale" not in page_columns

    assert "secondary_topics_json" not in extraction_columns
    assert "entities_json" not in extraction_columns
    assert "raw_json" not in extraction_columns

    assert "normalized_terms_json" in candidate_columns
    assert "primary_tokens_json" not in candidate_columns
    assert "match_terms_json" not in candidate_columns

    with engine.begin() as connection:
        page_row = connection.execute(
            text(
                """
                SELECT fetch_diagnostics_json
                FROM site_competitor_pages
                WHERE id = 1
                """
            )
        ).scalar_one()
        extraction_row = connection.execute(
            text(
                """
                SELECT semantic_card_json, chunk_summary_json
                FROM site_competitor_page_extractions
                WHERE id = 1
                """
            )
        ).mappings().one()
        candidate_row = connection.execute(
            text(
                """
                SELECT normalized_terms_json
                FROM site_competitor_semantic_candidates
                WHERE id = 1
                """
            )
        ).scalar_one()
        run_row = connection.execute(
            text(
                """
                SELECT summary_json
                FROM site_competitor_semantic_runs
                WHERE id = 1
                """
            )
        ).scalar_one()

    diagnostics = _json_value(page_row)
    semantic_card = _json_value(extraction_row["semantic_card_json"])
    chunk_summary = _json_value(extraction_row["chunk_summary_json"])
    normalized_terms = _json_value(candidate_row)
    summary = _json_value(run_row)

    assert diagnostics["robots_meta"] == "index,follow"
    assert diagnostics["x_robots_tag"] == "noarchive"
    assert diagnostics["schema_types"] == ["Service"]
    assert diagnostics["visible_text_truncated"] is True
    assert diagnostics["fetch_mode_used"] == "rendered"
    assert diagnostics["render_reason"] == "js detected"

    assert semantic_card["primary_topic"] == "Local SEO"
    assert chunk_summary is None
    assert normalized_terms == ["local", "seo", "google-business-profile"]
    assert "source_candidate_ids" not in summary
    assert summary["semantic_candidates_count"] == 1

    engine.dispose()
    get_settings.cache_clear()


def _json_value(value):
    if isinstance(value, str):
        return json.loads(value)
    return value
