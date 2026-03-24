from __future__ import annotations

from collections.abc import Iterable

import pytest
import scrapy
from scrapy.http import HtmlResponse, Request

from app.crawler.normalization.urls import normalize_url
from app.crawler.scrapy_project.items import PageWithLinksItem
from app.crawler.scrapy_project.spiders.site_spider import SiteSpider

pytestmark = pytest.mark.slow


def build_response(url: str, html: str, depth: int = 0) -> HtmlResponse:
    normalized = normalize_url(url) or url
    request = Request(
        url=url,
        meta={
            "depth": depth,
            "requested_url": url,
            "normalized_url": normalized,
        },
    )
    return HtmlResponse(url=url, request=request, body=html.encode("utf-8"), encoding="utf-8")


def collect_outputs(outputs: Iterable[object]) -> tuple[list[scrapy.Request], list[PageWithLinksItem]]:
    requests: list[scrapy.Request] = []
    items: list[PageWithLinksItem] = []
    for output in outputs:
        if isinstance(output, scrapy.Request):
            requests.append(output)
        elif isinstance(output, PageWithLinksItem):
            items.append(output)
    return requests, items


def build_spider(monkeypatch) -> SiteSpider:
    monkeypatch.setattr(SiteSpider, "_load_existing_page_urls", lambda self: set())
    return SiteSpider(
        start_url="https://example.com",
        crawl_job_id=1,
        max_urls=20,
        max_depth=3,
        request_delay=0.0,
        site_registered_domain="example.com",
    )


def test_external_link_is_saved_but_not_added_to_queue(monkeypatch) -> None:
    spider = build_spider(monkeypatch)
    response = build_response(
        url="https://example.com",
        html="""
        <html><body>
          <a href="/internal-page">Internal</a>
          <a href="https://external.test/page">External</a>
        </body></html>
        """,
    )

    requests, items = collect_outputs(spider.parse(response))

    assert len(requests) == 1
    assert requests[0].url == "https://example.com/internal-page"

    assert len(items) == 1
    links = items[0]["links"]
    assert any(link["target_url"] == "https://example.com/internal-page" for link in links)
    assert any(link["target_url"] == "https://external.test/page" for link in links)


def test_queue_deduplication_by_normalized_url(monkeypatch) -> None:
    spider = build_spider(monkeypatch)
    response = build_response(
        url="https://example.com",
        html="""
        <html><body>
          <a href="/dup">Dup A</a>
          <a href="/dup/">Dup B</a>
          <a href="/dup#fragment">Dup C</a>
        </body></html>
        """,
    )

    requests, items = collect_outputs(spider.parse(response))

    assert len(requests) == 1
    assert requests[0].url == "https://example.com/dup"
    assert len(items) == 1
    assert len(items[0]["links"]) == 3
