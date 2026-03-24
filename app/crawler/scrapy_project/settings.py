from __future__ import annotations

from importlib.util import find_spec

from app.core.config import get_settings

settings = get_settings()

BOT_NAME = "seo_crawler"
SPIDER_MODULES = ["app.crawler.scrapy_project.spiders"]
NEWSPIDER_MODULE = "app.crawler.scrapy_project.spiders"

ROBOTSTXT_OBEY = False
COOKIES_ENABLED = False
TELNETCONSOLE_ENABLED = False

CONCURRENT_REQUESTS = settings.scrapy_concurrent_requests
DOWNLOAD_DELAY = settings.crawl_default_request_delay
DOWNLOAD_TIMEOUT = settings.scrapy_download_timeout
USER_AGENT = settings.scrapy_user_agent

DEPTH_PRIORITY = 1
RETRY_ENABLED = True
REDIRECT_ENABLED = True
HTTPERROR_ALLOW_ALL = True

ITEM_PIPELINES = {
    "app.crawler.scrapy_project.pipelines.DatabasePipeline": 300,
}

LOG_LEVEL = settings.log_level


def configure_playwright(scrapy_settings, *, render_mode: str) -> None:
    if render_mode == "never":
        return

    if find_spec("scrapy_playwright") is None:
        raise RuntimeError(
            "render_mode requires scrapy-playwright. Install backend dependencies and run 'playwright install chromium'."
        )

    from app.crawler.scrapy_project.playwright_support import abort_playwright_request

    scrapy_settings.set("TWISTED_REACTOR", "twisted.internet.asyncioreactor.AsyncioSelectorReactor", priority="cmdline")
    scrapy_settings.set(
        "DOWNLOAD_HANDLERS",
        {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        priority="cmdline",
    )
    scrapy_settings.set("PLAYWRIGHT_BROWSER_TYPE", "chromium", priority="cmdline")
    scrapy_settings.set("PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT", settings.crawl_default_render_timeout_ms, priority="cmdline")
    scrapy_settings.set("PLAYWRIGHT_LAUNCH_OPTIONS", {"headless": True}, priority="cmdline")
    scrapy_settings.set("PLAYWRIGHT_MAX_CONTEXTS", 1, priority="cmdline")
    scrapy_settings.set("PLAYWRIGHT_MAX_PAGES_PER_CONTEXT", 2, priority="cmdline")
    scrapy_settings.set("PLAYWRIGHT_ABORT_REQUEST", abort_playwright_request, priority="cmdline")
