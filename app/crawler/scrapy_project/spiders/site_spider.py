from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import scrapy
from sqlalchemy import select
from scrapy.exceptions import CloseSpider
from twisted.python.failure import Failure

from app.core.config import get_settings
from app.crawler.extraction.heading_extractor import extract_first_h1
from app.crawler.extraction.links_extractor import ExtractedLink, extract_links
from app.crawler.extraction.meta_extractor import (
    extract_canonical_url,
    extract_meta_description,
    extract_robots_meta,
    extract_title,
)
from app.crawler.normalization.urls import (
    extract_host,
    extract_registered_domain,
    normalize_url,
)
from app.crawler.scrapy_project.items import LinkPayload, PagePayload, PageWithLinksItem
from app.db.models import CrawlJob, CrawlJobStatus, Page
from app.db.session import SessionLocal


class SiteSpider(scrapy.Spider):
    name = "site_spider"

    def __init__(
        self,
        start_url: str,
        crawl_job_id: int,
        max_urls: int,
        max_depth: int,
        request_delay: float,
        site_registered_domain: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        normalized_start = normalize_url(start_url)
        if normalized_start is None:
            raise ValueError(f"Invalid start URL: {start_url}")

        self.start_url = normalized_start
        self.crawl_job_id = int(crawl_job_id)
        self.max_urls = max(1, int(max_urls))
        self.max_depth = max(0, int(max_depth))
        self.request_delay = max(0.0, float(request_delay))

        extracted_domain = extract_registered_domain(self.start_url)
        if site_registered_domain:
            self.site_registered_domain = site_registered_domain.lower()
        elif extracted_domain:
            self.site_registered_domain = extracted_domain
        else:
            raise ValueError(f"Could not determine domain for URL: {self.start_url}")

        start_host = extract_host(self.start_url)
        self.allowed_domains = [self.site_registered_domain]
        if start_host and start_host not in self.allowed_domains:
            self.allowed_domains.append(start_host)

        self.blocked_extensions = get_settings().skip_extensions
        self.seen_normalized_urls = self._load_existing_page_urls()
        self.stop_requested = False

    def start_requests(self):  # type: ignore[no-untyped-def]
        self._refresh_stop_requested()
        if self.stop_requested:
            self.logger.info("Stop requested before start for crawl_job_id=%s", self.crawl_job_id)
            return

        if self.start_url in self.seen_normalized_urls:
            self.logger.info("Start URL already stored for crawl_job_id=%s", self.crawl_job_id)
            return

        if len(self.seen_normalized_urls) >= self.max_urls:
            self.logger.info("max_urls limit already reached for crawl_job_id=%s", self.crawl_job_id)
            return

        self.seen_normalized_urls.add(self.start_url)
        yield scrapy.Request(
            url=self.start_url,
            callback=self.parse,
            errback=self.handle_request_error,
            dont_filter=True,
            meta={
                "depth": 0,
                "requested_url": self.start_url,
                "normalized_url": self.start_url,
            },
        )

    def parse(self, response: scrapy.http.Response, **kwargs: Any):  # type: ignore[override]
        self._refresh_stop_requested()
        if self.stop_requested:
            raise CloseSpider("crawl_job_stopped")

        requested_url = str(response.meta.get("requested_url", response.request.url))
        normalized_url = str(
            response.meta.get("normalized_url")
            or normalize_url(requested_url)
            or normalize_url(response.url)
            or requested_url
        )
        depth = int(response.meta.get("depth", 0))
        status_code = int(response.status) if response.status is not None else None
        fetched_at = datetime.now(timezone.utc)

        final_url = response.url
        final_normalized = normalize_url(final_url)
        if final_normalized:
            self.seen_normalized_urls.add(final_normalized)

        title: str | None = None
        meta_description: str | None = None
        h1: str | None = None
        canonical_url: str | None = None
        robots_meta: str | None = None
        content_type = self._extract_content_type(response)
        response_time_ms = self._extract_response_time_ms(response.meta.get("download_latency"))
        links_payload: list[LinkPayload] = []
        error_message: str | None = None

        if status_code is not None and status_code >= 400:
            error_message = f"HTTP {status_code}"

        if self._is_html_response(response):
            try:
                title = extract_title(response)
                meta_description = extract_meta_description(response)
                h1 = extract_first_h1(response)
                canonical_url = extract_canonical_url(response)
                robots_meta = extract_robots_meta(response)
                extracted_links = extract_links(
                    response=response,
                    site_registered_domain=self.site_registered_domain,
                    blocked_extensions=self.blocked_extensions,
                )

                for link in extracted_links:
                    links_payload.append(self._to_link_payload(link))
                    if self._should_schedule_link(link=link, current_depth=depth):
                        next_depth = depth + 1
                        next_url = link.target_normalized_url or link.target_url
                        yield scrapy.Request(
                            url=next_url,
                            callback=self.parse,
                            errback=self.handle_request_error,
                            meta={
                                "depth": next_depth,
                                "requested_url": link.target_url,
                                "normalized_url": link.target_normalized_url,
                            },
                        )
            except Exception as exc:  # pragma: no cover - defensive
                if error_message:
                    error_message = f"{error_message}; parse_error: {exc}"
                else:
                    error_message = f"parse_error: {exc}"

        page_payload: PagePayload = {
            "crawl_job_id": self.crawl_job_id,
            "url": requested_url,
            "normalized_url": normalized_url,
            "final_url": final_url,
            "status_code": status_code,
            "title": title,
            "meta_description": meta_description,
            "h1": h1,
            "canonical_url": canonical_url,
            "robots_meta": robots_meta,
            "content_type": content_type,
            "response_time_ms": response_time_ms,
            "is_internal": True,
            "depth": depth,
            "fetched_at": fetched_at,
            "error_message": error_message,
        }
        yield PageWithLinksItem(page=page_payload, links=links_payload)

    def handle_request_error(self, failure: Failure):  # type: ignore[no-untyped-def]
        self._refresh_stop_requested()
        if self.stop_requested:
            raise CloseSpider("crawl_job_stopped")

        request = failure.request
        requested_url = str(request.meta.get("requested_url", request.url))
        normalized_url = str(request.meta.get("normalized_url") or normalize_url(requested_url) or requested_url)
        depth = int(request.meta.get("depth", 0))

        response = getattr(failure.value, "response", None)
        status_code = int(response.status) if response is not None else None
        final_url = response.url if response is not None else None
        fetched_at = datetime.now(timezone.utc)
        content_type = self._extract_content_type(response) if response is not None else None
        response_time_ms = self._extract_response_time_ms(request.meta.get("download_latency"))

        if final_url:
            final_normalized = normalize_url(final_url)
            if final_normalized:
                self.seen_normalized_urls.add(final_normalized)

        page_payload: PagePayload = {
            "crawl_job_id": self.crawl_job_id,
            "url": requested_url,
            "normalized_url": normalized_url,
            "final_url": final_url,
            "status_code": status_code,
            "title": None,
            "meta_description": None,
            "h1": None,
            "canonical_url": None,
            "robots_meta": None,
            "content_type": content_type,
            "response_time_ms": response_time_ms,
            "is_internal": True,
            "depth": depth,
            "fetched_at": fetched_at,
            "error_message": failure.getErrorMessage(),
        }
        yield PageWithLinksItem(page=page_payload, links=[])

    def _should_schedule_link(self, link: ExtractedLink, current_depth: int) -> bool:
        if self.stop_requested:
            return False
        if not link.should_crawl:
            return False
        if link.target_normalized_url is None:
            return False

        next_depth = current_depth + 1
        if next_depth > self.max_depth:
            return False

        if link.target_normalized_url in self.seen_normalized_urls:
            return False

        if len(self.seen_normalized_urls) >= self.max_urls:
            return False

        self.seen_normalized_urls.add(link.target_normalized_url)
        return True

    def _is_html_response(self, response: scrapy.http.Response) -> bool:
        content_type = response.headers.get("Content-Type", b"").decode("latin-1").lower()
        if not content_type:
            return True
        return ("text/html" in content_type) or ("application/xhtml+xml" in content_type)

    def _to_link_payload(self, link: ExtractedLink) -> LinkPayload:
        return {
            "crawl_job_id": self.crawl_job_id,
            "source_url": link.source_url,
            "target_url": link.target_url,
            "target_normalized_url": link.target_normalized_url,
            "target_domain": link.target_domain,
            "anchor_text": link.anchor_text,
            "rel_attr": link.rel_attr,
            "is_nofollow": link.is_nofollow,
            "is_internal": link.is_internal,
        }

    def _extract_content_type(self, response: scrapy.http.Response | None) -> str | None:
        if response is None:
            return None
        raw = response.headers.get("Content-Type", b"")
        if not raw:
            return None
        decoded = raw.decode("latin-1").strip()
        return decoded if decoded else None

    def _extract_response_time_ms(self, latency: Any) -> int | None:
        if latency is None:
            return None
        try:
            latency_float = float(latency)
        except (TypeError, ValueError):
            return None
        if latency_float < 0:
            return None
        return int(round(latency_float * 1000))

    def _load_existing_page_urls(self) -> set[str]:
        with SessionLocal() as session:
            rows = session.scalars(select(Page.normalized_url).where(Page.crawl_job_id == self.crawl_job_id)).all()
        return {url for url in rows if url}

    def _refresh_stop_requested(self) -> None:
        if self.stop_requested:
            return

        with SessionLocal() as session:
            status = session.scalar(select(CrawlJob.status).where(CrawlJob.id == self.crawl_job_id))

        if status == CrawlJobStatus.STOPPED or status == CrawlJobStatus.STOPPED.value:
            self.stop_requested = True
