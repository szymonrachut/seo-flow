from __future__ import annotations

from app.db.models import CrawlJob, CrawlJobStatus, Link, Page, Site
from app.services.audit_service import build_audit_report


def _make_page(crawl_job_id: int, path: str, **overrides) -> Page:
    url = f"https://example.com{path}"
    default_title = f"Stable title for {path} page coverage"
    default_meta_description = f"Stable meta description for {path} page used in audit coverage and long enough."
    defaults = {
        "crawl_job_id": crawl_job_id,
        "url": url,
        "normalized_url": url,
        "final_url": url,
        "status_code": 200,
        "title": default_title,
        "title_length": len(default_title),
        "meta_description": default_meta_description,
        "meta_description_length": len(default_meta_description),
        "h1": f"H1 {path}",
        "h1_count": 1,
        "h2_count": 1,
        "canonical_url": url,
        "robots_meta": "index,follow",
        "content_type": "text/html; charset=utf-8",
        "word_count": 220,
        "content_text_hash": f"hash-{path.strip('/')}",
        "images_count": 2,
        "images_missing_alt_count": 0,
        "html_size_bytes": 24_000,
        "response_time_ms": 20,
        "is_internal": True,
        "depth": 1,
        "fetched_at": None,
        "error_message": None,
    }
    defaults.update(overrides)
    return Page(**defaults)


def seed_stage4_audit_job(session) -> int:
    site = Site(root_url="https://example.com/", domain="example.com")
    session.add(site)
    session.flush()

    crawl_job = CrawlJob(site_id=site.id, status=CrawlJobStatus.FINISHED, settings_json={}, stats_json={})
    session.add(crawl_job)
    session.flush()

    pages = {
        "home": _make_page(crawl_job.id, "/"),
        "missing_title": _make_page(
            crawl_job.id,
            "/missing-title",
            title=None,
            title_length=None,
            content_text_hash="hash-missing-title",
        ),
        "title_short": _make_page(
            crawl_job.id,
            "/title-short",
            title="Short title",
            title_length=11,
            content_text_hash="hash-title-short",
        ),
        "title_long": _make_page(
            crawl_job.id,
            "/title-long",
            title="This is a very long title that clearly exceeds the sixty character default threshold",
            title_length=82,
            meta_description="Too short meta",
            meta_description_length=14,
            h1_count=2,
            h2_count=0,
            canonical_url="https://example.com/canonical-missing",
            content_text_hash="hash-shared-content",
            images_count=3,
        ),
        "missing_meta": _make_page(
            crawl_job.id,
            "/missing-meta",
            meta_description=None,
            meta_description_length=None,
            h1=None,
            h1_count=0,
            h2_count=2,
            canonical_url=None,
            robots_meta="noindex,follow",
            word_count=90,
            images_count=0,
            html_size_bytes=620_000,
            content_text_hash="hash-missing-meta",
        ),
        "meta_short": _make_page(
            crawl_job.id,
            "/meta-short",
            meta_description="Too short meta",
            meta_description_length=14,
            content_text_hash="hash-meta-short",
        ),
        "meta_long": _make_page(
            crawl_job.id,
            "/meta-long",
            meta_description="x" * 170,
            meta_description_length=170,
            images_count=0,
            content_text_hash="hash-meta-long",
        ),
        "duplicate_a": _make_page(
            crawl_job.id,
            "/duplicate-a",
            title="Shared title",
            title_length=12,
            meta_description="Shared meta description used in the duplicate group for stable audit coverage.",
            meta_description_length=77,
            canonical_url="https://example.com/redirect-source",
            images_missing_alt_count=1,
            content_text_hash="hash-shared-content",
        ),
        "duplicate_b": _make_page(
            crawl_job.id,
            "/duplicate-b",
            title="Shared title",
            title_length=12,
            meta_description="Shared meta description used in the duplicate group for stable audit coverage.",
            meta_description_length=77,
            canonical_url="https://example.com/broken-target",
            content_text_hash="hash-duplicate-b",
        ),
        "redirect_source": _make_page(
            crawl_job.id,
            "/redirect-source",
            final_url="https://example.com/redirect-final",
            canonical_url="https://example.com/redirect-final",
            content_text_hash="hash-redirect-source",
        ),
        "redirect_final": _make_page(
            crawl_job.id,
            "/redirect-final",
            title="Canonical final page",
            title_length=20,
            meta_description="Canonical final target with enough text for a normal page classification.",
            meta_description_length=70,
            content_text_hash="hash-redirect-final",
        ),
        "broken_target": _make_page(
            crawl_job.id,
            "/broken-target",
            status_code=404,
            error_message="HTTP 404",
            canonical_url="https://example.com/broken-target",
            content_text_hash="hash-broken-target",
        ),
        "chain_start": _make_page(
            crawl_job.id,
            "/chain-start",
            final_url="https://example.com/chain-mid",
            canonical_url="https://example.com/chain-mid",
            content_text_hash="hash-chain-start",
        ),
        "chain_mid": _make_page(
            crawl_job.id,
            "/chain-mid",
            final_url="https://example.com/chain-final",
            canonical_url="https://example.com/chain-final",
            content_text_hash="hash-chain-mid",
        ),
        "chain_final": _make_page(
            crawl_job.id,
            "/chain-final",
            canonical_url="https://example.com/chain-final",
            content_text_hash="hash-chain-final",
        ),
    }
    session.add_all(list(pages.values()))
    session.flush()

    links = [
        Link(
            crawl_job_id=crawl_job.id,
            source_page_id=pages["home"].id,
            source_url=pages["home"].url,
            target_url=pages["broken_target"].url,
            target_normalized_url=pages["broken_target"].normalized_url,
            target_domain="example.com",
            anchor_text="Broken target",
            rel_attr="",
            is_nofollow=False,
            is_internal=True,
        ),
        Link(
            crawl_job_id=crawl_job.id,
            source_page_id=pages["home"].id,
            source_url=pages["home"].url,
            target_url=pages["redirect_source"].url,
            target_normalized_url=pages["redirect_source"].normalized_url,
            target_domain="example.com",
            anchor_text="Redirect source",
            rel_attr="",
            is_nofollow=False,
            is_internal=True,
        ),
        Link(
            crawl_job_id=crawl_job.id,
            source_page_id=pages["home"].id,
            source_url=pages["home"].url,
            target_url="https://example.com/unresolved",
            target_normalized_url="https://example.com/unresolved",
            target_domain="example.com",
            anchor_text="Unresolved target",
            rel_attr="",
            is_nofollow=False,
            is_internal=True,
        ),
        Link(
            crawl_job_id=crawl_job.id,
            source_page_id=pages["home"].id,
            source_url=pages["home"].url,
            target_url=pages["missing_meta"].url,
            target_normalized_url=pages["missing_meta"].normalized_url,
            target_domain="example.com",
            anchor_text="Noindex target",
            rel_attr="",
            is_nofollow=False,
            is_internal=True,
        ),
        Link(
            crawl_job_id=crawl_job.id,
            source_page_id=pages["home"].id,
            source_url=pages["home"].url,
            target_url=pages["duplicate_a"].url,
            target_normalized_url=pages["duplicate_a"].normalized_url,
            target_domain="example.com",
            anchor_text="Canonicalized target",
            rel_attr="",
            is_nofollow=False,
            is_internal=True,
        ),
        Link(
            crawl_job_id=crawl_job.id,
            source_page_id=pages["home"].id,
            source_url=pages["home"].url,
            target_url=pages["chain_start"].url,
            target_normalized_url=pages["chain_start"].normalized_url,
            target_domain="example.com",
            anchor_text="Redirect chain target",
            rel_attr="",
            is_nofollow=False,
            is_internal=True,
        ),
    ]
    session.add_all(links)
    session.commit()
    return crawl_job.id


def test_title_and_meta_quality_signals(db_session) -> None:
    crawl_job_id = seed_stage4_audit_job(db_session)
    report = build_audit_report(db_session, crawl_job_id)

    assert report["summary"]["pages_missing_title"] == 1
    assert report["summary"]["pages_title_too_short"] == 4
    assert report["summary"]["pages_title_too_long"] == 1
    assert report["summary"]["pages_missing_meta_description"] == 1
    assert report["summary"]["pages_meta_description_too_short"] == 2
    assert report["summary"]["pages_meta_description_too_long"] == 1
    assert report["summary"]["pages_duplicate_title_groups"] == 1
    assert report["summary"]["pages_duplicate_meta_description_groups"] == 2


def test_headings_signals(db_session) -> None:
    crawl_job_id = seed_stage4_audit_job(db_session)
    report = build_audit_report(db_session, crawl_job_id)

    assert report["summary"]["pages_missing_h1"] == 1
    assert report["summary"]["pages_multiple_h1"] == 1
    assert report["summary"]["pages_missing_h2"] == 1


def test_canonical_and_indexability_signals(db_session) -> None:
    crawl_job_id = seed_stage4_audit_job(db_session)
    report = build_audit_report(db_session, crawl_job_id)

    assert report["summary"]["pages_missing_canonical"] == 1
    assert report["summary"]["pages_self_canonical"] >= 3
    assert report["summary"]["pages_canonical_to_other_url"] == 3
    assert report["summary"]["pages_canonical_to_non_200"] == 3
    assert report["summary"]["pages_canonical_to_redirect"] == 4
    assert report["summary"]["pages_noindex_like"] == 1
    assert report["summary"]["pages_non_indexable_like"] == 2


def test_link_health_signals(db_session) -> None:
    crawl_job_id = seed_stage4_audit_job(db_session)
    report = build_audit_report(db_session, crawl_job_id)

    assert report["summary"]["broken_internal_links"] == 1
    assert report["summary"]["unresolved_internal_targets"] == 1
    assert report["summary"]["redirecting_internal_links"] == 2
    assert report["summary"]["internal_links_to_noindex_like_pages"] == 2
    assert report["summary"]["internal_links_to_canonicalized_pages"] == 1
    assert report["summary"]["redirect_chains_internal"] == 1


def test_content_and_media_signals(db_session) -> None:
    crawl_job_id = seed_stage4_audit_job(db_session)
    report = build_audit_report(db_session, crawl_job_id)

    assert report["summary"]["pages_thin_content"] == 1
    assert report["summary"]["pages_duplicate_content_groups"] == 1
    assert report["summary"]["pages_with_missing_alt_images"] == 1
    assert report["summary"]["pages_with_no_images"] == 2
    assert report["summary"]["oversized_pages"] == 1

    duplicate_group = report["pages_duplicate_content"][0]
    assert duplicate_group["count"] == 2
    assert {page["normalized_url"] for page in duplicate_group["pages"]} == {
        "https://example.com/title-long",
        "https://example.com/duplicate-a",
    }
