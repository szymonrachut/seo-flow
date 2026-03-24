from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings


def test_competitive_gap_cluster_state_migration_creates_cache_table(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "competitive-gap-cluster-state.sqlite3"
    database_url = f"sqlite+pysqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(alembic_config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    cluster_state_columns = {
        column["name"]
        for column in inspector.get_columns("site_competitive_gap_cluster_states")
    }

    assert "site_competitive_gap_cluster_states" in table_names
    assert {
        "site_id",
        "active_crawl_id",
        "semantic_cluster_key",
        "cluster_state_hash",
        "coverage_state_hash",
        "cluster_summary_json",
        "coverage_state_json",
    }.issubset(cluster_state_columns)

    engine.dispose()
