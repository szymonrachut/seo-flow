from __future__ import annotations

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
