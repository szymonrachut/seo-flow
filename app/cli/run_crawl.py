from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings as ScrapySettings
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.crawler.scrapy_project import settings as scrapy_project_settings
from app.crawler.scrapy_project.spiders.site_spider import SiteSpider
from app.db.models import CrawlJob, CrawlJobStatus
from app.db.session import SessionLocal
from app.services import crawl_job_service, export_service, page_taxonomy_service

logger = logging.getLogger(__name__)
EXPORT_COMMANDS = {"export-pages", "export-links", "export-audit"}


def parse_crawl_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    app_settings = get_settings()

    parser = argparse.ArgumentParser(description="Run single-domain SEO crawl job.")
    parser.add_argument("start_url", help="Start URL (e.g. https://example.com)")
    parser.add_argument("--max-urls", type=int, default=app_settings.crawl_default_max_urls)
    parser.add_argument("--max-depth", type=int, default=app_settings.crawl_default_max_depth)
    parser.add_argument("--delay", type=float, default=app_settings.crawl_default_request_delay)
    parser.add_argument("--render-mode", choices=["never", "auto", "always"], default=app_settings.crawl_default_render_mode)
    parser.add_argument("--render-timeout-ms", type=int, default=app_settings.crawl_default_render_timeout_ms)
    parser.add_argument(
        "--max-rendered-pages",
        type=int,
        default=app_settings.crawl_default_max_rendered_pages_per_job,
    )
    parser.add_argument("--job-id", type=int, default=None, help="Existing crawl job ID to execute.")
    args = parser.parse_args(argv)
    crawl_job_service.validate_crawl_limits(
        max_urls=args.max_urls,
        max_depth=args.max_depth,
        delay=args.delay,
    )
    crawl_job_service.validate_render_settings(
        render_mode=args.render_mode,
        render_timeout_ms=args.render_timeout_ms,
        max_rendered_pages_per_job=args.max_rendered_pages,
    )
    return args


def parse_export_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export crawl job data to CSV.")
    parser.add_argument("command", choices=sorted(EXPORT_COMMANDS))
    parser.add_argument("--job-id", type=int, required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def build_scrapy_settings(delay: float, max_depth: int, *, render_mode: str) -> ScrapySettings:
    scrapy_settings = ScrapySettings()
    for key in dir(scrapy_project_settings):
        if key.isupper():
            scrapy_settings.set(key, getattr(scrapy_project_settings, key))

    scrapy_settings.set("DOWNLOAD_DELAY", delay, priority="cmdline")
    scrapy_settings.set("DEPTH_LIMIT", max_depth, priority="cmdline")
    scrapy_project_settings.configure_playwright(scrapy_settings, render_mode=render_mode)
    return scrapy_settings


def update_job_stats(session: Session, crawl_job: CrawlJob) -> dict[str, Any]:
    page_taxonomy_service.ensure_page_taxonomy_for_job(session, crawl_job.id)
    stats = crawl_job_service.get_crawl_job_stats(session, crawl_job.id)
    crawl_job.stats_json = stats
    return stats


def _execute_spider(
    crawl_job_id: int,
    *,
    start_url: str,
    registered_domain: str,
    max_urls: int,
    max_depth: int,
    delay: float,
    render_mode: str,
    render_timeout_ms: int,
    max_rendered_pages_per_job: int,
) -> None:
    process = CrawlerProcess(settings=build_scrapy_settings(delay=delay, max_depth=max_depth, render_mode=render_mode))
    process.crawl(
        SiteSpider,
        start_url=start_url,
        crawl_job_id=crawl_job_id,
        max_urls=max_urls,
        max_depth=max_depth,
        request_delay=delay,
        render_mode=render_mode,
        render_timeout_ms=render_timeout_ms,
        max_rendered_pages_per_job=max_rendered_pages_per_job,
        site_registered_domain=registered_domain,
    )
    process.start()


def _run_crawl_job(
    crawl_job_id: int,
    *,
    start_url: str,
    registered_domain: str,
    max_urls: int,
    max_depth: int,
    delay: float,
    render_mode: str,
    render_timeout_ms: int,
    max_rendered_pages_per_job: int,
) -> int:
    logger.info("Starting crawl_job_id=%s for %s", crawl_job_id, start_url)

    failed_error: str | None = None
    try:
        with SessionLocal() as session:
            crawl_job = session.get(CrawlJob, crawl_job_id)
            if crawl_job is None:
                raise RuntimeError(f"Crawl job {crawl_job_id} not found.")
            if crawl_job.status == CrawlJobStatus.STOPPED:
                update_job_stats(session, crawl_job)
                if crawl_job.finished_at is None:
                    crawl_job.finished_at = datetime.now(timezone.utc)
                session.commit()
                logger.info("Crawl job %s was already stopped before execution.", crawl_job_id)
                return crawl_job_id
            crawl_job.status = CrawlJobStatus.RUNNING
            crawl_job.started_at = datetime.now(timezone.utc)
            crawl_job.settings_json = crawl_job_service.build_crawl_settings(
                start_url=start_url,
                max_urls=max_urls,
                max_depth=max_depth,
                delay=delay,
                render_mode=render_mode,
                render_timeout_ms=render_timeout_ms,
                max_rendered_pages_per_job=max_rendered_pages_per_job,
            )
            session.commit()

        _execute_spider(
            crawl_job_id,
            start_url=start_url,
            registered_domain=registered_domain,
            max_urls=max_urls,
            max_depth=max_depth,
            delay=delay,
            render_mode=render_mode,
            render_timeout_ms=render_timeout_ms,
            max_rendered_pages_per_job=max_rendered_pages_per_job,
        )
    except Exception as exc:
        failed_error = str(exc)
        logger.exception("Crawl job failed: %s", exc)

    with SessionLocal() as session:
        crawl_job = session.get(CrawlJob, crawl_job_id)
        if crawl_job is None:
            raise RuntimeError(f"Crawl job {crawl_job_id} not found after execution.")

        update_job_stats(session, crawl_job)
        crawl_job.finished_at = datetime.now(timezone.utc)
        if crawl_job.status == CrawlJobStatus.STOPPED:
            pass
        else:
            crawl_job.status = CrawlJobStatus.FAILED if failed_error else CrawlJobStatus.FINISHED

        if failed_error:
            crawl_job.stats_json["error"] = failed_error

        session.commit()
        logger.info("Crawl job %s finished with status=%s", crawl_job_id, crawl_job.status.value)
        logger.info("Stats: %s", crawl_job.stats_json)

    return crawl_job_id


def run_crawl(
    *,
    start_url: str,
    max_urls: int,
    max_depth: int,
    delay: float,
    render_mode: str,
    render_timeout_ms: int,
    max_rendered_pages_per_job: int,
    existing_job_id: int | None = None,
) -> int:
    normalized_start_url, registered_domain = crawl_job_service.normalize_start_url_or_raise(start_url)
    crawl_job_service.validate_render_settings(
        render_mode=render_mode,
        render_timeout_ms=render_timeout_ms,
        max_rendered_pages_per_job=max_rendered_pages_per_job,
    )

    if existing_job_id is None:
        with SessionLocal() as session:
            crawl_job = crawl_job_service.create_crawl_job(
                session=session,
                root_url=normalized_start_url,
                max_urls=max_urls,
                max_depth=max_depth,
                delay=delay,
                render_mode=render_mode,
                render_timeout_ms=render_timeout_ms,
                max_rendered_pages_per_job=max_rendered_pages_per_job,
            )
            session.commit()
            crawl_job_id = crawl_job.id
    else:
        with SessionLocal() as session:
            crawl_job, normalized_start_url, registered_domain = crawl_job_service.prepare_existing_crawl_job(
                session=session,
                crawl_job_id=existing_job_id,
                root_url=normalized_start_url,
                max_urls=max_urls,
                max_depth=max_depth,
                delay=delay,
                render_mode=render_mode,
                render_timeout_ms=render_timeout_ms,
                max_rendered_pages_per_job=max_rendered_pages_per_job,
            )
            session.commit()
            crawl_job_id = crawl_job.id

    return _run_crawl_job(
        crawl_job_id,
        start_url=normalized_start_url,
        registered_domain=registered_domain,
        max_urls=max_urls,
        max_depth=max_depth,
        delay=delay,
        render_mode=render_mode,
        render_timeout_ms=render_timeout_ms,
        max_rendered_pages_per_job=max_rendered_pages_per_job,
    )


def run_export_command(command: str, *, job_id: int, output: str) -> Path:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as session:
        crawl_job = crawl_job_service.get_crawl_job(session, job_id)
        if crawl_job is None:
            raise RuntimeError(f"Crawl job {job_id} not found.")

        if command == "export-pages":
            content = export_service.build_pages_csv(session, job_id)
        elif command == "export-links":
            content = export_service.build_links_csv(session, job_id)
        elif command == "export-audit":
            content = export_service.build_audit_csv(session, job_id)
        else:  # pragma: no cover - guarded by argparse
            raise RuntimeError(f"Unknown export command: {command}")

    output_path.write_text(content, encoding="utf-8", newline="")
    logger.info("Exported %s for crawl_job_id=%s to %s", command, job_id, output_path)
    return output_path


def main() -> None:
    configure_logging()

    if len(sys.argv) > 1 and sys.argv[1] in EXPORT_COMMANDS:
        args = parse_export_args(sys.argv[1:])
        run_export_command(args.command, job_id=args.job_id, output=args.output)
        return

    args = parse_crawl_args()
    run_crawl(
        start_url=args.start_url,
        max_urls=args.max_urls,
        max_depth=args.max_depth,
        delay=args.delay,
        render_mode=args.render_mode,
        render_timeout_ms=args.render_timeout_ms,
        max_rendered_pages_per_job=args.max_rendered_pages,
        existing_job_id=args.job_id,
    )


if __name__ == "__main__":
    main()
