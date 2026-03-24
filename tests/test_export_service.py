from __future__ import annotations

import csv
import io

from app.services.export_service import build_audit_csv, build_links_csv, build_pages_csv
from tests.test_audit_service import seed_stage4_audit_job


def test_pages_csv_export_contains_stage4_columns_and_filtered_rows(db_session) -> None:
    crawl_job_id = seed_stage4_audit_job(db_session)
    csv_content = build_pages_csv(db_session, crawl_job_id, thin_content=True, sort_by="word_count", sort_order="asc")

    plain = csv_content.lstrip("\ufeff")
    assert plain.startswith(
        "id,crawl_job_id,url,normalized_url,final_url,status_code,title,title_length,meta_description,"
        "meta_description_length,h1,h1_count,h2_count,canonical_url"
    )

    rows = list(csv.DictReader(io.StringIO(plain)))
    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.com/missing-meta"
    assert rows[0]["thin_content"] == "True"
    assert rows[0]["html_size_bytes"] == "620000"
    assert rows[0]["page_type"] != ""
    assert rows[0]["page_bucket"] != ""
    assert rows[0]["page_type_confidence"] != ""
    assert rows[0]["page_type_version"] != ""


def test_links_csv_export_contains_stage4_columns_and_filtered_rows(db_session) -> None:
    crawl_job_id = seed_stage4_audit_job(db_session)
    csv_content = build_links_csv(db_session, crawl_job_id, redirect_chain=True)

    plain = csv_content.lstrip("\ufeff")
    assert plain.startswith(
        "id,crawl_job_id,source_page_id,source_url,target_url,target_normalized_url,target_domain,anchor_text,"
        "rel_attr,is_nofollow,is_internal,target_status_code,final_url,redirect_hops"
    )

    rows = list(csv.DictReader(io.StringIO(plain)))
    assert len(rows) == 1
    assert rows[0]["target_url"] == "https://example.com/chain-start"
    assert rows[0]["redirect_chain"] == "True"
    assert rows[0]["redirect_hops"] == "2"


def test_audit_csv_export_contains_stage4_sections(db_session) -> None:
    crawl_job_id = seed_stage4_audit_job(db_session)
    csv_content = build_audit_csv(db_session, crawl_job_id)
    plain = csv_content.lstrip("\ufeff")

    assert plain.startswith("issue_type,key,value,url,details")
    assert "summary,pages_title_too_short,4,," in plain
    assert "pages_canonical_to_non_200,page_id" in plain
    assert "pages_duplicate_content,hash-shared-content,2" in plain
    assert "internal_links_to_noindex_like_pages,target_url,https://example.com/missing-meta,https://example.com/," in plain
