from __future__ import annotations

from tests.test_trends_compare import seed_trends_jobs


def test_site_pages_compare_endpoint_uses_workspace_context(api_client, sqlite_session_factory) -> None:
    seed = seed_trends_jobs(sqlite_session_factory)

    response = api_client.get(
        f"/sites/{seed['site_id']}/pages",
        params={
            "active_crawl_id": seed["target_job_id"],
            "baseline_crawl_id": seed["baseline_job_id"],
            "change_type": "improved,new",
            "sort_by": "delta_priority_score",
            "sort_order": "desc",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["context"]["active_crawl_id"] == seed["target_job_id"]
    assert payload["context"]["baseline_crawl_id"] == seed["baseline_job_id"]
    assert payload["context"]["compare_available"] is True
    assert payload["summary"]["new_urls"] == 1
    assert payload["summary"]["missing_urls"] == 1
    assert payload["summary"]["improved_urls"] >= 1
    assert {item["change_type"] for item in payload["items"]}.issubset({"improved", "new"})
    assert any(item["url"] == "https://example.com/improved" for item in payload["items"])
    assert any(item["change_type"] == "new" for item in payload["items"])
    improved_row = next(item for item in payload["items"] if item["url"] == "https://example.com/improved")
    assert improved_row["internal_linking_trend"] == "improved"


def test_site_audit_and_opportunities_compare_endpoints(api_client, sqlite_session_factory) -> None:
    seed = seed_trends_jobs(sqlite_session_factory)

    audit_response = api_client.get(
        f"/sites/{seed['site_id']}/audit",
        params={
            "active_crawl_id": seed["target_job_id"],
            "baseline_crawl_id": seed["baseline_job_id"],
            "status": "resolved,worsened",
        },
    )
    assert audit_response.status_code == 200
    audit_payload = audit_response.json()
    assert audit_payload["summary"]["resolved_sections"] >= 1
    assert audit_payload["summary"]["worsened_sections"] >= 1
    assert all(section["status"] in {"resolved", "worsened"} for section in audit_payload["sections"])
    assert any(section["status"] == "worsened" for section in audit_payload["sections"])
    assert any(section["status"] == "resolved" for section in audit_payload["sections"])

    opportunities_response = api_client.get(
        f"/sites/{seed['site_id']}/opportunities",
        params={
            "active_crawl_id": seed["target_job_id"],
            "baseline_crawl_id": seed["baseline_job_id"],
            "change_kind": "NEW_OPPORTUNITY,PRIORITY_UP",
            "sort_by": "delta_priority_score",
            "sort_order": "desc",
        },
    )
    assert opportunities_response.status_code == 200
    opportunities_payload = opportunities_response.json()
    assert opportunities_payload["summary"]["new_opportunity_urls"] >= 1
    assert all(
        {"NEW_OPPORTUNITY", "PRIORITY_UP"} & set(row["highlights"]) for row in opportunities_payload["items"]
    )


def test_site_internal_linking_compare_endpoint(api_client, sqlite_session_factory) -> None:
    seed = seed_trends_jobs(sqlite_session_factory)

    response = api_client.get(
        f"/sites/{seed['site_id']}/internal-linking",
        params={
            "active_crawl_id": seed["target_job_id"],
            "baseline_crawl_id": seed["baseline_job_id"],
            "compare_kind": "LINKING_PAGES_UP,LINK_EQUITY_IMPROVED",
            "sort_by": "delta_incoming_follow_linking_pages",
            "sort_order": "desc",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["summary"]["linking_pages_up_urls"] >= 1
    assert payload["items"][0]["url"] == "https://example.com/improved"
    assert {"LINKING_PAGES_UP", "LINK_EQUITY_IMPROVED"} & set(payload["items"][0]["highlights"])
    assert payload["items"][0]["change_type"] == "improved"
