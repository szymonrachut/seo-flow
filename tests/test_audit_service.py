from __future__ import annotations

from app.db.models import CrawlJob, CrawlJobStatus, Link, Page, Site
from app.services.audit_service import build_audit_report


def seed_audit_job(session) -> int:
    site = Site(root_url="https://example.com/", domain="example.com")
    session.add(site)
    session.flush()

    crawl_job = CrawlJob(site_id=site.id, status=CrawlJobStatus.FINISHED, settings_json={}, stats_json={})
    session.add(crawl_job)
    session.flush()

    pages = {
        "home": Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/",
            normalized_url="https://example.com/",
            final_url="https://example.com/",
            status_code=200,
            title="Home",
            meta_description="Home desc",
            h1="Home H1",
            canonical_url="https://example.com/",
            robots_meta=None,
            content_type="text/html; charset=utf-8",
            response_time_ms=21,
            is_internal=True,
            depth=0,
            fetched_at=None,
            error_message=None,
        ),
        "missing_title": Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/missing-title",
            normalized_url="https://example.com/missing-title",
            final_url="https://example.com/missing-title",
            status_code=200,
            title=None,
            meta_description="Meta present",
            h1="H1 present",
            canonical_url=None,
            robots_meta=None,
            content_type="text/html",
            response_time_ms=18,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        ),
        "missing_meta": Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/missing-meta",
            normalized_url="https://example.com/missing-meta",
            final_url="https://example.com/missing-meta",
            status_code=200,
            title="Meta missing",
            meta_description=None,
            h1="H1 present",
            canonical_url=None,
            robots_meta=None,
            content_type="text/html",
            response_time_ms=17,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        ),
        "missing_h1": Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/missing-h1",
            normalized_url="https://example.com/missing-h1",
            final_url="https://example.com/missing-h1",
            status_code=200,
            title="H1 missing",
            meta_description="Meta present",
            h1=None,
            canonical_url=None,
            robots_meta=None,
            content_type="text/html",
            response_time_ms=19,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        ),
        "dup_a": Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/dup-a",
            normalized_url="https://example.com/dup-a",
            final_url="https://example.com/dup-a",
            status_code=200,
            title="Duplicate Title",
            meta_description="Duplicate Meta",
            h1="Dup A",
            canonical_url=None,
            robots_meta=None,
            content_type="text/html",
            response_time_ms=15,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        ),
        "dup_b": Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/dup-b",
            normalized_url="https://example.com/dup-b",
            final_url="https://example.com/dup-b",
            status_code=200,
            title="Duplicate Title",
            meta_description="Duplicate Meta",
            h1="Dup B",
            canonical_url=None,
            robots_meta=None,
            content_type="text/html",
            response_time_ms=16,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        ),
        "broken": Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/broken",
            normalized_url="https://example.com/broken",
            final_url="https://example.com/broken",
            status_code=404,
            title="Broken",
            meta_description="Broken",
            h1="Broken",
            canonical_url=None,
            robots_meta=None,
            content_type="text/html",
            response_time_ms=14,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message="HTTP 404",
        ),
        "redir": Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/redir",
            normalized_url="https://example.com/redir",
            final_url="https://example.com/final",
            status_code=301,
            title="Redirect",
            meta_description="Redirect",
            h1="Redirect",
            canonical_url=None,
            robots_meta=None,
            content_type="text/html",
            response_time_ms=22,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        ),
        "final": Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/final",
            normalized_url="https://example.com/final",
            final_url="https://example.com/final",
            status_code=200,
            title="Final",
            meta_description="Final",
            h1="Final",
            canonical_url=None,
            robots_meta=None,
            content_type="text/html",
            response_time_ms=13,
            is_internal=True,
            depth=2,
            fetched_at=None,
            error_message=None,
        ),
        "noindex": Page(
            crawl_job_id=crawl_job.id,
            url="https://example.com/noindex",
            normalized_url="https://example.com/noindex",
            final_url="https://example.com/noindex",
            status_code=200,
            title="Noindex",
            meta_description="Noindex",
            h1="Noindex",
            canonical_url=None,
            robots_meta="noindex, follow",
            content_type="text/html",
            response_time_ms=11,
            is_internal=True,
            depth=1,
            fetched_at=None,
            error_message=None,
        ),
    }
    session.add_all(list(pages.values()))
    session.flush()

    links = [
        Link(
            crawl_job_id=crawl_job.id,
            source_page_id=pages["home"].id,
            source_url=pages["home"].url,
            target_url=pages["broken"].url,
            target_normalized_url=pages["broken"].normalized_url,
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
            target_url=pages["redir"].url,
            target_normalized_url=pages["redir"].normalized_url,
            target_domain="example.com",
            anchor_text="Redirect target",
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
    ]
    session.add_all(links)
    session.commit()

    return crawl_job.id


def test_report_missing_title(db_session) -> None:
    crawl_job_id = seed_audit_job(db_session)
    report = build_audit_report(db_session, crawl_job_id)
    assert report["summary"]["pages_missing_title"] == 1
    assert report["pages_missing_title"][0]["normalized_url"] == "https://example.com/missing-title"


def test_report_missing_meta_description(db_session) -> None:
    crawl_job_id = seed_audit_job(db_session)
    report = build_audit_report(db_session, crawl_job_id)
    assert report["summary"]["pages_missing_meta_description"] == 1
    assert report["pages_missing_meta_description"][0]["normalized_url"] == "https://example.com/missing-meta"


def test_report_missing_h1(db_session) -> None:
    crawl_job_id = seed_audit_job(db_session)
    report = build_audit_report(db_session, crawl_job_id)
    assert report["summary"]["pages_missing_h1"] == 1
    assert report["pages_missing_h1"][0]["normalized_url"] == "https://example.com/missing-h1"


def test_report_duplicate_title(db_session) -> None:
    crawl_job_id = seed_audit_job(db_session)
    report = build_audit_report(db_session, crawl_job_id)
    assert report["summary"]["pages_duplicate_title_groups"] == 1
    group = report["pages_duplicate_title"][0]
    assert group["value"] == "Duplicate Title"
    assert group["count"] == 2


def test_report_duplicate_meta_description(db_session) -> None:
    crawl_job_id = seed_audit_job(db_session)
    report = build_audit_report(db_session, crawl_job_id)
    assert report["summary"]["pages_duplicate_meta_description_groups"] == 2
    duplicate_meta_group = next(
        group for group in report["pages_duplicate_meta_description"] if group["value"] == "Duplicate Meta"
    )
    assert duplicate_meta_group["count"] == 2


def test_report_broken_internal_links(db_session) -> None:
    crawl_job_id = seed_audit_job(db_session)
    report = build_audit_report(db_session, crawl_job_id)
    assert report["summary"]["broken_internal_links"] == 1
    finding = report["broken_internal_links"][0]
    assert finding["target_normalized_url"] == "https://example.com/broken"
    assert finding["target_status_code"] == 404


def test_report_redirecting_internal_links(db_session) -> None:
    crawl_job_id = seed_audit_job(db_session)
    report = build_audit_report(db_session, crawl_job_id)
    assert report["summary"]["redirecting_internal_links"] == 1
    finding = report["redirecting_internal_links"][0]
    assert finding["target_normalized_url"] == "https://example.com/redir"
    assert finding["final_url"] == "https://example.com/final"
