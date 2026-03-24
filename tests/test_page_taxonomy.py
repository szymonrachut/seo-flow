from __future__ import annotations

import csv
import io

import pytest

from app.db.models import CrawlJob, CrawlJobStatus, Page, Site
from app.services import page_taxonomy_service
from app.services.export_service import build_pages_csv


def _make_page(crawl_job_id: int, path: str, **overrides) -> Page:
    url = f"https://example.com{path}"
    defaults = {
        "crawl_job_id": crawl_job_id,
        "url": url,
        "normalized_url": url,
        "final_url": url,
        "status_code": 200,
        "title": f"Title for {path}",
        "meta_description": f"Meta description for {path}",
        "h1": f"H1 for {path}",
        "canonical_url": url,
        "content_type": "text/html",
        "is_internal": True,
        "depth": len([segment for segment in path.split("/") if segment]),
        "fetched_at": None,
        "error_message": None,
    }
    defaults.update(overrides)
    return Page(**defaults)


def seed_page_taxonomy_job(session_factory) -> int:
    with session_factory() as session:
        site = Site(root_url="https://example.com/", domain="example.com")
        session.add(site)
        session.flush()

        crawl_job = CrawlJob(site_id=site.id, status=CrawlJobStatus.FINISHED, settings_json={}, stats_json={})
        session.add(crawl_job)
        session.flush()

        session.add_all(
            [
                _make_page(
                    crawl_job.id,
                    "/",
                    title="Example home",
                    h1="Home",
                    schema_types_json=["Organization"],
                ),
                _make_page(
                    crawl_job.id,
                    "/kategoria/ogrod",
                    title="Kategoria ogrod",
                    h1="Kategoria ogrod",
                    schema_types_json=["CollectionPage"],
                ),
                _make_page(
                    crawl_job.id,
                    "/produkt/kosiarka-x1",
                    title="Produkt Kosiarka X1",
                    h1="Produkt Kosiarka X1",
                    schema_types_json=["Product"],
                ),
                _make_page(
                    crawl_job.id,
                    "/uslugi/audyt-seo",
                    title="Uslugi SEO",
                    h1="Uslugi SEO",
                    schema_types_json=["Service"],
                ),
                _make_page(
                    crawl_job.id,
                    "/blog/seo-audit-guide",
                    title="SEO audit guide",
                    h1="SEO audit guide",
                    schema_types_json=["Article"],
                ),
                _make_page(
                    crawl_job.id,
                    "/blog",
                    title="Blog",
                    h1="Blog",
                ),
                _make_page(
                    crawl_job.id,
                    "/kontakt",
                    title="Kontakt",
                    h1="Kontakt",
                    schema_types_json=["ContactPage"],
                ),
                _make_page(
                    crawl_job.id,
                    "/faq",
                    title="FAQ",
                    h1="FAQ",
                    schema_types_json=["FAQPage"],
                ),
                _make_page(
                    crawl_job.id,
                    "/lokalizacje/warszawa",
                    title="Warszawa showroom",
                    h1="Warszawa showroom",
                    schema_types_json=["LocalBusiness"],
                ),
                _make_page(
                    crawl_job.id,
                    "/polityka-prywatnosci",
                    title="Polityka prywatnosci",
                    h1="Polityka prywatnosci",
                ),
                _make_page(
                    crawl_job.id,
                    "/szukaj",
                    title="Search results",
                    h1="Search results",
                    schema_types_json=["SearchResultsPage"],
                ),
            ]
        )
        session.commit()
        return crawl_job.id


@pytest.mark.parametrize(
    ("kwargs", "expected_type", "expected_bucket"),
    [
        ({"url": "https://example.com/", "title": "Home", "h1": "Home"}, "home", "commercial"),
        (
            {
                "url": "https://example.com/kategoria/ogrod",
                "title": "Kategoria ogrod",
                "h1": "Kategoria ogrod",
                "schema_types": ["CollectionPage"],
            },
            "category",
            "commercial",
        ),
        (
            {
                "url": "https://example.com/produkt/kosiarka-x1",
                "title": "Produkt Kosiarka X1",
                "h1": "Produkt Kosiarka X1",
                "schema_types": ["Product"],
            },
            "product",
            "commercial",
        ),
        (
            {
                "url": "https://example.com/uslugi/audyt-seo",
                "title": "Uslugi SEO",
                "h1": "Uslugi SEO",
                "schema_types": ["Service"],
            },
            "service",
            "commercial",
        ),
        (
            {
                "url": "https://example.com/blog/seo-audit-guide",
                "title": "SEO audit guide",
                "h1": "SEO audit guide",
                "schema_types": ["Article"],
            },
            "blog_article",
            "informational",
        ),
        (
            {
                "url": "https://example.com/kontakt",
                "title": "Kontakt",
                "h1": "Kontakt",
                "schema_types": ["ContactPage"],
            },
            "contact",
            "trust",
        ),
        (
            {
                "url": "https://example.com/faq",
                "title": "FAQ",
                "h1": "FAQ",
                "schema_types": ["FAQPage"],
            },
            "faq",
            "informational",
        ),
        (
            {
                "url": "https://example.com/polityka-prywatnosci",
                "title": "Polityka prywatnosci",
                "h1": "Polityka prywatnosci",
            },
            "legal",
            "trust",
        ),
        (
            {
                "url": "https://example.com/szukaj",
                "title": "Search results",
                "h1": "Search results",
                "schema_types": ["SearchResultsPage"],
            },
            "utility",
            "utility",
        ),
    ],
)
def test_page_taxonomy_classifier_matches_expected_rules(
    kwargs: dict[str, object],
    expected_type: str,
    expected_bucket: str,
) -> None:
    result = page_taxonomy_service.classify_page(**kwargs)
    assert result.page_type == expected_type
    assert result.page_bucket == expected_bucket


def test_page_taxonomy_classifier_returns_confidence_version_and_rationale() -> None:
    result = page_taxonomy_service.classify_page(
        url="https://example.com/produkt/kosiarka-x1",
        title="Produkt Kosiarka X1",
        h1="Produkt Kosiarka X1",
        schema_types=["Product"],
    )

    assert result.page_type == "product"
    assert result.page_type_confidence >= 0.8
    assert result.page_type_version == page_taxonomy_service.PAGE_TAXONOMY_VERSION
    assert result.page_type_rationale is not None


def test_pages_endpoint_supports_page_taxonomy_filters_and_persists_classification(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_page_taxonomy_job(sqlite_session_factory)

    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/pages",
        params={"page_type": "product", "page_size": 20},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert payload["items"][0]["page_type"] == "product"
    assert payload["items"][0]["page_bucket"] == "commercial"
    assert payload["items"][0]["page_type_version"] == page_taxonomy_service.PAGE_TAXONOMY_VERSION

    with sqlite_session_factory() as session:
        product_page = session.query(Page).filter(Page.crawl_job_id == crawl_job_id, Page.url.like("%/produkt/%")).one()
        assert product_page.page_type == "product"
        assert product_page.page_type_version == page_taxonomy_service.PAGE_TAXONOMY_VERSION

    response = api_client.get(
        f"/crawl-jobs/{crawl_job_id}/pages",
        params={"page_bucket": "informational", "sort_by": "page_type_confidence", "sort_order": "desc", "page_size": 20},
    )
    assert response.status_code == 200
    payload = response.json()
    returned_types = {item["page_type"] for item in payload["items"]}
    assert returned_types == {"blog_article", "blog_index", "faq"}
    confidences = [item["page_type_confidence"] for item in payload["items"]]
    assert confidences == sorted(confidences, reverse=True)


def test_page_taxonomy_summary_endpoint_counts_page_types_and_buckets(api_client, sqlite_session_factory) -> None:
    crawl_job_id = seed_page_taxonomy_job(sqlite_session_factory)

    response = api_client.get(f"/crawl-jobs/{crawl_job_id}/page-taxonomy/summary")
    assert response.status_code == 200
    payload = response.json()

    assert payload["crawl_job_id"] == crawl_job_id
    assert payload["page_type_version"] == page_taxonomy_service.PAGE_TAXONOMY_VERSION
    assert payload["counts_by_page_type"]["category"] == 1
    assert payload["counts_by_page_type"]["product"] == 1
    assert payload["counts_by_page_type"]["service"] == 1
    assert payload["counts_by_page_type"]["blog_article"] == 1
    assert payload["counts_by_page_type"]["utility"] == 1
    assert payload["counts_by_page_bucket"]["commercial"] == 5
    assert payload["counts_by_page_bucket"]["informational"] == 3
    assert payload["counts_by_page_bucket"]["utility"] == 1
    assert payload["counts_by_page_bucket"]["trust"] == 2


def test_pages_csv_export_includes_page_taxonomy_fields_and_filters(sqlite_session_factory) -> None:
    crawl_job_id = seed_page_taxonomy_job(sqlite_session_factory)

    with sqlite_session_factory() as session:
        csv_content = build_pages_csv(
            session,
            crawl_job_id,
            page_type="product",
            sort_by="page_type_confidence",
            sort_order="desc",
        )

    plain = csv_content.lstrip("\ufeff")
    rows = list(csv.DictReader(io.StringIO(plain)))

    assert "page_type" in plain
    assert "page_bucket" in plain
    assert "page_type_confidence" in plain
    assert "page_type_version" in plain
    assert "page_type_rationale" in plain
    assert len(rows) == 1
    assert rows[0]["page_type"] == "product"
    assert rows[0]["page_bucket"] == "commercial"
    assert rows[0]["page_type_version"] == page_taxonomy_service.PAGE_TAXONOMY_VERSION
