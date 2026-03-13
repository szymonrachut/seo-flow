from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.cli.run_crawl import update_job_stats
from app.crawler.scrapy_project.items import PageWithLinksItem
from app.crawler.scrapy_project.pipelines import DatabasePipeline
from app.db.base import Base
from app.db.models import CrawlJob, CrawlJobStatus, Link, Page, Site


def build_session_factory(tmp_path):
    db_path = tmp_path / "pipeline_stats.sqlite3"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def create_site_and_job(SessionLocal) -> int:
    with SessionLocal() as session:
        site = Site(root_url="https://example.com/", domain="example.com")
        session.add(site)
        session.flush()

        job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.RUNNING,
            settings_json={},
            stats_json={},
        )
        session.add(job)
        session.commit()
        return job.id


def test_pipeline_saves_page_and_links_with_expected_fields(tmp_path, monkeypatch) -> None:
    SessionLocal = build_session_factory(tmp_path)
    crawl_job_id = create_site_and_job(SessionLocal)

    from app.crawler.scrapy_project import pipelines as pipelines_module

    monkeypatch.setattr(pipelines_module, "SessionLocal", SessionLocal)

    pipeline = DatabasePipeline()
    pipeline.open_spider(spider=None)
    try:
        item = PageWithLinksItem(
            page={
                "crawl_job_id": crawl_job_id,
                "url": "https://example.com/source",
                "normalized_url": "https://example.com/source",
                "final_url": "https://example.com/source",
                "status_code": 200,
                "title": "Source Page",
                "meta_description": "Meta",
                "h1": "Heading",
                "is_internal": True,
                "depth": 0,
                "fetched_at": datetime.now(timezone.utc),
                "error_message": None,
            },
            links=[
                {
                    "crawl_job_id": crawl_job_id,
                    "source_url": "https://example.com/source",
                    "target_url": "https://example.com/internal",
                    "target_normalized_url": "https://example.com/internal",
                    "target_domain": "example.com",
                    "anchor_text": "Internal Link",
                    "rel_attr": "nofollow noopener",
                    "is_nofollow": True,
                    "is_internal": True,
                },
                {
                    "crawl_job_id": crawl_job_id,
                    "source_url": "https://example.com/source",
                    "target_url": "https://external.test/out",
                    "target_normalized_url": "https://external.test/out",
                    "target_domain": "external.test",
                    "anchor_text": "External Link",
                    "rel_attr": "",
                    "is_nofollow": False,
                    "is_internal": False,
                },
            ],
        )

        pipeline.process_item(item, spider=None)
        pipeline.process_item(item, spider=None)
    finally:
        pipeline.close_spider(spider=None)

    with SessionLocal() as session:
        pages = session.scalars(select(Page).where(Page.crawl_job_id == crawl_job_id)).all()
        links = session.scalars(select(Link).where(Link.crawl_job_id == crawl_job_id)).all()

        assert len(pages) == 1
        assert len(links) == 2
        assert all(link.source_page_id == pages[0].id for link in links)
        assert {link.target_url for link in links} == {
            "https://example.com/internal",
            "https://external.test/out",
        }
        assert {link.anchor_text for link in links} == {"Internal Link", "External Link"}


def test_update_job_stats_counts_pages_links_and_errors(tmp_path) -> None:
    SessionLocal = build_session_factory(tmp_path)
    crawl_job_id = create_site_and_job(SessionLocal)

    with SessionLocal() as session:
        page_ok = Page(
            crawl_job_id=crawl_job_id,
            url="https://example.com/",
            normalized_url="https://example.com/",
            final_url="https://example.com/",
            status_code=200,
            title="Home",
            meta_description=None,
            h1=None,
            is_internal=True,
            depth=0,
            fetched_at=datetime.now(timezone.utc),
            error_message=None,
        )
        page_http_error = Page(
            crawl_job_id=crawl_job_id,
            url="https://example.com/missing",
            normalized_url="https://example.com/missing",
            final_url="https://example.com/missing",
            status_code=404,
            title=None,
            meta_description=None,
            h1=None,
            is_internal=True,
            depth=1,
            fetched_at=datetime.now(timezone.utc),
            error_message="HTTP 404",
        )
        page_runtime_error = Page(
            crawl_job_id=crawl_job_id,
            url="https://example.com/timeout",
            normalized_url="https://example.com/timeout",
            final_url="https://example.com/timeout",
            status_code=200,
            title=None,
            meta_description=None,
            h1=None,
            is_internal=True,
            depth=1,
            fetched_at=datetime.now(timezone.utc),
            error_message="Timeout",
        )
        session.add_all([page_ok, page_http_error, page_runtime_error])
        session.flush()

        session.add_all(
            [
                Link(
                    crawl_job_id=crawl_job_id,
                    source_page_id=page_ok.id,
                    source_url=page_ok.url,
                    target_url="https://example.com/internal-a",
                    target_normalized_url="https://example.com/internal-a",
                    target_domain="example.com",
                    anchor_text="Internal A",
                    rel_attr="",
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job_id,
                    source_page_id=page_ok.id,
                    source_url=page_ok.url,
                    target_url="https://example.com/internal-b",
                    target_normalized_url="https://example.com/internal-b",
                    target_domain="example.com",
                    anchor_text="Internal B",
                    rel_attr="",
                    is_nofollow=False,
                    is_internal=True,
                ),
                Link(
                    crawl_job_id=crawl_job_id,
                    source_page_id=page_ok.id,
                    source_url=page_ok.url,
                    target_url="https://external.test/out",
                    target_normalized_url="https://external.test/out",
                    target_domain="external.test",
                    anchor_text="External",
                    rel_attr="nofollow",
                    is_nofollow=True,
                    is_internal=False,
                ),
            ]
        )
        session.commit()

    with SessionLocal() as session:
        crawl_job = session.get(CrawlJob, crawl_job_id)
        assert crawl_job is not None

        stats = update_job_stats(session, crawl_job)
        session.commit()

    assert stats == {
        "total_pages": 3,
        "total_internal_links": 2,
        "total_external_links": 1,
        "total_errors": 2,
    }

    with SessionLocal() as session:
        crawl_job = session.get(CrawlJob, crawl_job_id)
        assert crawl_job is not None
        assert crawl_job.stats_json == stats
