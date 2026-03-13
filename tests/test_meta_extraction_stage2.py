from __future__ import annotations

from scrapy.http import HtmlResponse, Request

from app.crawler.extraction.meta_extractor import extract_canonical_url, extract_robots_meta


def build_response(url: str, html: str) -> HtmlResponse:
    request = Request(url=url)
    return HtmlResponse(url=url, request=request, body=html.encode("utf-8"), encoding="utf-8")


def test_extract_canonical_and_robots_meta() -> None:
    response = build_response(
        url="https://example.com/products?id=10",
        html="""
        <html>
          <head>
            <link rel="canonical" href="/products" />
            <meta name="robots" content="noindex, follow" />
          </head>
          <body>content</body>
        </html>
        """,
    )

    assert extract_canonical_url(response) == "https://example.com/products"
    assert extract_robots_meta(response) == "noindex, follow"
