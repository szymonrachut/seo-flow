from app.crawler.normalization.urls import (
    extract_registered_domain,
    is_crawlable_document_url,
    is_internal_url,
    normalize_url,
    should_skip_href,
)


def test_normalize_url_basic_rules() -> None:
    normalized = normalize_url("HTTPS://WWW.Example.com/products/?b=2&a=1&a=&z=3#section")
    assert normalized == "https://www.example.com/products?a=1&b=2&z=3"


def test_normalize_url_rejects_non_http() -> None:
    assert normalize_url("mailto:test@example.com") is None
    assert normalize_url("javascript:void(0)") is None


def test_is_internal_url_by_registered_domain() -> None:
    domain = extract_registered_domain("https://example.com")
    assert domain == "example.com"
    assert is_internal_url("https://blog.example.com/page", site_registered_domain=domain)
    assert not is_internal_url("https://example.org/page", site_registered_domain=domain)


def test_should_skip_href_special_schemes() -> None:
    assert should_skip_href("#section")
    assert should_skip_href("mailto:team@example.com")
    assert should_skip_href("javascript:void(0)")
    assert not should_skip_href("/kontakt")


def test_crawlable_document_filter() -> None:
    blocked = (".pdf", ".png")
    assert is_crawlable_document_url("https://example.com/page", blocked_extensions=blocked)
    assert not is_crawlable_document_url("https://example.com/file.pdf", blocked_extensions=blocked)
