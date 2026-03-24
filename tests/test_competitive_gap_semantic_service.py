from __future__ import annotations

from sqlalchemy import select

from app.db.models import (
    CrawlJob,
    CrawlJobStatus,
    Page,
    Site,
    SiteCompetitor,
    SiteCompetitorPage,
    SiteCompetitorSemanticCandidate,
)
from app.services import competitive_gap_semantic_service
from app.services.competitive_gap_page_diagnostics import build_fetch_diagnostics_payload
from app.services.competitive_gap_semantic_rules import resolve_semantic_exclusion_reason


def _seed_semantic_site(sqlite_session_factory) -> dict[str, int]:
    with sqlite_session_factory() as session:
        site = Site(root_url="https://example.com", domain="example.com")
        session.add(site)
        session.flush()

        crawl_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.FINISHED,
            settings_json={"start_url": site.root_url},
            stats_json={},
        )
        session.add(crawl_job)
        session.flush()

        service_page = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/local-seo",
            normalized_url="https://example.com/local-seo",
            final_url="https://example.com/local-seo",
            status_code=200,
            title="Local SEO Services",
            meta_description="Local SEO support for growing businesses.",
            h1="Local SEO Services",
            canonical_url="https://example.com/local-seo",
            content_type="text/html",
            word_count=320,
            schema_present=True,
            schema_count=1,
            schema_types_json=["Service"],
            page_type="service",
            page_bucket="commercial",
            page_type_confidence=0.95,
            page_type_version="11.1-v1",
            page_type_rationale="seed",
            is_internal=True,
            depth=1,
        )
        session.add(service_page)

        blog_page = Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/blog/local-seo-guide",
            normalized_url="https://example.com/blog/local-seo-guide",
            final_url="https://example.com/blog/local-seo-guide",
            status_code=200,
            title="Local SEO Guide",
            meta_description="A local SEO guide.",
            h1="Local SEO Guide",
            canonical_url="https://example.com/blog/local-seo-guide",
            content_type="text/html",
            word_count=280,
            schema_present=True,
            schema_count=1,
            schema_types_json=["Article"],
            page_type="blog_article",
            page_bucket="informational",
            page_type_confidence=0.91,
            page_type_version="11.1-v1",
            page_type_rationale="seed",
            is_internal=True,
            depth=2,
        )
        session.add(blog_page)
        session.flush()

        competitor_a = SiteCompetitor(
            site_id=site.id,
            label="Competitor A",
            root_url="https://competitor-a.com",
            domain="competitor-a.com",
            is_active=True,
        )
        competitor_b = SiteCompetitor(
            site_id=site.id,
            label="Competitor B",
            root_url="https://competitor-b.com",
            domain="competitor-b.com",
            is_active=True,
        )
        session.add_all([competitor_a, competitor_b])
        session.commit()

        return {
            "site_id": site.id,
            "crawl_job_id": crawl_job.id,
            "service_page_id": service_page.id,
            "blog_page_id": blog_page.id,
            "competitor_a_id": competitor_a.id,
            "competitor_b_id": competitor_b.id,
        }


def _create_competitor_page(
    session,
    *,
    site_id: int,
    competitor_id: int,
    url: str,
    title: str,
    h1: str,
    page_type: str = "service",
    page_bucket: str = "commercial",
    word_count: int = 220,
    schema_types_json: list[str] | None = None,
    robots_meta: str | None = None,
    x_robots_tag: str | None = None,
    status_code: int = 200,
    visible_text: str | None = None,
) -> SiteCompetitorPage:
    resolved_visible_text = visible_text or " ".join(["local", "seo", "services"] * max(40, word_count // 3))
    page = SiteCompetitorPage(
        site_id=site_id,
        competitor_id=competitor_id,
        url=url,
        normalized_url=url,
        final_url=url,
        status_code=status_code,
        title=title,
        h1=h1,
        canonical_url=url,
        content_type="text/html",
        visible_text=resolved_visible_text,
        fetch_diagnostics_json=build_fetch_diagnostics_payload(
            robots_meta=robots_meta,
            x_robots_tag=x_robots_tag,
            schema_count=len(schema_types_json or []),
            schema_types=schema_types_json or [],
        ),
        page_type=page_type,
        page_bucket=page_bucket,
        page_type_confidence=0.9,
    )
    session.add(page)
    session.flush()
    return page


def test_semantic_exclusion_rules_cover_expected_reasons() -> None:
    cases = [
        ({"status_code": 404, "normalized_url": "https://c.com/contact", "word_count": 200, "visible_text_chars": 900}, ["contact"], "error_like"),
        ({"status_code": 200, "robots_meta": "index, noindex", "normalized_url": "https://c.com/local-seo", "word_count": 200, "visible_text_chars": 900}, ["local", "seo"], "non_indexable"),
        ({"status_code": 200, "normalized_url": "https://c.com/privacy-policy", "word_count": 200, "visible_text_chars": 900}, ["privacy"], "privacy_policy"),
        ({"status_code": 200, "normalized_url": "https://c.com/regulamin-i-polityka-prywatnosci", "word_count": 200, "visible_text_chars": 900}, ["terms"], "terms"),
        ({"status_code": 200, "normalized_url": "https://c.com/regulamin", "word_count": 200, "visible_text_chars": 900, "page_type": "legal"}, ["terms"], "terms"),
        ({"status_code": 200, "normalized_url": "https://c.com/contact", "word_count": 200, "visible_text_chars": 900, "page_type": "contact"}, ["contact"], "contact"),
        ({"status_code": 200, "normalized_url": "https://c.com/o-nas", "title": "O nas", "h1": "O nas", "word_count": 220, "visible_text_chars": 900, "page_type": "about"}, ["company"], "weak_about"),
        ({"status_code": 200, "normalized_url": "https://c.com/punkty-konsultacyjne", "title": "Punkty konsultacyjne", "h1": "Punkty konsultacyjne", "word_count": 220, "visible_text_chars": 900}, ["punkt", "konsultacyjne"], "weak_location"),
        ({"status_code": 200, "normalized_url": "https://c.com/certyfikaty", "title": "Certyfikaty", "h1": "Certyfikaty", "word_count": 220, "visible_text_chars": 900}, ["certificate"], "weak_certificate"),
        ({"status_code": 200, "normalized_url": "https://c.com/cart", "word_count": 200, "visible_text_chars": 900}, ["cart"], "cart"),
        ({"status_code": 200, "normalized_url": "https://c.com/checkout", "word_count": 200, "visible_text_chars": 900}, ["checkout"], "checkout"),
        ({"status_code": 200, "normalized_url": "https://c.com/account", "word_count": 200, "visible_text_chars": 900}, ["account"], "account"),
        ({"status_code": 200, "normalized_url": "https://c.com/login", "word_count": 200, "visible_text_chars": 900}, ["login"], "login"),
        ({"status_code": 200, "normalized_url": "https://c.com/register", "word_count": 200, "visible_text_chars": 900}, ["register"], "register"),
        ({"status_code": 200, "normalized_url": "https://c.com/search", "word_count": 200, "visible_text_chars": 900}, ["search"], "search"),
        ({"status_code": 200, "normalized_url": "https://c.com/tag/local-seo", "word_count": 200, "visible_text_chars": 900}, ["tag"], "tag"),
        ({"status_code": 200, "normalized_url": "https://c.com/archive/2026", "word_count": 200, "visible_text_chars": 900}, ["archive"], "archive"),
        ({"status_code": 200, "normalized_url": "https://c.com/tools", "page_type": "utility", "word_count": 200, "visible_text_chars": 900}, ["tool"], "utility_page"),
        ({"status_code": 200, "normalized_url": "https://c.com/local-seo", "word_count": 50, "visible_text_chars": 240}, ["local", "seo"], "thin"),
        ({"status_code": 200, "normalized_url": "https://c.com/local-seo", "word_count": 240, "visible_text_chars": 900}, [], "low_value"),
    ]

    for page, match_terms, expected in cases:
        assert resolve_semantic_exclusion_reason(page, match_terms=match_terms) == expected


def test_semantic_exclusion_keeps_actionable_slug_pages_with_generic_shared_title() -> None:
    page = {
        "status_code": 200,
        "normalized_url": "https://c.com/protezy-konczyn",
        "final_url": "https://c.com/protezy-konczyn",
        "title": "Proteza Nogi, Protezy Kończyn Dolnych, Ortezy - Protetyk Marian Zarychta",
        "h1": None,
        "meta_description": None,
        "page_type": "other",
        "word_count": 260,
        "visible_text_chars": 1400,
        "visible_text": (
            "Protezy konczyn Strona Glowna Protezy konczyn "
            "W poradni zaopatrujemy w indywidualnie dobrane protezy konczyn dolnych oraz gornych. "
            "Protezy konczyn pomagaja odzyskac mobilnosc i komfort ruchu."
        ),
    }

    assert resolve_semantic_exclusion_reason(page, match_terms=["protezy", "konczyn"]) is None


def test_materialize_page_semantic_topic_is_deterministic(sqlite_session_factory) -> None:
    ids = _seed_semantic_site(sqlite_session_factory)
    with sqlite_session_factory() as session:
        page = _create_competitor_page(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            url="https://competitor-a.com/services/local-seo",
            title="Local SEO Services",
            h1="Local SEO Services",
            word_count=280,
            schema_types_json=["Service"],
        )
        first = competitive_gap_semantic_service.materialize_page_semantic_topic(page)
        second = competitive_gap_semantic_service.materialize_page_semantic_topic(page)

        assert first.semantic_input_hash == second.semantic_input_hash
        assert first.raw_topic_key == "local-seo"
        assert first.raw_topic_label == "Local SEO Services"
        assert first.primary_tokens == ["local", "seo"]
        assert first.match_terms[:2] == ["local", "seo"]
        assert 80 <= first.quality_score <= 100

        page.h1 = "Local SEO for Clinics"
        third = competitive_gap_semantic_service.materialize_page_semantic_topic(page)
        assert third.semantic_input_hash != first.semantic_input_hash


def test_materialize_page_semantic_topic_prefers_title_h1_and_meta_over_boilerplate_body(sqlite_session_factory) -> None:
    ids = _seed_semantic_site(sqlite_session_factory)
    with sqlite_session_factory() as session:
        page = _create_competitor_page(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            url="https://competitor-a.com/services/local-seo",
            title="Local SEO Services",
            h1="Local SEO Services",
            word_count=420,
            visible_text=(
                "Sidebar boilerplate appointments clinic team contact gallery " * 14
                + "Local SEO services for multi-location clinics and GBP optimization. "
            ),
            schema_types_json=["Service"],
        )
        page.meta_description = "Local SEO services for multi-location clinics."
        materialized = competitive_gap_semantic_service.materialize_page_semantic_topic(page)

        assert materialized.raw_topic_key == "local-seo"
        assert materialized.raw_topic_label == "Local SEO Services"
        assert materialized.primary_tokens[:2] == ["local", "seo"]
        assert materialized.match_terms[:2] == ["local", "seo"]


def test_refresh_competitor_semantic_foundation_inserts_skips_and_retires(sqlite_session_factory) -> None:
    ids = _seed_semantic_site(sqlite_session_factory)
    with sqlite_session_factory() as session:
        page = _create_competitor_page(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            url="https://competitor-a.com/services/local-seo",
            title="Local SEO Services",
            h1="Local SEO Services",
            word_count=240,
            schema_types_json=["Service"],
        )
        session.commit()

    with sqlite_session_factory() as session:
        result = competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
            session,
            ids["site_id"],
            ids["competitor_a_id"],
            page_ids=[page.id],
        )
        session.commit()

        assert result.eligible_pages == 1
        assert result.inserted_candidates == 1
        stored_page = session.get(SiteCompetitorPage, page.id)
        assert stored_page is not None
        assert stored_page.semantic_eligible is True
        assert stored_page.semantic_exclusion_reason is None

    with sqlite_session_factory() as session:
        result = competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
            session,
            ids["site_id"],
            ids["competitor_a_id"],
            page_ids=[page.id],
        )
        session.commit()

        assert result.unchanged_pages == 1
        assert result.inserted_candidates == 0
        assert session.scalar(
            select(SiteCompetitorSemanticCandidate.id).where(
                SiteCompetitorSemanticCandidate.competitor_page_id == page.id
            )
        ) is not None

    with sqlite_session_factory() as session:
        stored_page = session.get(SiteCompetitorPage, page.id)
        assert stored_page is not None
        stored_page.h1 = "Local SEO for Multi-Location Clinics"
        result = competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
            session,
            ids["site_id"],
            ids["competitor_a_id"],
            page_ids=[page.id],
        )
        session.commit()

        rows = session.scalars(
            select(SiteCompetitorSemanticCandidate)
            .where(SiteCompetitorSemanticCandidate.competitor_page_id == page.id)
            .order_by(SiteCompetitorSemanticCandidate.id.asc())
        ).all()
        assert result.retired_candidates == 1
        assert result.inserted_candidates == 1
        assert len(rows) == 2
        assert rows[0].current is False
        assert rows[1].current is True


def test_refresh_competitor_semantic_foundation_retires_candidates_when_page_becomes_excluded(sqlite_session_factory) -> None:
    ids = _seed_semantic_site(sqlite_session_factory)
    with sqlite_session_factory() as session:
        page = _create_competitor_page(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            url="https://competitor-a.com/local-seo",
            title="Local SEO Services",
            h1="Local SEO Services",
            word_count=240,
            schema_types_json=["Service"],
        )
        competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
            session,
            ids["site_id"],
            ids["competitor_a_id"],
            page_ids=[page.id],
        )
        session.commit()

    with sqlite_session_factory() as session:
        stored_page = session.get(SiteCompetitorPage, page.id)
        assert stored_page is not None
        stored_page.normalized_url = "https://competitor-a.com/privacy-policy"
        stored_page.final_url = stored_page.normalized_url
        stored_page.url = stored_page.normalized_url
        stored_page.title = "Privacy Policy"
        stored_page.h1 = "Privacy Policy"
        result = competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
            session,
            ids["site_id"],
            ids["competitor_a_id"],
            page_ids=[page.id],
        )
        session.commit()

        refreshed_page = session.get(SiteCompetitorPage, page.id)
        rows = session.scalars(
            select(SiteCompetitorSemanticCandidate)
            .where(SiteCompetitorSemanticCandidate.competitor_page_id == page.id)
            .order_by(SiteCompetitorSemanticCandidate.id.asc())
        ).all()
        assert result.excluded_pages == 1
        assert result.retired_candidates == 1
        assert refreshed_page is not None
        assert refreshed_page.semantic_eligible is False
        assert refreshed_page.semantic_exclusion_reason == "privacy_policy"
        assert len(rows) == 1
        assert rows[0].current is False


def test_refresh_competitor_semantic_foundation_excludes_utility_and_error_pages(sqlite_session_factory) -> None:
    ids = _seed_semantic_site(sqlite_session_factory)
    with sqlite_session_factory() as session:
        utility_page = _create_competitor_page(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            url="https://competitor-a.com/tools/seo-brief-generator",
            title="SEO Brief Generator",
            h1="SEO Brief Generator",
            page_type="utility",
            page_bucket="utility",
            word_count=260,
            schema_types_json=["WebApplication"],
        )
        error_page = _create_competitor_page(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            url="https://competitor-a.com/server-error",
            title="Server Error",
            h1="Server Error",
            status_code=500,
            word_count=240,
            schema_types_json=["WebPage"],
        )
        session.commit()

    with sqlite_session_factory() as session:
        result = competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
            session,
            ids["site_id"],
            ids["competitor_a_id"],
            page_ids=[utility_page.id, error_page.id],
        )
        session.commit()

        utility_page = session.get(SiteCompetitorPage, utility_page.id)
        error_page = session.get(SiteCompetitorPage, error_page.id)
        assert result.excluded_pages == 2
        assert utility_page is not None
        assert utility_page.semantic_eligible is False
        assert utility_page.semantic_exclusion_reason == "utility_page"
        assert error_page is not None
        assert error_page.semantic_eligible is False
        assert error_page.semantic_exclusion_reason == "error_like"


def test_refresh_competitor_semantic_foundation_marks_weak_evidence_pages_and_stores_debug_signals(sqlite_session_factory) -> None:
    ids = _seed_semantic_site(sqlite_session_factory)
    with sqlite_session_factory() as session:
        about_page = _create_competitor_page(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            url="https://competitor-a.com/o-nas",
            title="O nas",
            h1="O nas",
            page_type="about",
            page_bucket="trust",
            word_count=240,
            visible_text="Poznaj zespol kliniki, historie marki i partnerow." * 8,
        )
        session.commit()

    with sqlite_session_factory() as session:
        result = competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
            session,
            ids["site_id"],
            ids["competitor_a_id"],
            page_ids=[about_page.id],
        )
        session.commit()

        stored_page = session.get(SiteCompetitorPage, about_page.id)
        assert result.excluded_pages == 1
        assert stored_page is not None
        assert stored_page.semantic_eligible is False
        assert stored_page.semantic_exclusion_reason == "weak_about"
        assert stored_page.fetch_diagnostics_json["weak_evidence_flag"] is True
        assert stored_page.fetch_diagnostics_json["weak_evidence_reason"] == "weak_about"
        assert "dominant_topic_strength" in stored_page.fetch_diagnostics_json


def test_list_competitor_merge_candidates_returns_ranked_matches(sqlite_session_factory) -> None:
    ids = _seed_semantic_site(sqlite_session_factory)
    with sqlite_session_factory() as session:
        source_page = _create_competitor_page(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            url="https://competitor-a.com/local-seo",
            title="Local SEO Services",
            h1="Local SEO Services",
            word_count=240,
            schema_types_json=["Service"],
        )
        exact_page = _create_competitor_page(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_b_id"],
            url="https://competitor-b.com/local-seo",
            title="Local SEO Services",
            h1="Local SEO Services",
            word_count=210,
            schema_types_json=["Service"],
        )
        partial_page = _create_competitor_page(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_b_id"],
            url="https://competitor-b.com/local-seo-guide",
            title="Local SEO Guide",
            h1="Local SEO Guide",
            page_type="blog_article",
            page_bucket="informational",
            word_count=240,
            schema_types_json=["Article"],
        )
        ignored_page = _create_competitor_page(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_b_id"],
            url="https://competitor-b.com/contact",
            title="Contact",
            h1="Contact",
            page_type="contact",
            page_bucket="trust",
            visible_text="Call us.",
            word_count=12,
        )
        competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
            session,
            ids["site_id"],
            ids["competitor_a_id"],
            page_ids=[source_page.id],
        )
        competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
            session,
            ids["site_id"],
            ids["competitor_b_id"],
            page_ids=[exact_page.id, partial_page.id, ignored_page.id],
        )
        ignored_candidate = session.scalar(
            select(SiteCompetitorSemanticCandidate).where(
                SiteCompetitorSemanticCandidate.competitor_page_id == partial_page.id
            )
        )
        assert ignored_candidate is not None
        ignored_candidate.current = False
        session.commit()

    with sqlite_session_factory() as session:
        source_candidate = session.scalar(
            select(SiteCompetitorSemanticCandidate).where(
                SiteCompetitorSemanticCandidate.competitor_page_id == source_page.id
            )
        )
        assert source_candidate is not None
        groups = competitive_gap_semantic_service.list_competitor_merge_candidates(
            session,
            ids["site_id"],
            source_candidate_ids=[source_candidate.id],
        )
        assert len(groups) == 1
        assert [item.candidate_id for item in groups[0].candidates] == [
            session.scalar(
                select(SiteCompetitorSemanticCandidate.id).where(
                    SiteCompetitorSemanticCandidate.competitor_page_id == exact_page.id
                )
            )
        ]
        assert groups[0].candidates[0].exact_topic_key_match is True


def test_list_own_site_match_candidates_returns_ranked_pages(sqlite_session_factory) -> None:
    ids = _seed_semantic_site(sqlite_session_factory)
    with sqlite_session_factory() as session:
        source_page = _create_competitor_page(
            session,
            site_id=ids["site_id"],
            competitor_id=ids["competitor_a_id"],
            url="https://competitor-a.com/local-seo",
            title="Local SEO Services",
            h1="Local SEO Services",
            word_count=240,
            schema_types_json=["Service"],
        )
        competitive_gap_semantic_service.refresh_competitor_semantic_foundation(
            session,
            ids["site_id"],
            ids["competitor_a_id"],
            page_ids=[source_page.id],
        )
        session.commit()

    with sqlite_session_factory() as session:
        source_candidate = session.scalar(
            select(SiteCompetitorSemanticCandidate).where(
                SiteCompetitorSemanticCandidate.competitor_page_id == source_page.id
            )
        )
        assert source_candidate is not None
        groups = competitive_gap_semantic_service.list_own_site_match_candidates(
            session,
            ids["site_id"],
            ids["crawl_job_id"],
            source_candidate_ids=[source_candidate.id],
        )
        assert len(groups) == 1
        assert groups[0].candidates
        assert groups[0].candidates[0].page_id == ids["service_page_id"]
        assert groups[0].candidates[0].shared_primary_tokens >= 1
        assert groups[0].candidates[0].same_page_family is True
