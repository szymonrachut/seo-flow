from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import (
    CrawlJob,
    CrawlJobStatus,
    GscProperty,
    GscUrlMetric,
    Page,
    Site,
    SiteCompetitor,
    SiteCompetitorPage,
    SiteCompetitorPageExtraction,
    SiteContentStrategy,
)
from app.services.competitive_gap_page_diagnostics import build_fetch_diagnostics_payload
from app.services.competitive_gap_semantic_card_service import build_semantic_card


FIXED_TIME = datetime(2026, 3, 16, 12, 0, tzinfo=timezone.utc)


def _make_extraction_semantic_fields(
    *,
    topic_label: str,
    search_intent: str = "commercial",
    page_role: str = "money_page",
    content_format: str = "service_page",
    confidence: float = 0.8,
) -> dict[str, object]:
    semantic_card = build_semantic_card(
        primary_topic=topic_label,
        topic_labels=[topic_label],
        core_problem=topic_label,
        dominant_intent=search_intent,
        secondary_intents=[],
        page_role=page_role,
        content_format=content_format,
        target_audience=None,
        entities=[],
        geo_scope=None,
        supporting_subtopics=[],
        what_this_page_is_about=topic_label,
        what_this_page_is_not_about="Other topics.",
        commerciality="high" if search_intent == "commercial" else "medium",
        evidence_snippets=[],
        confidence=confidence,
    )
    return {
        "semantic_card_json": semantic_card,
        "semantic_version": semantic_card["semantic_version"],
        "semantic_input_hash": semantic_card["semantic_input_hash"],
    }


def _make_page(crawl_job_id: int, path: str, **overrides) -> Page:
    url = f"https://example.com{path}"
    defaults = {
        "crawl_job_id": crawl_job_id,
        "url": url,
        "normalized_url": url,
        "final_url": url,
        "status_code": 200,
        "title": path.strip("/") or "Home",
        "meta_description": f"Meta for {path}",
        "h1": path.strip("/") or "Home",
        "canonical_url": url,
        "content_type": "text/html",
        "word_count": 500,
        "h1_count": 1,
        "h2_count": 2,
        "schema_present": True,
        "schema_count": 1,
        "schema_types_json": [],
        "is_internal": True,
        "depth": len([segment for segment in path.split("/") if segment]),
        "fetched_at": FIXED_TIME,
        "created_at": FIXED_TIME,
    }
    defaults.update(overrides)
    return Page(**defaults)


def _add_gsc_metric(
    session,
    *,
    gsc_property_id: int,
    crawl_job_id: int,
    page: Page,
    clicks: int,
    impressions: int,
    ctr: float,
    position: float,
) -> None:
    session.add(
        GscUrlMetric(
            gsc_property_id=gsc_property_id,
            crawl_job_id=crawl_job_id,
            page_id=page.id,
            url=page.url,
            normalized_url=page.normalized_url,
            date_range_label="last_28_days",
            clicks=clicks,
            impressions=impressions,
            ctr=ctr,
            position=position,
            fetched_at=FIXED_TIME,
            created_at=FIXED_TIME,
        )
    )


def seed_competitive_gap_site(session_factory) -> dict[str, int]:
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

        gsc_property = GscProperty(
            site_id=site.id,
            property_uri="sc-domain:example.com",
            permission_level="siteOwner",
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        session.add(gsc_property)
        session.flush()

        content_strategy = SiteContentStrategy(
            site_id=site.id,
            raw_user_input="Focus on local SEO, audits and content strategy.",
            normalized_strategy_json={
                "schema_version": "competitive_gap_strategy_v1",
                "business_summary": "SEO consultancy focused on audits, local SEO and strategy.",
                "target_audiences": ["local businesses", "marketing teams"],
                "primary_goals": ["lead generation", "local visibility"],
                "priority_topics": ["local seo", "seo audit", "content strategy"],
                "supporting_topics": ["google business profile", "technical seo"],
                "priority_page_types": ["service", "faq"],
                "geographic_focus": ["Poland"],
                "constraints": ["no broad ecommerce scope"],
                "differentiation_points": ["hands-on consulting"],
            },
            llm_provider=None,
            llm_model=None,
            prompt_version=None,
            normalization_status="ready",
            normalized_at=FIXED_TIME,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        session.add(content_strategy)

        pages = {
            "audit": _make_page(
                crawl_job.id,
                "/seo-audit",
                title="SEO Audit",
                h1="SEO Audit",
                page_type="service",
                page_bucket="commercial",
                page_type_confidence=0.92,
                page_type_version="11.1-v1",
                page_type_rationale="seed",
                word_count=850,
            ),
            "content_strategy": _make_page(
                crawl_job.id,
                "/content-strategy",
                title="Content Strategy",
                h1="Content Strategy",
                page_type="service",
                page_bucket="commercial",
                page_type_confidence=0.94,
                page_type_version="11.1-v1",
                page_type_rationale="seed",
                word_count=620,
                meta_description=None,
            ),
            "about": _make_page(
                crawl_job.id,
                "/about",
                title="About",
                h1="About",
                page_type="about",
                page_bucket="trust",
                page_type_confidence=0.91,
                page_type_version="11.1-v1",
                page_type_rationale="seed",
            ),
        }
        session.add_all(pages.values())
        session.flush()

        _add_gsc_metric(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=crawl_job.id,
            page=pages["audit"],
            clicks=14,
            impressions=240,
            ctr=0.058,
            position=6.8,
        )
        _add_gsc_metric(
            session,
            gsc_property_id=gsc_property.id,
            crawl_job_id=crawl_job.id,
            page=pages["content_strategy"],
            clicks=11,
            impressions=180,
            ctr=0.061,
            position=8.1,
        )

        competitor_a = SiteCompetitor(
            site_id=site.id,
            label="Competitor A",
            root_url="https://competitor-a.com",
            domain="competitor-a.com",
            is_active=True,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        competitor_b = SiteCompetitor(
            site_id=site.id,
            label="Competitor B",
            root_url="https://competitor-b.com",
            domain="competitor-b.com",
            is_active=True,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        session.add_all([competitor_a, competitor_b])
        session.flush()

        local_a = SiteCompetitorPage(
            site_id=site.id,
            competitor_id=competitor_a.id,
            url="https://competitor-a.com/local-seo",
            normalized_url="https://competitor-a.com/local-seo",
            final_url="https://competitor-a.com/local-seo",
            title="Local SEO Services",
            h1="Local SEO Services",
            page_type="service",
            page_bucket="commercial",
            page_type_confidence=0.91,
            semantic_eligible=True,
            semantic_exclusion_reason=None,
            semantic_input_hash="seed-local-a",
            semantic_last_evaluated_at=FIXED_TIME,
            fetch_diagnostics_json=build_fetch_diagnostics_payload(
                schema_count=1,
                schema_types=["Service"],
            ),
            visible_text="Local SEO services for growing businesses.",
            fetched_at=FIXED_TIME,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        local_b = SiteCompetitorPage(
            site_id=site.id,
            competitor_id=competitor_b.id,
            url="https://competitor-b.com/local-seo",
            normalized_url="https://competitor-b.com/local-seo",
            final_url="https://competitor-b.com/local-seo",
            title="Local SEO Agency",
            h1="Local SEO Agency",
            page_type="service",
            page_bucket="commercial",
            page_type_confidence=0.9,
            semantic_eligible=True,
            semantic_exclusion_reason=None,
            semantic_input_hash="seed-local-b",
            semantic_last_evaluated_at=FIXED_TIME,
            fetch_diagnostics_json=build_fetch_diagnostics_payload(
                schema_count=1,
                schema_types=["Service"],
            ),
            visible_text="Local SEO agency with GBP optimization and local pages.",
            fetched_at=FIXED_TIME,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        audit_a = SiteCompetitorPage(
            site_id=site.id,
            competitor_id=competitor_a.id,
            url="https://competitor-a.com/seo-audit",
            normalized_url="https://competitor-a.com/seo-audit",
            final_url="https://competitor-a.com/seo-audit",
            title="SEO Audit Services",
            h1="SEO Audit Services",
            page_type="service",
            page_bucket="commercial",
            page_type_confidence=0.93,
            semantic_eligible=True,
            semantic_exclusion_reason=None,
            semantic_input_hash="seed-audit-a",
            semantic_last_evaluated_at=FIXED_TIME,
            fetch_diagnostics_json=build_fetch_diagnostics_payload(
                schema_count=1,
                schema_types=["Service"],
            ),
            visible_text="Technical SEO audit and strategy engagement.",
            fetched_at=FIXED_TIME,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        audit_b = SiteCompetitorPage(
            site_id=site.id,
            competitor_id=competitor_b.id,
            url="https://competitor-b.com/seo-audit/faq",
            normalized_url="https://competitor-b.com/seo-audit/faq",
            final_url="https://competitor-b.com/seo-audit/faq",
            title="SEO Audit FAQ",
            h1="SEO Audit FAQ",
            page_type="faq",
            page_bucket="informational",
            page_type_confidence=0.95,
            semantic_eligible=True,
            semantic_exclusion_reason=None,
            semantic_input_hash="seed-audit-b",
            semantic_last_evaluated_at=FIXED_TIME,
            fetch_diagnostics_json=build_fetch_diagnostics_payload(
                schema_count=1,
                schema_types=["FAQPage"],
            ),
            visible_text="SEO audit FAQ with common questions.",
            fetched_at=FIXED_TIME,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        content_a = SiteCompetitorPage(
            site_id=site.id,
            competitor_id=competitor_a.id,
            url="https://competitor-a.com/content-strategy",
            normalized_url="https://competitor-a.com/content-strategy",
            final_url="https://competitor-a.com/content-strategy",
            title="Content Strategy Services",
            h1="Content Strategy Services",
            page_type="service",
            page_bucket="commercial",
            page_type_confidence=0.94,
            semantic_eligible=True,
            semantic_exclusion_reason=None,
            semantic_input_hash="seed-content-a",
            semantic_last_evaluated_at=FIXED_TIME,
            fetch_diagnostics_json=build_fetch_diagnostics_payload(
                schema_count=1,
                schema_types=["Service"],
            ),
            visible_text="Content strategy services and editorial planning.",
            fetched_at=FIXED_TIME,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        content_b = SiteCompetitorPage(
            site_id=site.id,
            competitor_id=competitor_b.id,
            url="https://competitor-b.com/content-strategy",
            normalized_url="https://competitor-b.com/content-strategy",
            final_url="https://competitor-b.com/content-strategy",
            title="Content Strategy Consulting",
            h1="Content Strategy Consulting",
            page_type="service",
            page_bucket="commercial",
            page_type_confidence=0.94,
            semantic_eligible=True,
            semantic_exclusion_reason=None,
            semantic_input_hash="seed-content-b",
            semantic_last_evaluated_at=FIXED_TIME,
            fetch_diagnostics_json=build_fetch_diagnostics_payload(
                schema_count=1,
                schema_types=["Service"],
            ),
            visible_text="Content strategy consulting for SEO teams.",
            fetched_at=FIXED_TIME,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )
        session.add_all([local_a, local_b, audit_a, audit_b, content_a, content_b])
        session.flush()

        session.add_all(
            [
                SiteCompetitorPageExtraction(
                    site_id=site.id,
                    competitor_id=competitor_a.id,
                    competitor_page_id=local_a.id,
                    content_hash_at_extraction=local_a.content_text_hash,
                    topic_key="legacy-local",
                    topic_label="Legacy Local",
                    page_role="money_page",
                    confidence=0.3,
                    **_make_extraction_semantic_fields(topic_label="Legacy Local", confidence=0.3),
                    extracted_at=datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
                ),
                SiteCompetitorPageExtraction(
                    site_id=site.id,
                    competitor_id=competitor_a.id,
                    competitor_page_id=local_a.id,
                    content_hash_at_extraction=local_a.content_text_hash,
                    topic_key="local-seo",
                    topic_label="Local SEO",
                    page_role="money_page",
                    confidence=0.87,
                    **_make_extraction_semantic_fields(topic_label="Local SEO", confidence=0.87),
                    extracted_at=FIXED_TIME,
                ),
                SiteCompetitorPageExtraction(
                    site_id=site.id,
                    competitor_id=competitor_b.id,
                    competitor_page_id=local_b.id,
                    content_hash_at_extraction=local_b.content_text_hash,
                    topic_key="local-seo",
                    topic_label="Local SEO",
                    page_role="money_page",
                    confidence=0.85,
                    **_make_extraction_semantic_fields(topic_label="Local SEO", confidence=0.85),
                    extracted_at=FIXED_TIME,
                ),
                SiteCompetitorPageExtraction(
                    site_id=site.id,
                    competitor_id=competitor_a.id,
                    competitor_page_id=audit_a.id,
                    content_hash_at_extraction=audit_a.content_text_hash,
                    topic_key="seo-audit",
                    topic_label="SEO Audit",
                    page_role="money_page",
                    confidence=0.88,
                    **_make_extraction_semantic_fields(topic_label="SEO Audit", confidence=0.88),
                    extracted_at=FIXED_TIME,
                ),
                SiteCompetitorPageExtraction(
                    site_id=site.id,
                    competitor_id=competitor_b.id,
                    competitor_page_id=audit_b.id,
                    content_hash_at_extraction=audit_b.content_text_hash,
                    topic_key="seo-audit",
                    topic_label="SEO Audit",
                    page_role="supporting_page",
                    confidence=0.9,
                    **_make_extraction_semantic_fields(topic_label="SEO Audit", page_role="supporting_page", confidence=0.9),
                    extracted_at=FIXED_TIME,
                ),
                SiteCompetitorPageExtraction(
                    site_id=site.id,
                    competitor_id=competitor_a.id,
                    competitor_page_id=content_a.id,
                    content_hash_at_extraction=content_a.content_text_hash,
                    topic_key="content-strategy",
                    topic_label="Content Strategy",
                    page_role="money_page",
                    confidence=0.84,
                    **_make_extraction_semantic_fields(topic_label="Content Strategy", confidence=0.84),
                    extracted_at=FIXED_TIME,
                ),
                SiteCompetitorPageExtraction(
                    site_id=site.id,
                    competitor_id=competitor_b.id,
                    competitor_page_id=content_b.id,
                    content_hash_at_extraction=content_b.content_text_hash,
                    topic_key="content-strategy",
                    topic_label="Content Strategy",
                    page_role="money_page",
                    confidence=0.82,
                    **_make_extraction_semantic_fields(topic_label="Content Strategy", confidence=0.82),
                    extracted_at=FIXED_TIME,
                ),
            ]
        )
        session.commit()

        return {
            "site_id": site.id,
            "crawl_job_id": crawl_job.id,
            "audit_page_id": pages["audit"].id,
            "content_strategy_page_id": pages["content_strategy"].id,
            "competitor_a_id": competitor_a.id,
            "competitor_b_id": competitor_b.id,
        }
