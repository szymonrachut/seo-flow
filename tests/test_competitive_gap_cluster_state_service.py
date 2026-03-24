from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db.models import SiteCompetitiveGapClusterState, SiteCompetitorPage
from app.services import competitive_gap_cluster_state_service, competitive_gap_semantic_service, competitive_gap_service
from tests.competitive_gap_test_utils import seed_competitive_gap_site


def _prepare_semantic_read_model(sqlite_session_factory) -> dict[str, int]:
    ids = seed_competitive_gap_site(sqlite_session_factory)
    with sqlite_session_factory() as session:
        for competitor_id in [ids["competitor_a_id"], ids["competitor_b_id"]]:
            pages = session.scalars(
                select(SiteCompetitorPage)
                .where(SiteCompetitorPage.competitor_id == competitor_id)
                .order_by(SiteCompetitorPage.id.asc())
            ).all()
            for page in pages:
                page.status_code = 200
                page.visible_text = ((page.visible_text or page.title or page.h1 or "seo topic") + " ") * 12
            page_ids = [page.id for page in pages]
            competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
                session,
                ids["site_id"],
                competitor_id,
                page_ids=page_ids,
            )
        session.commit()
    return ids


def test_semantic_read_model_persists_and_reuses_cluster_state_cache(sqlite_session_factory, monkeypatch) -> None:
    ids = _prepare_semantic_read_model(sqlite_session_factory)

    with sqlite_session_factory() as session:
        first_payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            gsc_date_range="last_28_days",
            page=1,
            page_size=50,
        )
        session.commit()
        cluster_states = session.scalars(
            select(SiteCompetitiveGapClusterState)
            .where(SiteCompetitiveGapClusterState.site_id == ids["site_id"])
            .order_by(SiteCompetitiveGapClusterState.id.asc())
        ).all()
        assert cluster_states
        assert all(row.coverage_state_json for row in cluster_states)

    monkeypatch.setattr(
        competitive_gap_service,
        "_resolve_cluster_coverage",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("coverage should come from cache")),
    )

    with sqlite_session_factory() as session:
        second_payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            gsc_date_range="last_28_days",
            page=1,
            page_size=50,
        )

    assert second_payload["items"]
    assert [row["gap_key"] for row in second_payload["items"]] == [
        row["gap_key"] for row in first_payload["items"]
    ]


def test_semantic_read_model_loads_cluster_state_cache_in_single_batch(sqlite_session_factory, monkeypatch) -> None:
    ids = _prepare_semantic_read_model(sqlite_session_factory)
    load_calls: list[list[str]] = []
    original_loader = competitive_gap_service.competitive_gap_cluster_state_service.load_cluster_state_map

    def spy_load_cluster_state_map(*args, **kwargs):
        load_calls.append(list(kwargs.get("semantic_cluster_keys") or []))
        return original_loader(*args, **kwargs)

    monkeypatch.setattr(
        competitive_gap_service.competitive_gap_cluster_state_service,
        "load_cluster_state_map",
        spy_load_cluster_state_map,
    )

    with sqlite_session_factory() as session:
        payload = competitive_gap_service.build_competitive_gap_payload(
            session,
            ids["site_id"],
            gsc_date_range="last_28_days",
            page=1,
            page_size=50,
        )

    assert payload["items"]
    assert len(load_calls) == 1
    assert len(load_calls[0]) >= 2


def test_cluster_state_scope_uses_postgres_safe_equality_for_non_null_active_crawl_id() -> None:
    statement = select(SiteCompetitiveGapClusterState).where(
        *competitive_gap_cluster_state_service._cluster_state_scope_predicates(
            site_id=2,
            active_crawl_id=7,
        ),
        SiteCompetitiveGapClusterState.semantic_cluster_key.in_(["sg:test"]),
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "active_crawl_id =" in compiled
    assert "active_crawl_id IS " not in compiled


def test_cluster_state_scope_uses_is_null_when_active_crawl_id_missing() -> None:
    statement = select(SiteCompetitiveGapClusterState).where(
        *competitive_gap_cluster_state_service._cluster_state_scope_predicates(
            site_id=2,
            active_crawl_id=None,
        ),
        SiteCompetitiveGapClusterState.semantic_cluster_key.in_(["sg:test"]),
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "active_crawl_id IS NULL" in compiled
