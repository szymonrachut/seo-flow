from __future__ import annotations

from scrapy.http import HtmlResponse, Request

from app.crawler.rendering.detection import detect_js_heavy_page
from app.crawler.scrapy_project.items import PageWithLinksItem
from app.crawler.scrapy_project.spiders import site_spider as site_spider_module
from app.crawler.scrapy_project.spiders.site_spider import SiteSpider
from app.db.models import CrawlJob, CrawlJobStatus, Site


def _seed_spider_job(session_factory) -> int:
    with session_factory() as session:
        site = Site(root_url="https://example.com/", domain="example.com")
        session.add(site)
        session.flush()

        crawl_job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.PENDING,
            settings_json={"start_url": "https://example.com/"},
            stats_json={},
        )
        session.add(crawl_job)
        session.commit()
        return crawl_job.id


def _make_spider(sqlite_session_factory, monkeypatch, *, render_mode: str) -> SiteSpider:
    crawl_job_id = _seed_spider_job(sqlite_session_factory)
    monkeypatch.setattr(site_spider_module, "SessionLocal", sqlite_session_factory)
    return SiteSpider(
        start_url="https://example.com/",
        crawl_job_id=crawl_job_id,
        max_urls=25,
        max_depth=2,
        request_delay=0.0,
        render_mode=render_mode,
        render_timeout_ms=6_000,
        max_rendered_pages_per_job=5,
        site_registered_domain="example.com",
    )


def _html_response(
    *,
    url: str,
    html: str,
    meta: dict | None = None,
    status: int = 200,
    headers: dict[bytes, bytes] | None = None,
) -> HtmlResponse:
    request = Request(url=url, meta=meta or {})
    resolved_headers = headers or {b"Content-Type": b"text/html; charset=utf-8"}
    return HtmlResponse(
        url=url,
        body=html.encode("utf-8"),
        encoding="utf-8",
        request=request,
        headers=resolved_headers,
        status=status,
    )


def test_detect_js_heavy_page_marks_shell_html() -> None:
    html = """
    <html>
      <head>
        <script></script><script></script><script></script><script></script><script></script><script></script>
      </head>
      <body>
        <div id="__next">Loading...</div>
      </body>
    </html>
    """
    response = _html_response(url="https://example.com/", html=html)

    result = detect_js_heavy_page(
        response,
        title=None,
        meta_description=None,
        canonical_url=None,
        h1=None,
        visible_text="Loading",
        link_count=0,
    )

    assert result.js_heavy_like is True
    assert result.reason is not None


def test_render_mode_never_keeps_raw_html_flow(sqlite_session_factory, monkeypatch) -> None:
    spider = _make_spider(sqlite_session_factory, monkeypatch, render_mode="never")
    response = _html_response(
        url="https://example.com/",
        html="""
        <html><head><title>Home</title></head><body><h1>Home</h1><p>Enough visible text for a normal HTML page.</p></body></html>
        """,
        meta={"depth": 0, "requested_url": "https://example.com/", "normalized_url": "https://example.com/"},
    )

    results = list(spider.parse(response))

    assert any(isinstance(result, PageWithLinksItem) for result in results)
    assert not any(isinstance(result, Request) and result.meta.get("is_render_request") for result in results)


def test_render_mode_auto_attempts_render_only_for_js_heavy_pages(sqlite_session_factory, monkeypatch) -> None:
    spider = _make_spider(sqlite_session_factory, monkeypatch, render_mode="auto")
    shell_response = _html_response(
        url="https://example.com/",
        html="""
        <html>
          <head>
            <script></script><script></script><script></script><script></script><script></script><script></script>
          </head>
          <body><div id="__next">Loading...</div></body>
        </html>
        """,
        meta={"depth": 0, "requested_url": "https://example.com/", "normalized_url": "https://example.com/"},
    )
    rich_response = _html_response(
        url="https://example.com/about",
        html="""
        <html><head><title>About</title><meta name="description" content="About page with enough text." /></head>
        <body><h1>About</h1><p>This page has enough meaningful text to avoid the JS-heavy heuristic.</p></body></html>
        """,
        meta={
            "depth": 0,
            "requested_url": "https://example.com/about",
            "normalized_url": "https://example.com/about",
        },
    )

    shell_results = list(spider.parse(shell_response))
    rich_results = list(spider.parse(rich_response))

    assert len(shell_results) == 1
    assert isinstance(shell_results[0], Request)
    assert shell_results[0].meta["is_render_request"] is True
    assert shell_results[0].meta["render_attempted"] is True

    assert any(isinstance(result, PageWithLinksItem) for result in rich_results)
    assert not any(isinstance(result, Request) and result.meta.get("is_render_request") for result in rich_results)


def test_render_mode_always_attempts_render_for_html_pages(sqlite_session_factory, monkeypatch) -> None:
    spider = _make_spider(sqlite_session_factory, monkeypatch, render_mode="always")
    response = _html_response(
        url="https://example.com/",
        html="<html><head><title>Home</title></head><body><h1>Home</h1><p>Text.</p></body></html>",
        meta={"depth": 0, "requested_url": "https://example.com/", "normalized_url": "https://example.com/"},
    )

    results = list(spider.parse(response))

    assert len(results) == 1
    assert isinstance(results[0], Request)
    assert results[0].meta["render_reason"] == "render_mode=always"


def test_rendered_response_extracts_canonical_robots_and_schema(sqlite_session_factory, monkeypatch) -> None:
    spider = _make_spider(sqlite_session_factory, monkeypatch, render_mode="auto")
    response = _html_response(
        url="https://example.com/rendered",
        html="""
        <html>
          <head>
            <title>Rendered title</title>
            <meta name="description" content="Rendered description for the page." />
            <meta name="robots" content="noindex,follow" />
            <link rel="canonical" href="/canonical-target" />
            <script type="application/ld+json">
              {"@context":"https://schema.org","@type":["Article","BreadcrumbList"]}
            </script>
          </head>
          <body>
            <h1>Rendered heading</h1>
            <h2>More context</h2>
            <a href="/next">Next</a>
            <p>Rendered content with enough words to be stored from the final DOM.</p>
          </body>
        </html>
        """,
        meta={
            "depth": 0,
            "requested_url": "https://example.com/rendered",
            "normalized_url": "https://example.com/rendered",
            "is_render_request": True,
            "render_attempted": True,
            "render_reason": "low_text_many_scripts(words=1,scripts=6,links=0)",
            "js_heavy_like": True,
        },
        headers={
            b"Content-Type": b"text/html; charset=utf-8",
            b"X-Robots-Tag": b"noindex",
        },
    )

    results = list(spider.parse(response))
    page_item = next(result for result in results if isinstance(result, PageWithLinksItem))
    page = page_item["page"]

    assert page["was_rendered"] is True
    assert page["fetch_mode_used"] == "playwright"
    assert page["render_reason"] == "low_text_many_scripts(words=1,scripts=6,links=0)"
    assert page["canonical_url"] == "https://example.com/canonical-target"
    assert page["robots_meta"] == "noindex,follow"
    assert page["x_robots_tag"] == "noindex"
    assert page["schema_present"] is True
    assert page["schema_count"] == 1
    assert page["schema_types_json"] == ["Article", "BreadcrumbList"]


def test_render_error_falls_back_to_raw_page_data(sqlite_session_factory, monkeypatch) -> None:
    spider = _make_spider(sqlite_session_factory, monkeypatch, render_mode="auto")
    raw_response = _html_response(
        url="https://example.com/",
        html="""
        <html>
          <head>
            <script></script><script></script><script></script><script></script><script></script><script></script>
          </head>
          <body>
            <div id="__next">Loading...</div>
            <a href="/next">Next</a>
          </body>
        </html>
        """,
        meta={"depth": 0, "requested_url": "https://example.com/", "normalized_url": "https://example.com/"},
    )
    render_request = list(spider.parse(raw_response))[0]

    class FakeFailure:
        def __init__(self, request: Request) -> None:
            self.request = request
            self.value = type("FailureValue", (), {"response": None})()

        def getErrorMessage(self) -> str:
            return "Navigation timeout"

    results = list(spider.handle_request_error(FakeFailure(render_request)))

    page_item = next(result for result in results if isinstance(result, PageWithLinksItem))
    page = page_item["page"]

    assert page["render_attempted"] is True
    assert page["was_rendered"] is False
    assert page["render_error_message"] == "Navigation timeout"
    assert page["js_heavy_like"] is True
    assert any(isinstance(result, Request) and result.url == "https://example.com/next" for result in results)
