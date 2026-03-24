from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.db.models import CrawlJob, CrawlJobStatus, Site, SiteContentGapCandidate
from app.services import content_gap_candidate_service, competitive_gap_sync_service
from app.services.competitive_gap_extraction_service import CompetitorExtractionResult
from app.services.competitive_gap_semantic_card_service import build_semantic_card
from tests.test_competitor_sync_service import (
    FIXED_TIME,
    _make_document,
    _seed_sync_site,
)


def _seed_site_with_two_crawls(sqlite_session_factory) -> dict[str, int]:
    with sqlite_session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com", created_at=FIXED_TIME)
        session.add(site)
        session.flush()

        crawl_a = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=FIXED_TIME,
            started_at=FIXED_TIME,
            finished_at=FIXED_TIME,
            settings_json={"start_url": "https://example.com"},
            stats_json={},
        )
        crawl_b = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=FIXED_TIME + timedelta(days=1),
            started_at=FIXED_TIME + timedelta(days=1),
            finished_at=FIXED_TIME + timedelta(days=1),
            settings_json={"start_url": "https://example.com"},
            stats_json={},
        )
        session.add_all([crawl_a, crawl_b])
        session.commit()
        return {"site_id": site.id, "crawl_a_id": crawl_a.id, "crawl_b_id": crawl_b.id}


def _candidate_row(
    *,
    candidate_key: str,
    candidate_input_hash: str,
    topic_key: str = "local-seo",
    topic_label: str = "Local SEO",
    gap_type: str = "NEW_TOPIC",
    competitor_ids: list[int] | None = None,
    competitor_page_ids: list[int] | None = None,
    priority_score: int = 74,
) -> dict[str, object]:
    return {
        "candidate_key": candidate_key,
        "candidate_input_hash": candidate_input_hash,
        "normalized_topic_key": topic_key,
        "original_topic_label": topic_label,
        "original_phrase": topic_label,
        "gap_type": gap_type,
        "source_cluster_key": f"cluster:{candidate_key}",
        "source_cluster_hash": f"hash:{candidate_input_hash}",
        "source_competitor_ids_json": competitor_ids or [1, 2],
        "source_competitor_page_ids_json": competitor_page_ids or [11, 12],
        "competitor_count": len(competitor_ids or [1, 2]),
        "own_coverage_hint": "none",
        "deterministic_priority_score": priority_score,
        "rationale_summary": f"Rationale for {topic_label}",
        "signals_json": {
            "competitor_pages": len(competitor_page_ids or [11, 12]),
            "semantic": {
                "source_candidate_ids": [],
                "candidate_source_mode": "legacy",
            },
        },
    }


def _make_extraction_result(
    *,
    topic_label: str,
    topic_key: str,
    confidence: float = 0.82,
) -> CompetitorExtractionResult:
    semantic_card = build_semantic_card(
        primary_topic=topic_label,
        topic_labels=[topic_label],
        core_problem=topic_label,
        dominant_intent="commercial",
        secondary_intents=[],
        page_role="money_page",
        content_format="service_page",
        target_audience=None,
        entities=[],
        geo_scope=None,
        supporting_subtopics=[],
        what_this_page_is_about=topic_label,
        what_this_page_is_not_about="Other topics.",
        commerciality="high",
        evidence_snippets=[topic_label],
        confidence=confidence,
    )
    return CompetitorExtractionResult(
        llm_provider="openai",
        llm_model="gpt-5-mini",
        prompt_version="competitive-gap-competitor-extraction-v2",
        schema_version="competitive_gap_competitor_extraction_v2",
        topic_label=topic_label,
        topic_key=topic_key,
        search_intent="commercial",
        content_format="service_page",
        page_role="money_page",
        evidence_snippets_json=[topic_label],
        confidence=confidence,
        semantic_version=str(semantic_card["semantic_version"]),
        semantic_input_hash=str(semantic_card["semantic_input_hash"]),
        semantic_card_json=semantic_card,
    )


def test_refresh_site_content_gap_candidates_persists_rows_for_basis_crawl(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    rows = [
        _candidate_row(candidate_key="gap-a", candidate_input_hash="hash-a"),
        _candidate_row(candidate_key="gap-b", candidate_input_hash="hash-b", topic_key="seo-audit", topic_label="SEO Audit"),
    ]

    monkeypatch.setattr(
        content_gap_candidate_service,
        "_build_raw_candidate_rows",
        lambda *args, **kwargs: rows,
    )

    with sqlite_session_factory() as session:
        summary = content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            generated_at=FIXED_TIME,
        )
        session.commit()

        persisted = session.scalars(
            select(SiteContentGapCandidate)
            .where(SiteContentGapCandidate.site_id == ids["site_id"])
            .order_by(SiteContentGapCandidate.id.asc())
        ).all()

    assert summary.generated_count == 2
    assert summary.reused_count == 0
    assert all(row.basis_crawl_job_id == ids["crawl_a_id"] for row in persisted)
    assert all(row.current is True for row in persisted)
    assert all(row.status == "active" for row in persisted)


def test_refresh_site_content_gap_candidates_same_hash_reuses_current_revision(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    row = _candidate_row(candidate_key="gap-a", candidate_input_hash="hash-a")

    monkeypatch.setattr(
        content_gap_candidate_service,
        "_build_raw_candidate_rows",
        lambda *args, **kwargs: [row],
    )

    with sqlite_session_factory() as session:
        content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            generated_at=FIXED_TIME,
        )
        session.commit()

    with sqlite_session_factory() as session:
        summary = content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            generated_at=FIXED_TIME + timedelta(hours=1),
        )
        session.commit()

        rows = session.scalars(
            select(SiteContentGapCandidate)
            .where(SiteContentGapCandidate.site_id == ids["site_id"])
            .order_by(SiteContentGapCandidate.id.asc())
        ).all()

    assert summary.generated_count == 0
    assert summary.reused_count == 1
    assert len(rows) == 1
    assert rows[0].current is True
    assert rows[0].status == "active"
    assert rows[0].last_generated_at == (FIXED_TIME + timedelta(hours=1)).replace(tzinfo=None)


def test_refresh_site_content_gap_candidates_hash_change_supersedes_current_revision(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    initial_row = _candidate_row(candidate_key="gap-a", candidate_input_hash="hash-a")
    changed_row = _candidate_row(candidate_key="gap-a", candidate_input_hash="hash-b", priority_score=81)

    monkeypatch.setattr(
        content_gap_candidate_service,
        "_build_raw_candidate_rows",
        lambda *args, **kwargs: [initial_row],
    )
    with sqlite_session_factory() as session:
        content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            generated_at=FIXED_TIME,
        )
        session.commit()

    monkeypatch.setattr(
        content_gap_candidate_service,
        "_build_raw_candidate_rows",
        lambda *args, **kwargs: [changed_row],
    )
    with sqlite_session_factory() as session:
        summary = content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            generated_at=FIXED_TIME + timedelta(hours=2),
        )
        session.commit()

        rows = session.scalars(
            select(SiteContentGapCandidate)
            .where(SiteContentGapCandidate.site_id == ids["site_id"])
            .order_by(SiteContentGapCandidate.id.asc())
        ).all()

    assert summary.generated_count == 1
    assert summary.superseded_count == 1
    assert len(rows) == 2
    assert rows[0].status == "superseded"
    assert rows[0].current is False
    assert rows[1].status == "active"
    assert rows[1].current is True
    assert rows[1].candidate_input_hash == "hash-b"


def test_refresh_site_content_gap_candidates_missing_key_invalidates_previous_current(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    row = _candidate_row(candidate_key="gap-a", candidate_input_hash="hash-a")

    monkeypatch.setattr(
        content_gap_candidate_service,
        "_build_raw_candidate_rows",
        lambda *args, **kwargs: [row],
    )
    with sqlite_session_factory() as session:
        content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            generated_at=FIXED_TIME,
        )
        session.commit()

    monkeypatch.setattr(
        content_gap_candidate_service,
        "_build_raw_candidate_rows",
        lambda *args, **kwargs: [],
    )
    with sqlite_session_factory() as session:
        summary = content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            generated_at=FIXED_TIME + timedelta(hours=3),
        )
        session.commit()

        rows = session.scalars(
            select(SiteContentGapCandidate)
            .where(SiteContentGapCandidate.site_id == ids["site_id"])
            .order_by(SiteContentGapCandidate.id.asc())
        ).all()

    assert summary.invalidated_count == 1
    assert len(rows) == 1
    assert rows[0].status == "invalidated"
    assert rows[0].current is False


def test_refresh_site_content_gap_candidates_keeps_snapshot_boundaries(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_site_with_two_crawls(sqlite_session_factory)
    row = _candidate_row(candidate_key="gap-a", candidate_input_hash="hash-a")

    monkeypatch.setattr(
        content_gap_candidate_service,
        "_build_raw_candidate_rows",
        lambda *args, **kwargs: [row],
    )

    with sqlite_session_factory() as session:
        content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            ids["site_id"],
            basis_crawl_job_id=ids["crawl_a_id"],
            generated_at=FIXED_TIME,
        )
        content_gap_candidate_service.refresh_site_content_gap_candidates(
            session,
            ids["site_id"],
            basis_crawl_job_id=ids["crawl_b_id"],
            generated_at=FIXED_TIME + timedelta(days=1),
        )
        session.commit()

        crawl_a_rows = session.scalars(
            select(SiteContentGapCandidate)
            .where(SiteContentGapCandidate.basis_crawl_job_id == ids["crawl_a_id"])
            .order_by(SiteContentGapCandidate.id.asc())
        ).all()
        crawl_b_rows = session.scalars(
            select(SiteContentGapCandidate)
            .where(SiteContentGapCandidate.basis_crawl_job_id == ids["crawl_b_id"])
            .order_by(SiteContentGapCandidate.id.asc())
        ).all()

    assert len(crawl_a_rows) == 1
    assert len(crawl_b_rows) == 1
    assert crawl_a_rows[0].basis_crawl_job_id != crawl_b_rows[0].basis_crawl_job_id
    assert crawl_a_rows[0].current is True
    assert crawl_b_rows[0].current is True


def test_run_site_competitor_sync_persists_raw_content_gap_candidates(sqlite_session_factory) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    html_map = {
        "https://competitor-sync.com/": _make_document(
            "https://competitor-sync.com/",
            """
            <html><body>
              <h1>Competitor Sync</h1>
              <p>SEO consultancy homepage.</p>
              <a href="/local-seo">Local SEO</a>
              <a href="/seo-audit-faq">SEO Audit FAQ</a>
            </body></html>
            """,
        ),
        "https://competitor-sync.com/local-seo": _make_document(
            "https://competitor-sync.com/local-seo",
            """
            <html><head><title>Local SEO services</title></head><body>
              <h1>Local SEO services</h1>
              <p>Local SEO services for growing businesses and Google Business Profile support.</p>
            </body></html>
            """,
        ),
        "https://competitor-sync.com/seo-audit-faq": _make_document(
            "https://competitor-sync.com/seo-audit-faq",
            """
            <html><head><title>SEO Audit FAQ</title></head><body>
              <h1>SEO Audit FAQ</h1>
              <p>Frequently asked questions about SEO audits and technical reviews.</p>
            </body></html>
            """,
        ),
    }

    def fake_fetch(url: str):
        return html_map.get(url)

    def fake_extract(page):
        if page.normalized_url.endswith("/local-seo"):
            return _make_extraction_result(topic_label="Local SEO", topic_key="local-seo", confidence=0.86)
        return _make_extraction_result(topic_label="SEO Audit", topic_key="seo-audit", confidence=0.82)

    with sqlite_session_factory() as session:
        result = competitive_gap_sync_service.run_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
            fetch_document=fake_fetch,
            extract_competitor_page=fake_extract,
        )
        session.commit()

        candidates = session.scalars(
            select(SiteContentGapCandidate)
            .where(SiteContentGapCandidate.site_id == ids["site_id"])
            .order_by(SiteContentGapCandidate.id.asc())
        ).all()

    assert result.content_gap_candidates_generated >= 1
    assert candidates
    assert all(candidate.basis_crawl_job_id == ids["crawl_job_id"] for candidate in candidates)
    assert all(candidate.current is True for candidate in candidates)
