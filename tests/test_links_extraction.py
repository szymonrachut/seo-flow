from __future__ import annotations

from scrapy.http import HtmlResponse, Request

from app.crawler.extraction.links_extractor import extract_links


def build_html_response(url: str, html: str) -> HtmlResponse:
    request = Request(url=url)
    return HtmlResponse(url=url, request=request, body=html.encode("utf-8"), encoding="utf-8")


def test_link_classification_internal_and_external() -> None:
    response = build_html_response(
        url="https://example.com",
        html="""
        <html>
          <body>
            <a href="/internal-page">Internal</a>
            <a href="https://other-domain.com/page">External</a>
          </body>
        </html>
        """,
    )

    links = extract_links(
        response=response,
        site_registered_domain="example.com",
        blocked_extensions=(".pdf", ".png"),
    )

    assert len(links) == 2

    internal = next(link for link in links if link.target_url == "https://example.com/internal-page")
    external = next(link for link in links if link.target_url == "https://other-domain.com/page")

    assert internal.is_internal is True
    assert internal.should_crawl is True

    assert external.is_internal is False
    assert external.should_crawl is False


def test_anchor_text_cleaning_rel_and_empty_anchor_behavior() -> None:
    response = build_html_response(
        url="https://example.com",
        html="""
        <html>
          <body>
            <a href="/with-spaces" rel="nofollow   noopener">  Oferta
              Premium
            </a>
            <a href="/empty-anchor">    </a>
          </body>
        </html>
        """,
    )

    links = extract_links(
        response=response,
        site_registered_domain="example.com",
        blocked_extensions=(".pdf", ".png"),
    )

    assert len(links) == 2

    first = next(link for link in links if link.target_url == "https://example.com/with-spaces")
    empty = next(link for link in links if link.target_url == "https://example.com/empty-anchor")

    assert first.anchor_text == "Oferta Premium"
    assert first.rel_attr == "nofollow noopener"
    assert first.is_nofollow is True

    # ETAP 1: pusty anchor jest przechowywany jako pusty string.
    assert empty.anchor_text == ""
