from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import scrapy
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from scrapy.exceptions import CloseSpider
from twisted.python.failure import Failure

from app.core.config import get_settings
from app.crawler.extraction.content_extractor import extract_html_size_bytes
from app.crawler.extraction.links_extractor import ExtractedLink
from app.crawler.extraction.page_extractor import ExtractedPageData, extract_page_data
from app.crawler.normalization.urls import extract_host, extract_registered_domain, normalize_url
from app.crawler.rendering.detection import RenderDetectionResult, detect_js_heavy_page
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
        render_mode: str = "never",
        render_timeout_ms: int = 8_000,
        max_rendered_pages_per_job: int = 25,
        site_registered_domain: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        normalized_start = normalize_url(start_url)
        if normalized_start is None:
            raise ValueError(f"Invalid start URL: {start_url}")

        resolved_render_mode = str(render_mode).strip().lower()
        if resolved_render_mode not in {"never", "auto", "always"}:
            raise ValueError(f"Invalid render_mode: {render_mode}")

        self.start_url = normalized_start
        self.crawl_job_id = int(crawl_job_id)
        self.max_urls = max(1, int(max_urls))
        self.max_depth = max(0, int(max_depth))
        self.request_delay = max(0.0, float(request_delay))
        self.render_mode = resolved_render_mode
        self.render_timeout_ms = max(1, int(render_timeout_ms))
        self.max_rendered_pages_per_job = max(1, int(max_rendered_pages_per_job))
        self.render_attempts_count = 0

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
        yield self._build_crawl_request(
            url=self.start_url,
            depth=0,
            requested_url=self.start_url,
            normalized_url=self.start_url,
            dont_filter=True,
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
        content_type = self._extract_content_type(response)
        html_size_bytes = extract_html_size_bytes(response)
        response_time_ms = self._extract_response_time_ms(response.meta.get("download_latency"))
        is_render_request = bool(response.meta.get("is_render_request"))

        final_normalized = normalize_url(final_url)
        if final_normalized:
            self.seen_normalized_urls.add(final_normalized)

        error_message = f"HTTP {status_code}" if status_code is not None and status_code >= 400 else None
        extracted_data: ExtractedPageData | None = None
        detection = self._resolve_detection_result(response, None)

        if self._is_html_response(response):
            try:
                extracted_data = extract_page_data(
                    response,
                    site_registered_domain=self.site_registered_domain,
                    blocked_extensions=self.blocked_extensions,
                )
                detection = self._resolve_detection_result(response, extracted_data)
            except Exception as exc:  # pragma: no cover - defensive
                if is_render_request:
                    yield from self._yield_render_error_fallback(
                        meta=response.meta,
                        error_message=f"render_parse_error: {exc}",
                    )
                    return
                error_message = self._combine_error_message(error_message, f"parse_error: {exc}")

        if extracted_data is not None and self._should_attempt_render(
            response=response,
            status_code=status_code,
            detection=detection,
            is_render_request=is_render_request,
        ):
            raw_page_payload = self._build_page_payload(
                requested_url=requested_url,
                normalized_url=normalized_url,
                final_url=final_url,
                status_code=status_code,
                content_type=content_type,
                html_size_bytes=html_size_bytes,
                response_time_ms=response_time_ms,
                depth=depth,
                fetched_at=fetched_at,
                extracted_data=extracted_data,
                error_message=error_message,
                was_rendered=False,
                render_attempted=False,
                fetch_mode_used="http",
                js_heavy_like=detection.js_heavy_like,
                render_reason=self._base_render_reason(detection),
                render_error_message=None,
            )
            yield self._build_render_request(
                response=response,
                depth=depth,
                requested_url=requested_url,
                normalized_url=normalized_url,
                raw_page_payload=raw_page_payload,
                raw_extracted_links=extracted_data.links,
                render_reason=self._base_render_reason(detection),
                js_heavy_like=detection.js_heavy_like,
            )
            return

        render_reason = self._resolved_page_render_reason(
            response=response,
            status_code=status_code,
            detection=detection,
            is_render_request=is_render_request,
        )

        page_payload = self._build_page_payload(
            requested_url=requested_url,
            normalized_url=normalized_url,
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            html_size_bytes=html_size_bytes,
            response_time_ms=response_time_ms,
            depth=depth,
            fetched_at=fetched_at,
            extracted_data=extracted_data,
            error_message=error_message,
            was_rendered=is_render_request,
            render_attempted=bool(response.meta.get("render_attempted")) or is_render_request,
            fetch_mode_used="playwright" if is_render_request else "http",
            js_heavy_like=detection.js_heavy_like,
            render_reason=render_reason,
            render_error_message=response.meta.get("render_error_message"),
        )
        links_payload = self._build_links_payload(extracted_data.links if extracted_data is not None else [])
        yield PageWithLinksItem(page=page_payload, links=links_payload)

        if extracted_data is not None:
            yield from self._schedule_links(extracted_data.links, current_depth=depth)

    def handle_request_error(self, failure: Failure):  # type: ignore[no-untyped-def]
        self._refresh_stop_requested()
        if self.stop_requested:
            raise CloseSpider("crawl_job_stopped")

        request = failure.request
        if request.meta.get("is_render_request"):
            yield from self._yield_render_error_fallback(
                meta=request.meta,
                error_message=failure.getErrorMessage(),
            )
            return

        requested_url = str(request.meta.get("requested_url", request.url))
        normalized_url = str(request.meta.get("normalized_url") or normalize_url(requested_url) or requested_url)
        depth = int(request.meta.get("depth", 0))

        response = getattr(failure.value, "response", None)
        status_code = int(response.status) if response is not None else None
        final_url = response.url if response is not None else None
        fetched_at = datetime.now(timezone.utc)
        content_type = self._extract_content_type(response) if response is not None else None
        html_size_bytes = extract_html_size_bytes(response) if response is not None else None
        response_time_ms = self._extract_response_time_ms(request.meta.get("download_latency"))

        if final_url:
            final_normalized = normalize_url(final_url)
            if final_normalized:
                self.seen_normalized_urls.add(final_normalized)

        page_payload = self._build_page_payload(
            requested_url=requested_url,
            normalized_url=normalized_url,
            final_url=final_url,
            status_code=status_code,
            content_type=content_type,
            html_size_bytes=html_size_bytes,
            response_time_ms=response_time_ms,
            depth=depth,
            fetched_at=fetched_at,
            extracted_data=None,
            error_message=failure.getErrorMessage(),
            was_rendered=False,
            render_attempted=False,
            fetch_mode_used="http",
            js_heavy_like=False,
            render_reason=None,
            render_error_message=None,
        )
        yield PageWithLinksItem(page=page_payload, links=[])

    def _should_attempt_render(
        self,
        *,
        response: scrapy.http.Response,
        status_code: int | None,
        detection: RenderDetectionResult,
        is_render_request: bool,
    ) -> bool:
        if is_render_request:
            return False
        if self.render_mode == "never":
            return False
        if not self._is_html_response(response):
            return False
        if status_code is not None and status_code >= 400:
            return False
        if self.render_attempts_count >= self.max_rendered_pages_per_job:
            return False
        if self.render_mode == "always":
            return True
        return detection.js_heavy_like

    def _build_render_request(
        self,
        *,
        response: scrapy.http.Response,
        depth: int,
        requested_url: str,
        normalized_url: str,
        raw_page_payload: PagePayload,
        raw_extracted_links: list[ExtractedLink],
        render_reason: str | None,
        js_heavy_like: bool,
    ) -> scrapy.Request:
        self.render_attempts_count += 1
        target_url = response.url or requested_url
        return scrapy.Request(
            url=target_url,
            callback=self.parse,
            errback=self.handle_request_error,
            dont_filter=True,
            meta={
                "depth": depth,
                "requested_url": requested_url,
                "normalized_url": normalized_url,
                "render_attempted": True,
                "render_reason": render_reason,
                "js_heavy_like": js_heavy_like,
                "raw_page_payload": raw_page_payload,
                "raw_extracted_links": raw_extracted_links,
                "is_render_request": True,
                "playwright": True,
                "playwright_page_goto_kwargs": {
                    "wait_until": "networkidle",
                    "timeout": self.render_timeout_ms,
                },
            },
        )

    def _yield_render_error_fallback(self, *, meta: dict[str, Any], error_message: str):
        raw_page_payload = meta.get("raw_page_payload")
        if not isinstance(raw_page_payload, dict):
            return

        fallback_payload = dict(raw_page_payload)
        fallback_payload["render_attempted"] = True
        fallback_payload["was_rendered"] = False
        fallback_payload["fetch_mode_used"] = "http"
        fallback_payload["render_reason"] = meta.get("render_reason")
        fallback_payload["render_error_message"] = error_message
        yield PageWithLinksItem(page=fallback_payload, links=self._build_links_payload(meta.get("raw_extracted_links", [])))

        raw_extracted_links = meta.get("raw_extracted_links")
        if isinstance(raw_extracted_links, list):
            yield from self._schedule_links(raw_extracted_links, current_depth=int(meta.get("depth", 0)))

    def _schedule_links(self, links: list[ExtractedLink], *, current_depth: int):
        for link in links:
            if self._should_schedule_link(link=link, current_depth=current_depth):
                next_depth = current_depth + 1
                next_url = link.target_normalized_url or link.target_url
                yield self._build_crawl_request(
                    url=next_url,
                    depth=next_depth,
                    requested_url=link.target_url,
                    normalized_url=link.target_normalized_url,
                )

    def _build_crawl_request(
        self,
        *,
        url: str,
        depth: int,
        requested_url: str,
        normalized_url: str | None,
        dont_filter: bool = False,
    ) -> scrapy.Request:
        return scrapy.Request(
            url=url,
            callback=self.parse,
            errback=self.handle_request_error,
            dont_filter=dont_filter,
            meta={
                "depth": depth,
                "requested_url": requested_url,
                "normalized_url": normalized_url,
            },
        )

    def _resolve_detection_result(
        self,
        response: scrapy.http.Response,
        extracted_data: ExtractedPageData | None,
    ) -> RenderDetectionResult:
        if response.meta.get("is_render_request"):
            js_heavy_like = bool(response.meta.get("js_heavy_like"))
            reason = response.meta.get("render_reason")
            return RenderDetectionResult(js_heavy_like=js_heavy_like, reason=reason if isinstance(reason, str) else None)

        if extracted_data is None or not self._is_html_response(response):
            return RenderDetectionResult(js_heavy_like=False, reason=None)

        return detect_js_heavy_page(
            response,
            title=extracted_data.title,
            meta_description=extracted_data.meta_description,
            canonical_url=extracted_data.canonical_url,
            h1=extracted_data.h1,
            visible_text=extracted_data.visible_text,
            link_count=len(extracted_data.links),
        )

    def _resolved_page_render_reason(
        self,
        *,
        response: scrapy.http.Response,
        status_code: int | None,
        detection: RenderDetectionResult,
        is_render_request: bool,
    ) -> str | None:
        if is_render_request:
            return response.meta.get("render_reason")

        base_reason = self._base_render_reason(detection)
        if base_reason is None:
            return None

        if self._render_was_skipped_due_to_limit(response=response, status_code=status_code, detection=detection):
            return f"{base_reason}; render_limit_reached"

        return base_reason

    def _render_was_skipped_due_to_limit(
        self,
        *,
        response: scrapy.http.Response,
        status_code: int | None,
        detection: RenderDetectionResult,
    ) -> bool:
        if self.render_mode == "never":
            return False
        if not self._is_html_response(response):
            return False
        if status_code is not None and status_code >= 400:
            return False
        if self.render_attempts_count < self.max_rendered_pages_per_job:
            return False
        if self.render_mode == "always":
            return True
        return detection.js_heavy_like

    def _base_render_reason(self, detection: RenderDetectionResult) -> str | None:
        if self.render_mode == "always":
            return "render_mode=always"
        return detection.reason

    def _build_page_payload(
        self,
        *,
        requested_url: str,
        normalized_url: str,
        final_url: str | None,
        status_code: int | None,
        content_type: str | None,
        html_size_bytes: int | None,
        response_time_ms: int | None,
        depth: int,
        fetched_at: datetime,
        extracted_data: ExtractedPageData | None,
        error_message: str | None,
        was_rendered: bool,
        render_attempted: bool,
        fetch_mode_used: str | None,
        js_heavy_like: bool,
        render_reason: str | None,
        render_error_message: str | None,
    ) -> PagePayload:
        return {
            "crawl_job_id": self.crawl_job_id,
            "url": requested_url,
            "normalized_url": normalized_url,
            "final_url": final_url,
            "status_code": status_code,
            "title": extracted_data.title if extracted_data is not None else None,
            "title_length": extracted_data.title_length if extracted_data is not None else None,
            "meta_description": extracted_data.meta_description if extracted_data is not None else None,
            "meta_description_length": extracted_data.meta_description_length if extracted_data is not None else None,
            "h1": extracted_data.h1 if extracted_data is not None else None,
            "h1_count": extracted_data.h1_count if extracted_data is not None else None,
            "h2_count": extracted_data.h2_count if extracted_data is not None else None,
            "canonical_url": extracted_data.canonical_url if extracted_data is not None else None,
            "robots_meta": extracted_data.robots_meta if extracted_data is not None else None,
            "x_robots_tag": extracted_data.x_robots_tag if extracted_data is not None else None,
            "content_type": content_type,
            "word_count": extracted_data.word_count if extracted_data is not None else None,
            "content_text_hash": extracted_data.content_text_hash if extracted_data is not None else None,
            "images_count": extracted_data.images_count if extracted_data is not None else None,
            "images_missing_alt_count": extracted_data.images_missing_alt_count if extracted_data is not None else None,
            "html_size_bytes": html_size_bytes,
            "was_rendered": was_rendered,
            "render_attempted": render_attempted,
            "fetch_mode_used": fetch_mode_used,
            "js_heavy_like": js_heavy_like,
            "render_reason": render_reason,
            "render_error_message": render_error_message,
            "schema_present": extracted_data.schema_present if extracted_data is not None else False,
            "schema_count": extracted_data.schema_count if extracted_data is not None else 0,
            "schema_types_json": extracted_data.schema_types_json if extracted_data is not None and extracted_data.schema_types_json else None,
            "response_time_ms": response_time_ms,
            "is_internal": True,
            "depth": depth,
            "fetched_at": fetched_at,
            "error_message": error_message,
        }

    def _build_links_payload(self, links: list[ExtractedLink] | object) -> list[LinkPayload]:
        if not isinstance(links, list):
            return []
        return [self._to_link_payload(link) for link in links if isinstance(link, ExtractedLink)]

    def _combine_error_message(self, current: str | None, next_value: str) -> str:
        if current:
            return f"{current}; {next_value}"
        return next_value

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

        try:
            with SessionLocal() as session:
                status = session.scalar(select(CrawlJob.status).where(CrawlJob.id == self.crawl_job_id))
        except SQLAlchemyError as exc:  # pragma: no cover - defensive fallback for unit tests / transient DB issues
            self.logger.warning(
                "Could not refresh crawl stop flag for crawl_job_id=%s: %s",
                self.crawl_job_id,
                exc,
            )
            return

        if status == CrawlJobStatus.STOPPED or status == CrawlJobStatus.STOPPED.value:
            self.stop_requested = True
