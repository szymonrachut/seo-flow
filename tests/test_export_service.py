from __future__ import annotations

import csv
import io

from app.db.models import CrawlJob, CrawlJobStatus, Link, Page, Site
from app.services.export_service import build_audit_csv, build_links_csv, build_pages_csv


def seed_export_job(db_session) -> int:
    site = Site(root_url="https://example.com/", domain="example.com")
    db_session.add(site)
    db_session.flush()

    crawl_job = CrawlJob(site_id=site.id, status=CrawlJobStatus.FINISHED, settings_json={}, stats_json={})
    db_session.add(crawl_job)
    db_session.flush()

    home = Page(
        crawl_job_id=crawl_job.id,
        url="https://example.com/",
        normalized_url="https://example.com/",
        final_url="https://example.com/",
        status_code=200,
        title="Home",
        meta_description="Desc",
        h1="H1",
        canonical_url="https://example.com/",
        robots_meta="index,follow",
        content_type="text/html",
        response_time_ms=25,
        is_internal=True,
        depth=0,
        fetched_at=None,
        error_message=None,
    )
    broken = Page(
        crawl_job_id=crawl_job.id,
        url="https://example.com/broken",
        normalized_url="https://example.com/broken",
        final_url="https://example.com/broken",
        status_code=404,
        title=None,
        meta_description=None,
        h1=None,
        canonical_url=None,
        robots_meta="noindex",
        content_type="text/html",
        response_time_ms=30,
        is_internal=True,
        depth=1,
        fetched_at=None,
        error_message="HTTP 404",
    )
    db_session.add_all([home, broken])
    db_session.flush()

    db_session.add(
        Link(
            crawl_job_id=crawl_job.id,
            source_page_id=home.id,
            source_url=home.url,
            target_url=broken.url,
            target_normalized_url=broken.normalized_url,
            target_domain="example.com",
            anchor_text="Broken link",
            rel_attr="",
            is_nofollow=False,
            is_internal=True,
        )
    )
    db_session.commit()
    return crawl_job.id


def test_pages_csv_export_contains_headers_rows_order_and_bom(db_session) -> None:
    crawl_job_id = seed_export_job(db_session)
    csv_content = build_pages_csv(db_session, crawl_job_id)

    assert csv_content.startswith("\ufeffid,crawl_job_id,url,normalized_url,final_url,status_code,title,meta_description,h1,canonical_url,robots_meta,content_type,response_time_ms,is_internal,depth,fetched_at,error_message,created_at")
    rows = list(csv.DictReader(io.StringIO(csv_content.lstrip("\ufeff"))))
    assert len(rows) == 2
    assert rows[0]["url"] == "https://example.com/"
    assert rows[0]["canonical_url"] == "https://example.com/"


def test_links_csv_export_contains_headers_rows_order_and_bom(db_session) -> None:
    crawl_job_id = seed_export_job(db_session)
    csv_content = build_links_csv(db_session, crawl_job_id)

    assert csv_content.startswith("\ufeffid,crawl_job_id,source_page_id,source_url,target_url,target_normalized_url,target_domain,anchor_text,rel_attr,is_nofollow,is_internal,created_at")
    rows = list(csv.DictReader(io.StringIO(csv_content.lstrip("\ufeff"))))
    assert len(rows) == 1
    assert rows[0]["target_url"] == "https://example.com/broken"
    assert rows[0]["anchor_text"] == "Broken link"


def test_audit_csv_export_contains_issue_type_and_record_data(db_session) -> None:
    crawl_job_id = seed_export_job(db_session)
    csv_content = build_audit_csv(db_session, crawl_job_id)
    plain = csv_content.lstrip("\ufeff")

    assert plain.startswith("issue_type,key,value,url,details")
    assert "summary,total_pages,2,," in plain
    assert "pages_missing_title,page_id" in plain
    assert "broken_internal_links,target_url,https://example.com/broken,https://example.com/," in plain
