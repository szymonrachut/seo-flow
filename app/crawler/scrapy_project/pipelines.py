from __future__ import annotations

import logging
from typing import Any, cast

from itemadapter import ItemAdapter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crawler.scrapy_project.items import LinkPayload, PagePayload
from app.db.models import Link, Page
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


class DatabasePipeline:
    def __init__(self) -> None:
        self.session: Session | None = None

    def open_spider(self, spider) -> None:  # type: ignore[no-untyped-def]
        self.session = SessionLocal()

    def close_spider(self, spider) -> None:  # type: ignore[no-untyped-def]
        if self.session is not None:
            self.session.close()
            self.session = None

    def process_item(self, item, spider):  # type: ignore[no-untyped-def]
        if self.session is None:
            raise RuntimeError("Database session is not initialized.")

        adapter = ItemAdapter(item)
        page_data = cast(PagePayload, adapter.get("page"))
        links_data = cast(list[LinkPayload], adapter.get("links", []))

        normalized_url = page_data["normalized_url"]
        crawl_job_id = page_data["crawl_job_id"]

        existing_page = self.session.scalar(
            select(Page).where(
                Page.crawl_job_id == crawl_job_id,
                Page.normalized_url == normalized_url,
            )
        )
        if existing_page is not None:
            return item

        page = Page(**cast(dict[str, Any], page_data))
        self.session.add(page)

        try:
            self.session.flush()
            for link_data in links_data:
                link = Link(
                    crawl_job_id=link_data["crawl_job_id"],
                    source_page_id=page.id,
                    source_url=link_data["source_url"],
                    target_url=link_data["target_url"],
                    target_normalized_url=link_data["target_normalized_url"],
                    target_domain=link_data["target_domain"],
                    anchor_text=link_data["anchor_text"],
                    rel_attr=link_data["rel_attr"],
                    is_nofollow=link_data["is_nofollow"],
                    is_internal=link_data["is_internal"],
                )
                self.session.add(link)

            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            duplicate_page = self.session.scalar(
                select(Page).where(
                    Page.crawl_job_id == crawl_job_id,
                    Page.normalized_url == normalized_url,
                )
            )
            if duplicate_page is not None:
                logger.debug(
                    "Skipping duplicate page crawl_job_id=%s normalized_url=%s",
                    crawl_job_id,
                    normalized_url,
                )
                return item
            raise

        return item
