from __future__ import annotations

from datetime import timedelta, timezone

from sqlalchemy import select

from app.crawler.extraction.page_extractor import ExtractedPageData
from app.db.models import (
    CrawlJob,
    CrawlJobStatus,
    Page,
    Site,
    SiteCompetitor,
    SiteCompetitorPageExtraction,
    SiteCompetitorSemanticCandidate,
    SiteCompetitorSyncRun,
)
from app.services import competitive_gap_sync_run_service, competitive_gap_sync_service
from app.services.competitive_gap_extraction_service import CompetitorExtractionResult
from app.services.competitive_gap_semantic_card_service import build_semantic_card


FIXED_TIME = competitive_gap_sync_service.utcnow().replace(year=2026, month=3, day=16, hour=12, minute=0, second=0, microsecond=0)


def _make_extraction_result(
    *,
    topic_label: str,
    topic_key: str,
    search_intent: str,
    content_format: str,
    page_role: str,
    secondary_topics: list[str] | None = None,
    entities: list[str] | None = None,
    evidence_snippets: list[str] | None = None,
    confidence: float = 0.8,
) -> CompetitorExtractionResult:
    semantic_card = build_semantic_card(
        primary_topic=topic_label,
        topic_labels=[topic_label],
        core_problem=topic_label,
        dominant_intent=search_intent,
        secondary_intents=[],
        page_role=page_role,
        content_format=content_format,
        target_audience=None,
        entities=entities or [],
        geo_scope=None,
        supporting_subtopics=secondary_topics or [],
        what_this_page_is_about=topic_label,
        what_this_page_is_not_about="Not another topic.",
        commerciality="high" if search_intent == "commercial" else "low",
        evidence_snippets=evidence_snippets or [topic_label],
        confidence=confidence,
    )
    return CompetitorExtractionResult(
        llm_provider="openai",
        llm_model="gpt-5-mini",
        prompt_version="competitive-gap-competitor-extraction-v2",
        schema_version="competitive_gap_competitor_extraction_v2",
        topic_label=topic_label,
        topic_key=topic_key,
        search_intent=search_intent,
        content_format=content_format,
        page_role=page_role,
        evidence_snippets_json=evidence_snippets or [topic_label],
        confidence=confidence,
        semantic_version=str(semantic_card.get("semantic_version") or "competitive-gap-semantic-card-v1"),
        semantic_input_hash=str(semantic_card.get("semantic_input_hash") or f"{topic_key}-hash"),
        semantic_card_json=semantic_card,
    )


def _seed_sync_site(session_factory) -> dict[str, int]:
    with session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com", created_at=FIXED_TIME)
        session.add(site)
        session.flush()

        crawl_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            created_at=FIXED_TIME,
            started_at=FIXED_TIME,
            finished_at=FIXED_TIME,
            settings_json={"start_url": "https://example.com"},
            stats_json={},
        )
        session.add(crawl_job)
        session.flush()

        own_page = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/seo-audit",
            normalized_url="https://example.com/seo-audit",
            final_url="https://example.com/seo-audit",
            status_code=200,
            title="SEO Audit",
            meta_description="SEO audit services",
            h1="SEO Audit",
            canonical_url="https://example.com/seo-audit",
            content_type="text/html",
            word_count=420,
            schema_present=True,
            schema_count=1,
            schema_types_json=["Service"],
            page_type="service",
            page_bucket="commercial",
            page_type_confidence=0.92,
            page_type_version="11.1-v1",
            page_type_rationale="seed",
            is_internal=True,
            depth=1,
            fetched_at=FIXED_TIME,
            created_at=FIXED_TIME,
        )
        session.add(own_page)
        session.flush()

        competitor = SiteCompetitor(
            site_id=site.id,
            label="Competitor Sync",
            root_url="https://competitor-sync.com",
            domain="competitor-sync.com",
            is_active=True,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        session.add(competitor)
        session.commit()

        return {
            "site_id": site.id,
            "competitor_id": competitor.id,
            "crawl_job_id": crawl_job.id,
        }


def _attach_sync_run(
    session,
    *,
    site_id: int,
    competitor_id: int,
    run_id: int,
    status: str,
    stage: str,
    trigger_source: str = "manual_single",
    error_code: str | None = None,
    error_message_safe: str | None = None,
) -> SiteCompetitorSyncRun:
    current_time = competitive_gap_sync_service.utcnow()
    run = SiteCompetitorSyncRun(
        site_id=site_id,
        competitor_id=competitor_id,
        run_id=run_id,
        status=status,
        stage=stage,
        trigger_source=trigger_source,
        started_at=current_time if status != "queued" else None,
        finished_at=current_time if status in {"done", "failed", "stale", "cancelled"} else None,
        last_heartbeat_at=current_time,
        lease_expires_at=current_time + timedelta(seconds=competitive_gap_sync_run_service.DEFAULT_SYNC_LEASE_SECONDS),
        error_code=error_code,
        error_message_safe=error_message_safe,
        summary_json=competitive_gap_sync_service.site_competitor_service.build_empty_sync_summary_payload(),
        retry_of_run_id=None,
        processed_urls=0,
        url_limit=competitive_gap_sync_service.COMPETITOR_SYNC_MAX_URLS,
        processed_extraction_pages=0,
        total_extractable_pages=0,
        created_at=current_time,
        updated_at=current_time,
    )
    session.add(run)
    return run


def _make_document(url: str, html: str) -> competitive_gap_sync_service.FetchedCompetitorDocument:
    return competitive_gap_sync_service.FetchedCompetitorDocument(
        requested_url=url,
        final_url=url,
        normalized_url=url,
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        body=html.encode("utf-8"),
        fetched_at=FIXED_TIME,
        response_time_ms=120,
    )


def _make_extracted_page_data(
    *,
    title: str | None,
    meta_description: str | None,
    h1: str | None,
    canonical_url: str | None,
    word_count: int | None,
    content_text_hash: str | None,
    visible_text: str,
    schema_present: bool = False,
    schema_count: int = 0,
    schema_types_json: list[str] | None = None,
    robots_meta: str | None = None,
    x_robots_tag: str | None = None,
) -> ExtractedPageData:
    return ExtractedPageData(
        title=title,
        title_length=len(title) if title else None,
        meta_description=meta_description,
        meta_description_length=len(meta_description) if meta_description else None,
        h1=h1,
        h1_count=1 if h1 else 0,
        h2_count=0,
        canonical_url=canonical_url,
        robots_meta=robots_meta,
        x_robots_tag=x_robots_tag,
        word_count=word_count,
        content_text_hash=content_text_hash,
        visible_text=visible_text,
        images_count=0,
        images_missing_alt_count=0,
        schema_present=schema_present,
        schema_count=schema_count,
        schema_types_json=schema_types_json or [],
        links=[],
    )


def test_run_site_competitor_sync_persists_pages_and_skips_unchanged_extractions(sqlite_session_factory) -> None:
    ids = _seed_sync_site(sqlite_session_factory)
    extraction_calls: list[str] = []

    html_map = {
        "https://competitor-sync.com/": _make_document(
            "https://competitor-sync.com/",
            """
            <html><body>
              <h1>Competitor Sync</h1>
              <p>SEO consultancy homepage.</p>
              <a href="/local-seo">Local SEO</a>
              <a href="/seo-audit-faq">SEO Audit FAQ</a>
              <a href="/login">Login</a>
              <a href="/products?color=red">Filter</a>
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
        extraction_calls.append(page.normalized_url)
        if page.normalized_url.endswith("/local-seo"):
            return _make_extraction_result(
                topic_label="Local SEO",
                topic_key="local-seo",
                search_intent="commercial",
                content_format="service_page",
                page_role="money_page",
                secondary_topics=["google business profile"],
                entities=["Google Business Profile"],
                evidence_snippets=["Local SEO services for growing businesses and Google Business Profile support."],
                confidence=0.86,
            )
        return _make_extraction_result(
            topic_label="SEO Audit",
            topic_key="seo-audit",
            search_intent="informational",
            content_format="faq",
            page_role="supporting_page",
            entities=["SEO audit"],
            evidence_snippets=["Frequently asked questions about SEO audits and technical reviews."],
            confidence=0.82,
        )

    with sqlite_session_factory() as session:
        first_result = competitive_gap_sync_service.run_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
            fetch_document=fake_fetch,
            extract_competitor_page=fake_extract,
        )
        session.commit()

        assert first_result.pages_saved == 3
        assert first_result.extraction_created == 2
        assert first_result.extraction_skipped == 1
        assert first_result.extraction_failed == 0
        assert first_result.summary_payload["visited_urls_count"] >= 3
        assert first_result.summary_payload["stored_pages_count"] == 3
        assert first_result.summary_payload["extracted_pages_count"] == 2
        assert first_result.summary_payload["skipped_urls_count"] >= 2
        assert first_result.summary_payload["skipped_filtered_count"] >= 2
        assert first_result.summary_payload["skipped_low_value_count"] == 1

    with sqlite_session_factory() as session:
        second_result = competitive_gap_sync_service.run_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
            fetch_document=fake_fetch,
            extract_competitor_page=fake_extract,
        )
        session.commit()

        assert second_result.pages_saved == 3
        assert second_result.extraction_created == 0
        assert second_result.extraction_skipped == 3
        assert second_result.extraction_failed == 0
        assert second_result.summary_payload["extraction_skipped_unchanged_count"] == 2
        assert second_result.summary_payload["skipped_low_value_count"] == 1

        extractions = session.scalars(
            select(SiteCompetitorPageExtraction)
            .where(SiteCompetitorPageExtraction.competitor_id == ids["competitor_id"])
            .order_by(SiteCompetitorPageExtraction.id.asc())
        ).all()
        assert len(extractions) == 2
        assert extraction_calls.count("https://competitor-sync.com/local-seo") == 1
        assert extraction_calls.count("https://competitor-sync.com/seo-audit-faq") == 1


def test_run_site_competitor_sync_populates_semantic_foundation_without_affecting_extractions(
    sqlite_session_factory,
) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    html_map = {
        "https://competitor-sync.com/": _make_document(
            "https://competitor-sync.com/",
            """
            <html><body>
              <h1>Competitor Sync</h1>
              <p>SEO consultancy homepage with technical SEO, local SEO, audits, content strategy,
              internal linking, topical authority planning, competitor research, and recurring support
              for in-house marketing teams across healthcare, e-commerce, SaaS, and multi-location brands.</p>
              <p>Our consultants plan growth roadmaps, uncover content gaps, improve information architecture,
              and create service pages, hub pages, FAQs, and supporting blog articles that answer the full
              customer journey from discovery to conversion.</p>
              <a href="/local-seo">Local SEO</a>
              <a href="/contact">Contact</a>
            </body></html>
            """,
        ),
        "https://competitor-sync.com/local-seo": _make_document(
            "https://competitor-sync.com/local-seo",
            """
            <html><head><title>Local SEO services</title></head><body>
              <h1>Local SEO services</h1>
              <p>Local SEO services for growing businesses and multi-location brands include Google Business
              Profile optimization, location landing pages, review acquisition, local citations, internal
              linking, local content planning, and conversion-focused updates for service pages.</p>
              <p>We help brands improve local rankings, strengthen map pack visibility, document location
              specific proof points, align service intent with city-level demand, and create supporting
              FAQ content that answers trust, pricing, process, and implementation questions.</p>
            </body></html>
            """,
        ),
        "https://competitor-sync.com/contact": _make_document(
            "https://competitor-sync.com/contact",
            """
            <html><head><title>Contact</title></head><body>
              <h1>Contact</h1>
              <p>Call our SEO consultancy team.</p>
            </body></html>
            """,
        ),
    }

    def fake_fetch(url: str):
        return html_map.get(url)

    def fake_extract(page):
        topic_label = "Local SEO" if page.normalized_url.endswith("/local-seo") else "Contact"
        topic_key = "local-seo" if page.normalized_url.endswith("/local-seo") else "contact"
        return _make_extraction_result(
            topic_label=topic_label,
            topic_key=topic_key,
            search_intent="commercial" if topic_key == "local-seo" else "navigational",
            content_format="service_page" if topic_key == "local-seo" else "contact",
            page_role="money_page" if topic_key == "local-seo" else "trust_page",
            evidence_snippets=[topic_label],
            confidence=0.8,
        )

    with sqlite_session_factory() as session:
        result = competitive_gap_sync_service.run_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
            fetch_document=fake_fetch,
            extract_competitor_page=fake_extract,
        )
        session.commit()

        assert result.pages_saved == 3
        assert result.extraction_created == 1
        assert result.extraction_skipped == 2

        pages = session.scalars(
            select(competitive_gap_sync_service.SiteCompetitorPage)
            .where(competitive_gap_sync_service.SiteCompetitorPage.competitor_id == ids["competitor_id"])
            .order_by(competitive_gap_sync_service.SiteCompetitorPage.id.asc())
        ).all()
        by_url = {page.normalized_url: page for page in pages}
        assert by_url["https://competitor-sync.com/local-seo"].semantic_eligible is True
        assert by_url["https://competitor-sync.com/local-seo"].semantic_exclusion_reason is None
        assert by_url["https://competitor-sync.com/contact"].semantic_eligible is False
        assert by_url["https://competitor-sync.com/contact"].semantic_exclusion_reason == "contact"
        assert by_url["https://competitor-sync.com/"].semantic_eligible is False
        assert by_url["https://competitor-sync.com/"].semantic_exclusion_reason == "weak_low_strength"

        semantic_candidates = session.scalars(
            select(SiteCompetitorSemanticCandidate)
            .where(SiteCompetitorSemanticCandidate.competitor_id == ids["competitor_id"])
            .order_by(SiteCompetitorSemanticCandidate.id.asc())
        ).all()
        current_candidates = [candidate for candidate in semantic_candidates if candidate.current]
        assert current_candidates
        assert {
            candidate.competitor_page_id
            for candidate in current_candidates
        } == {
            by_url["https://competitor-sync.com/local-seo"].id,
        }


def test_run_site_competitor_sync_skips_noindex_pages_before_persistence(sqlite_session_factory) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    html_map = {
        "https://competitor-sync.com/": _make_document(
            "https://competitor-sync.com/",
            """
            <html><body>
              <h1>Competitor Sync</h1>
              <a href="/noindex-service">Noindex service</a>
              <a href="/local-seo">Local SEO</a>
            </body></html>
            """,
        ),
        "https://competitor-sync.com/noindex-service": _make_document(
            "https://competitor-sync.com/noindex-service",
            """
            <html><head><title>Noindex service</title><meta name="robots" content="noindex,follow"></head><body>
              <h1>Noindex service</h1>
              <p>This page should not be persisted for competitive gap.</p>
            </body></html>
            """,
        ),
        "https://competitor-sync.com/local-seo": _make_document(
            "https://competitor-sync.com/local-seo",
            """
            <html><head><title>Local SEO services</title></head><body>
              <h1>Local SEO services</h1>
              <p>Local SEO services for growing businesses.</p>
            </body></html>
            """,
        ),
    }

    def fake_fetch(url: str):
        return html_map.get(url)

    def fake_extract(page):
        return _make_extraction_result(
            topic_label="Local SEO" if page.normalized_url.endswith("/local-seo") else "Competitor Sync",
            topic_key="local-seo" if page.normalized_url.endswith("/local-seo") else "competitor-sync",
            search_intent="commercial",
            content_format="service_page",
            page_role="money_page",
            evidence_snippets=["Local SEO services for growing businesses."],
            confidence=0.82,
        )

    with sqlite_session_factory() as session:
        result = competitive_gap_sync_service.run_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
            fetch_document=fake_fetch,
            extract_competitor_page=fake_extract,
        )
        session.commit()

        assert result.pages_saved == 2
        assert result.extraction_created == 1
        assert result.extraction_skipped == 1
        assert result.summary_payload["skipped_non_indexable_count"] == 1
        assert "https://competitor-sync.com/noindex-service" in result.summary_payload["sample_urls_by_reason"]["non_indexable"]

        pages = session.scalars(
            select(competitive_gap_sync_service.SiteCompetitorPage)
            .where(competitive_gap_sync_service.SiteCompetitorPage.competitor_id == ids["competitor_id"])
            .order_by(competitive_gap_sync_service.SiteCompetitorPage.id.asc())
        ).all()
        assert {page.normalized_url for page in pages} == {
            "https://competitor-sync.com/",
            "https://competitor-sync.com/local-seo",
        }


def test_run_site_competitor_sync_does_not_fail_when_all_pages_are_filtered_by_quality_gate(
    sqlite_session_factory,
) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    html_map = {
        "https://competitor-sync.com/": _make_document(
            "https://competitor-sync.com/",
            """
            <html><body>
              <a href="/o-firmie">O firmie</a>
              <a href="/galeria">Galeria</a>
              <a href="/kontakt">Kontakt</a>
            </body></html>
            """,
        ),
        "https://competitor-sync.com/o-firmie": _make_document(
            "https://competitor-sync.com/o-firmie",
            """
            <html><head><title>O firmie</title></head><body>
              <p>Poznaj nasz zespol.</p>
            </body></html>
            """,
        ),
        "https://competitor-sync.com/galeria": _make_document(
            "https://competitor-sync.com/galeria",
            """
            <html><head><title>Galeria</title></head><body>
              <p>Galeria realizacji.</p>
            </body></html>
            """,
        ),
        "https://competitor-sync.com/kontakt": _make_document(
            "https://competitor-sync.com/kontakt",
            """
            <html><head><title>Kontakt</title></head><body>
              <p>Skontaktuj sie z nami.</p>
            </body></html>
            """,
        ),
    }

    def fake_fetch(url: str):
        return html_map.get(url)

    def fake_extract(_page):
        raise AssertionError("No page should reach extraction when every page is excluded by the quality gate.")

    with sqlite_session_factory() as session:
        result = competitive_gap_sync_service.run_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
            fetch_document=fake_fetch,
            extract_competitor_page=fake_extract,
        )
        session.commit()

        assert result.pages_saved == 4
        assert result.extraction_created == 0
        assert result.extraction_skipped == 4
        assert result.extraction_failed == 0
        assert result.summary_payload["stored_pages_count"] == 4
        assert result.summary_payload["extracted_pages_count"] == 0


def test_run_site_competitor_sync_reextracts_changed_pages_only(sqlite_session_factory) -> None:
    ids = _seed_sync_site(sqlite_session_factory)
    extraction_calls: list[str] = []
    local_seo_body = {
        "value": """
        <html><head><title>Local SEO services</title></head><body>
          <h1>Local SEO services</h1>
          <p>Local SEO services for growing businesses and Google Business Profile support.</p>
        </body></html>
        """,
    }

    def fake_fetch(url: str):
        pages = {
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
                local_seo_body["value"],
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
        return pages.get(url)

    def fake_extract(page):
        extraction_calls.append(page.normalized_url)
        topic_label = "Local SEO" if page.normalized_url.endswith("/local-seo") else "SEO Audit"
        topic_key = "local-seo" if page.normalized_url.endswith("/local-seo") else "seo-audit"
        return _make_extraction_result(
            topic_label=topic_label,
            topic_key=topic_key,
            search_intent="commercial" if topic_key == "local-seo" else "informational",
            content_format="service_page" if topic_key == "local-seo" else "faq",
            page_role="money_page" if topic_key == "local-seo" else "supporting_page",
            evidence_snippets=[topic_label],
            confidence=0.8,
        )

    with sqlite_session_factory() as session:
        competitive_gap_sync_service.run_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
            fetch_document=fake_fetch,
            extract_competitor_page=fake_extract,
        )
        session.commit()

    local_seo_body["value"] = """
        <html><head><title>Local SEO services</title></head><body>
          <h1>Local SEO services</h1>
          <p>Local SEO services for multi-location businesses, Google Business Profile support and review strategy.</p>
        </body></html>
    """

    with sqlite_session_factory() as session:
        result = competitive_gap_sync_service.run_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
            fetch_document=fake_fetch,
            extract_competitor_page=fake_extract,
        )
        session.commit()

        assert result.extraction_created == 1
        assert result.extraction_skipped == 2

        local_page_extractions = session.scalars(
            select(SiteCompetitorPageExtraction)
            .where(
                SiteCompetitorPageExtraction.competitor_id == ids["competitor_id"],
                SiteCompetitorPageExtraction.competitor_page.has(
                    normalized_url="https://competitor-sync.com/local-seo"
                ),
            )
            .order_by(SiteCompetitorPageExtraction.id.asc())
        ).all()
        assert len(local_page_extractions) == 2
        assert extraction_calls.count("https://competitor-sync.com/local-seo") == 2
        assert extraction_calls.count("https://competitor-sync.com/seo-audit-faq") == 1


def test_run_site_competitor_sync_continues_when_semantic_foundation_fails(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    html_map = {
        "https://competitor-sync.com/": _make_document(
            "https://competitor-sync.com/",
            """
            <html><body>
              <h1>Competitor Sync</h1>
              <p>SEO consultancy homepage.</p>
              <a href="/local-seo">Local SEO</a>
            </body></html>
            """,
        ),
        "https://competitor-sync.com/local-seo": _make_document(
            "https://competitor-sync.com/local-seo",
            """
            <html><head><title>Local SEO services</title></head><body>
              <h1>Local SEO services</h1>
              <p>Local SEO services for growing businesses.</p>
            </body></html>
            """,
        ),
    }

    def fake_fetch(url: str):
        return html_map.get(url)

    def fake_extract(page):
        return _make_extraction_result(
            topic_label="Local SEO" if page.normalized_url.endswith("/local-seo") else "Competitor Sync",
            topic_key="local-seo" if page.normalized_url.endswith("/local-seo") else "competitor-sync",
            search_intent="commercial",
            content_format="service_page",
            page_role="money_page",
            evidence_snippets=["Local SEO services for growing businesses."],
            confidence=0.84,
        )

    monkeypatch.setattr(
        competitive_gap_sync_service.competitive_gap_semantic_service,
        "refresh_competitor_semantic_foundation",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("semantic failure")),
    )

    with sqlite_session_factory() as session:
        result = competitive_gap_sync_service.run_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
            fetch_document=fake_fetch,
            extract_competitor_page=fake_extract,
        )
        session.commit()

        assert result.pages_saved == 2
        assert result.extraction_created == 1
        assert result.extraction_skipped == 1
        assert session.scalar(
            select(SiteCompetitorPageExtraction.id).where(
                SiteCompetitorPageExtraction.competitor_id == ids["competitor_id"]
            )
        ) is not None
        assert session.scalar(
            select(SiteCompetitorSemanticCandidate.id).where(
                SiteCompetitorSemanticCandidate.competitor_id == ids["competitor_id"]
            )
        ) is None


def test_run_site_competitor_sync_deduplicates_duplicate_normalized_urls_before_flush(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    duplicate_pages = [
        competitive_gap_sync_service.CrawledCompetitorPage(
            requested_url="https://competitor-sync.com/",
            normalized_url="https://competitor-sync.com/",
            final_url="https://competitor-sync.com/",
            status_code=200,
            content_type="text/html; charset=utf-8",
            fetched_at=FIXED_TIME,
            extracted_data=_make_extracted_page_data(
                title="Competitor Sync",
                meta_description="Homepage",
                h1="Competitor Sync",
                canonical_url="https://competitor-sync.com/",
                word_count=20,
                content_text_hash="hash-home-a",
                visible_text="Competitor Sync homepage",
                schema_present=True,
                schema_count=1,
                schema_types_json=["Organization"],
            ),
        ),
        competitive_gap_sync_service.CrawledCompetitorPage(
            requested_url="https://competitor-sync.com/?ref=nav",
            normalized_url="https://competitor-sync.com/",
            final_url="https://competitor-sync.com/",
            status_code=200,
            content_type="text/html; charset=utf-8",
            fetched_at=FIXED_TIME,
            extracted_data=_make_extracted_page_data(
                title="Competitor Sync Updated",
                meta_description="Homepage updated",
                h1="Competitor Sync Updated",
                canonical_url="https://competitor-sync.com/",
                word_count=24,
                content_text_hash="hash-home-b",
                visible_text="Competitor Sync homepage updated",
                schema_present=True,
                schema_count=1,
                schema_types_json=["Organization"],
            ),
        ),
    ]

    monkeypatch.setattr(
        competitive_gap_sync_service,
        "_crawl_competitor_pages",
        lambda competitor, *, fetch_document: duplicate_pages,
    )

    def fake_extract(page):
        return _make_extraction_result(
            topic_label="Orthopedic Lab",
            topic_key="orthopedic-lab",
            search_intent="commercial",
            content_format="service_page",
            page_role="money_page",
            evidence_snippets=["Competitor Sync homepage updated"],
            confidence=0.8,
        )

    with sqlite_session_factory() as session:
        result = competitive_gap_sync_service.run_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
            fetch_document=lambda _url: None,
            extract_competitor_page=fake_extract,
        )
        session.commit()

        assert result.pages_saved == 1
        assert result.extraction_created == 1

        pages = session.scalars(
            select(competitive_gap_sync_service.SiteCompetitorPage)
            .where(competitive_gap_sync_service.SiteCompetitorPage.competitor_id == ids["competitor_id"])
        ).all()
        assert len(pages) == 1
        assert pages[0].title == "Competitor Sync Updated"


def test_run_site_competitor_sync_accepts_current_extraction_when_page_hash_is_null(
    sqlite_session_factory,
    monkeypatch,
) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    pages_with_null_hash = [
        competitive_gap_sync_service.CrawledCompetitorPage(
            requested_url="https://competitor-sync.com/local-seo",
            normalized_url="https://competitor-sync.com/local-seo",
            final_url="https://competitor-sync.com/local-seo",
            status_code=200,
            content_type="text/html; charset=utf-8",
            fetched_at=FIXED_TIME,
            extracted_data=_make_extracted_page_data(
                title="Local SEO services",
                meta_description="Local SEO support for growing businesses.",
                h1="Local SEO services",
                canonical_url="https://competitor-sync.com/local-seo",
                word_count=0,
                content_text_hash=None,
                visible_text="Local SEO services for growing businesses.",
            ),
        ),
    ]

    monkeypatch.setattr(
        competitive_gap_sync_service,
        "_crawl_competitor_pages",
        lambda competitor, *, fetch_document: pages_with_null_hash,
    )

    def fake_extract(page):
        return _make_extraction_result(
            topic_label="Local SEO",
            topic_key="local-seo",
            search_intent="commercial",
            content_format="service_page",
            page_role="money_page",
            evidence_snippets=["Local SEO"],
            confidence=0.71,
        )

    with sqlite_session_factory() as session:
        result = competitive_gap_sync_service.run_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
            fetch_document=lambda _url: None,
            extract_competitor_page=fake_extract,
        )
        session.commit()

        assert result.pages_saved == 1
        assert result.extraction_created == 1


def test_run_site_competitor_sync_keeps_checkpointed_pages_and_extractions_when_later_step_crashes(
    sqlite_session_factory,
) -> None:
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
              <p>Local SEO services for growing businesses.</p>
            </body></html>
            """,
        ),
        "https://competitor-sync.com/seo-audit-faq": _make_document(
            "https://competitor-sync.com/seo-audit-faq",
            """
            <html><head><title>SEO Audit FAQ</title></head><body>
              <h1>SEO Audit FAQ</h1>
              <p>Frequently asked questions about SEO audits.</p>
            </body></html>
            """,
        ),
    }

    def fake_fetch(url: str):
        return html_map.get(url)

    def fake_extract(page):
        if page.normalized_url.endswith("/") or page.normalized_url.endswith("/local-seo"):
            return _make_extraction_result(
                topic_label="Local SEO" if page.normalized_url.endswith("/local-seo") else "Competitor Sync",
                topic_key="local-seo" if page.normalized_url.endswith("/local-seo") else "competitor-sync",
                search_intent="commercial",
                content_format="service_page",
                page_role="money_page",
                evidence_snippets=["Local SEO services for growing businesses."],
                confidence=0.86,
            )
        raise RuntimeError("unexpected extraction crash")

    with sqlite_session_factory() as session:
        competitor = session.get(competitive_gap_sync_service.SiteCompetitor, ids["competitor_id"])
        assert competitor is not None
        competitor.last_sync_run_id = 1
        competitor.last_sync_status = "running"
        competitor.last_sync_stage = "crawling"
        _attach_sync_run(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_id"],
            run_id=1,
            status="running",
            stage="crawling",
        )
        session.commit()

    with sqlite_session_factory() as session:
        try:
            competitive_gap_sync_service.run_site_competitor_sync(
                session,
                ids["site_id"],
                ids["competitor_id"],
                fetch_document=fake_fetch,
                extract_competitor_page=fake_extract,
                sync_run_id=1,
                persist_sync_progress=True,
                checkpoint_after_save=True,
                checkpoint_each_extraction=True,
            )
        except RuntimeError as exc:
            assert "unexpected extraction crash" in str(exc)
        else:  # pragma: no cover - defensive branch
            raise AssertionError("Expected extraction crash to bubble up.")

    with sqlite_session_factory() as session:
        pages = session.scalars(
            select(competitive_gap_sync_service.SiteCompetitorPage)
            .where(competitive_gap_sync_service.SiteCompetitorPage.competitor_id == ids["competitor_id"])
            .order_by(competitive_gap_sync_service.SiteCompetitorPage.id.asc())
        ).all()
        assert len(pages) == 3

        extractions = session.scalars(
            select(SiteCompetitorPageExtraction)
            .where(SiteCompetitorPageExtraction.competitor_id == ids["competitor_id"])
            .order_by(SiteCompetitorPageExtraction.id.asc())
        ).all()
        assert len(extractions) >= 1

        competitor = session.get(competitive_gap_sync_service.SiteCompetitor, ids["competitor_id"])
        assert competitor is not None
        assert competitor.last_sync_stage == "extracting"
        assert competitor.last_sync_processed_urls >= 3
        assert competitor.last_sync_processed_extraction_pages >= 1


def test_reset_site_competitor_sync_clears_runtime_state_without_deleting_saved_rows(sqlite_session_factory) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        competitor = session.get(competitive_gap_sync_service.SiteCompetitor, ids["competitor_id"])
        assert competitor is not None
        competitor.last_sync_status = "failed"
        competitor.last_sync_stage = "extracting"
        competitor.last_sync_started_at = FIXED_TIME
        competitor.last_sync_finished_at = FIXED_TIME
        competitor.last_sync_error = "timeout"
        competitor.last_sync_processed_urls = 12
        competitor.last_sync_processed_extraction_pages = 3
        competitor.last_sync_total_extractable_pages = 9
        session.add(
            competitive_gap_sync_service.SiteCompetitorPage(
                site_id=ids["site_id"],
                competitor_id=ids["competitor_id"],
                url="https://competitor-sync.com/local-seo",
                normalized_url="https://competitor-sync.com/local-seo",
            )
        )
        session.commit()

    with sqlite_session_factory() as session:
        payload = competitive_gap_sync_service.reset_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
        )
        session.commit()

        assert payload["last_sync_status"] == "idle"
        assert payload["last_sync_stage"] == "idle"
        assert payload["last_sync_error_code"] is None
        assert payload["last_sync_error"] is None
        assert payload["last_sync_processed_urls"] == 0
        assert payload["last_sync_processed_extraction_pages"] == 0
        assert payload["last_sync_total_extractable_pages"] == 0
        assert payload["last_sync_summary"]["visited_urls_count"] == 0
        assert payload["last_sync_summary"]["stored_pages_count"] == 0
        assert payload["pages_count"] == 1


def test_queue_site_competitor_sync_blocks_duplicate_running_sync(sqlite_session_factory) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        competitor = session.get(competitive_gap_sync_service.SiteCompetitor, ids["competitor_id"])
        assert competitor is not None
        competitor.last_sync_run_id = 1
        competitor.last_sync_status = "running"
        competitor.last_sync_stage = "crawling"
        _attach_sync_run(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_id"],
            run_id=1,
            status="running",
            stage="crawling",
        )
        session.commit()

    with sqlite_session_factory() as session:
        try:
            competitive_gap_sync_service.queue_site_competitor_sync(
                session,
                ids["site_id"],
                ids["competitor_id"],
            )
        except competitive_gap_sync_service.CompetitiveGapSyncServiceError as exc:
            assert exc.code == "already_running"
            assert "already queued or running" in str(exc)
        else:  # pragma: no cover - defensive branch
            raise AssertionError("Expected duplicate queue protection to raise.")


def test_queue_site_competitor_sync_reconciles_stale_runtime_before_requeue(sqlite_session_factory) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        competitor = session.get(SiteCompetitor, ids["competitor_id"])
        assert competitor is not None
        competitor.last_sync_run_id = 1
        competitor.last_sync_status = "running"
        competitor.last_sync_stage = "crawling"
        competitor.last_sync_started_at = FIXED_TIME
        stale_run = _attach_sync_run(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_id"],
            run_id=1,
            status="running",
            stage="crawling",
        )
        stale_run.lease_expires_at = FIXED_TIME - timedelta(seconds=1)
        session.commit()

    with sqlite_session_factory() as session:
        payload = competitive_gap_sync_service.queue_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
        )
        session.commit()

        assert payload["last_sync_status"] == "queued"
        assert payload["last_sync_run_id"] == 2

        runs = competitive_gap_sync_run_service.list_sync_runs(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_id"],
        )
        assert runs[0]["run_id"] == 2
        assert runs[0]["status"] == "queued"
        assert runs[1]["run_id"] == 1
        assert runs[1]["status"] == "stale"
        assert runs[1]["error_code"] == competitive_gap_sync_run_service.STALE_RUN_ERROR_CODE


def test_retry_site_competitor_sync_queues_new_run_from_latest_failed_run(sqlite_session_factory) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        competitor = session.get(SiteCompetitor, ids["competitor_id"])
        assert competitor is not None
        competitor.last_sync_run_id = 3
        competitor.last_sync_status = "failed"
        competitor.last_sync_stage = "failed"
        _attach_sync_run(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_id"],
            run_id=3,
            status="failed",
            stage="failed",
            error_code="timeout",
            error_message_safe="OpenAI request timed out.",
        )
        session.commit()

    with sqlite_session_factory() as session:
        payload = competitive_gap_sync_service.retry_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
        )
        session.commit()

        assert payload["last_sync_status"] == "queued"
        assert payload["last_sync_run_id"] == 4

        runs = competitive_gap_sync_run_service.list_sync_runs(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_id"],
        )
        assert runs[0]["run_id"] == 4
        assert runs[0]["trigger_source"] == "retry"
        assert runs[0]["retry_of_run_id"] == 3
        assert runs[1]["run_id"] == 3
        assert runs[1]["status"] == "failed"


def test_reset_site_competitor_sync_cancels_active_run_and_preserves_run_history(sqlite_session_factory) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        competitor = session.get(SiteCompetitor, ids["competitor_id"])
        assert competitor is not None
        competitor.last_sync_run_id = 2
        competitor.last_sync_status = "running"
        competitor.last_sync_stage = "extracting"
        competitor.last_sync_processed_urls = 8
        competitor.last_sync_processed_extraction_pages = 2
        active_run = _attach_sync_run(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_id"],
            run_id=2,
            status="running",
            stage="extracting",
        )
        active_run.processed_urls = 8
        active_run.processed_extraction_pages = 2
        session.commit()

    with sqlite_session_factory() as session:
        payload = competitive_gap_sync_service.reset_site_competitor_sync(
            session,
            ids["site_id"],
            ids["competitor_id"],
        )
        session.commit()

        assert payload["last_sync_status"] == "idle"
        assert payload["last_sync_stage"] == "idle"

        runs = competitive_gap_sync_run_service.list_sync_runs(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_id"],
        )
        assert runs[0]["run_id"] == 2
        assert runs[0]["status"] == "cancelled"
        assert runs[0]["error_code"] == competitive_gap_sync_run_service.CANCELLED_RUN_ERROR_CODE


def test_list_site_competitor_sync_runs_returns_latest_runs_desc(sqlite_session_factory) -> None:
    ids = _seed_sync_site(sqlite_session_factory)

    with sqlite_session_factory() as session:
        session.add_all(
            [
                SiteCompetitorSyncRun(
                    site_id=ids["site_id"],
                    competitor_id=ids["competitor_id"],
                    run_id=1,
                    status="done",
                    stage="done",
                    trigger_source="manual_single",
                    started_at=FIXED_TIME,
                    finished_at=FIXED_TIME,
                    last_heartbeat_at=FIXED_TIME,
                    lease_expires_at=FIXED_TIME,
                    summary_json=competitive_gap_sync_service.site_competitor_service.build_empty_sync_summary_payload(),
                    processed_urls=12,
                    url_limit=competitive_gap_sync_service.COMPETITOR_SYNC_MAX_URLS,
                    processed_extraction_pages=4,
                    total_extractable_pages=4,
                    created_at=FIXED_TIME,
                    updated_at=FIXED_TIME,
                ),
                SiteCompetitorSyncRun(
                    site_id=ids["site_id"],
                    competitor_id=ids["competitor_id"],
                    run_id=2,
                    status="failed",
                    stage="failed",
                    trigger_source="retry",
                    started_at=FIXED_TIME,
                    finished_at=FIXED_TIME,
                    last_heartbeat_at=FIXED_TIME,
                    lease_expires_at=FIXED_TIME,
                    error_code="timeout",
                    error_message_safe="OpenAI request timed out.",
                    summary_json=competitive_gap_sync_service.site_competitor_service.build_empty_sync_summary_payload(),
                    retry_of_run_id=1,
                    processed_urls=6,
                    url_limit=competitive_gap_sync_service.COMPETITOR_SYNC_MAX_URLS,
                    processed_extraction_pages=1,
                    total_extractable_pages=3,
                    created_at=FIXED_TIME,
                    updated_at=FIXED_TIME,
                ),
            ]
        )
        session.commit()

    with sqlite_session_factory() as session:
        payload = competitive_gap_sync_service.list_site_competitor_sync_runs(
            session,
            ids["site_id"],
            ids["competitor_id"],
            limit=5,
        )
        assert [item["run_id"] for item in payload] == [2, 1]
        assert payload[0]["status"] == "failed"
        assert payload[0]["retry_of_run_id"] == 1
