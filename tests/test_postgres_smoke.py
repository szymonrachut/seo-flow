from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.models import CrawlJob, CrawlJobStatus, Page, Site

pytestmark = pytest.mark.postgres_smoke


def require_postgres_smoke_enabled() -> None:
    if os.environ.get("RUN_POSTGRES_SMOKE") != "1":
        pytest.skip("Postgres smoke is disabled. Set RUN_POSTGRES_SMOKE=1 to run.", allow_module_level=False)


def get_postgres_database_url() -> str:
    database_url = os.environ.get("POSTGRES_SMOKE_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_SMOKE_DATABASE_URL / DATABASE_URL is not set.", allow_module_level=False)
    if not database_url.startswith("postgresql+psycopg://"):
        pytest.skip("Postgres smoke requires DATABASE_URL in postgresql+psycopg format.", allow_module_level=False)
    return database_url


def truncate_application_tables(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE links, pages, crawl_jobs, sites RESTART IDENTITY CASCADE"))


class PostgresSmokeSiteHandler(BaseHTTPRequestHandler):
    ROOT_HTML = """
    <html>
      <head>
        <title>Home</title>
        <link rel="canonical" href="/" />
        <meta name="robots" content="noindex, follow" />
        <meta name="description" content=" Home page desc " />
      </head>
      <body>
        <h1> Home Header </h1>
        <a href="/about"> About us </a>
        <a href="/about#team"> About team </a>
        <a href="/go"> Go redirect </a>
        <a href="/broken"> Broken page </a>
        <a href="/file.pdf"> PDF file </a>
        <a href="https://external.example/out"> External </a>
        <a href="mailto:test@example.com"> Mail </a>
      </body>
    </html>
    """

    ABOUT_HTML = """
    <html>
      <head><title>About</title></head>
      <body>
        <h1> About Header </h1>
        <a href="/"> Home </a>
        <a href="https://external.example/about-out"> External 2 </a>
      </body>
    </html>
    """

    FINAL_HTML = """
    <html>
      <head><title>Final</title></head>
      <body><h1>Final Header</h1></body>
    </html>
    """

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/":
            self._send_html(200, self.ROOT_HTML)
            return
        if path == "/about":
            self._send_html(200, self.ABOUT_HTML)
            return
        if path == "/go":
            self.send_response(302)
            self.send_header("Location", "/final")
            self.end_headers()
            return
        if path == "/final":
            self._send_html(200, self.FINAL_HTML)
            return
        if path == "/broken":
            self._send_html(404, "<html><body><h1>Not Found</h1></body></html>")
            return
        if path == "/file.pdf":
            body = b"%PDF-1.4 fake"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._send_html(404, "<html><body><h1>Not Found</h1></body></html>")

    def log_message(self, format, *args) -> None:  # noqa: A003
        return

    def _send_html(self, status: int, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@contextlib.contextmanager
def run_local_site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), PostgresSmokeSiteHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture(scope="session")
def postgres_database_url() -> str:
    require_postgres_smoke_enabled()
    return get_postgres_database_url()


@pytest.fixture(scope="session", autouse=True)
def migrated_postgres_database(postgres_database_url: str) -> None:
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DATABASE_URL"] = postgres_database_url
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert migration.returncode == 0, migration.stderr or migration.stdout


def test_postgres_schema_constraints_and_mutable_json(postgres_database_url: str) -> None:
    engine = create_engine(postgres_database_url)
    truncate_application_tables(engine)
    inspector = inspect(engine)

    assert {"sites", "crawl_jobs", "pages", "links"}.issubset(set(inspector.get_table_names()))

    page_unique_constraints = {item["name"] for item in inspector.get_unique_constraints("pages")}
    assert "uq_pages_crawl_job_id_normalized_url" in page_unique_constraints

    page_index_names = {item["name"] for item in inspector.get_indexes("pages")}
    assert {"ix_pages_crawl_job_id", "ix_pages_status_code", "ix_pages_is_internal", "ix_pages_depth"}.issubset(
        page_index_names
    )
    page_columns = {item["name"] for item in inspector.get_columns("pages")}
    assert {"canonical_url", "robots_meta", "content_type", "response_time_ms"}.issubset(page_columns)

    link_index_names = {item["name"] for item in inspector.get_indexes("links")}
    assert {"ix_links_crawl_job_id", "ix_links_source_page_id", "ix_links_target_domain", "ix_links_is_internal"}.issubset(
        link_index_names
    )

    with engine.connect() as connection:
        enum_values = connection.execute(
            text(
                """
                SELECT e.enumlabel
                FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                WHERE t.typname = 'crawl_job_status'
                ORDER BY e.enumsortorder
                """
            )
        ).scalars().all()
    assert enum_values == ["pending", "running", "finished", "failed", "stopped"]

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with SessionLocal() as session:
        site = Site(root_url="https://example.com/", domain="example.com")
        session.add(site)
        session.flush()

        job = CrawlJob(
            site_id=site.id,
            status=CrawlJobStatus.PENDING,
            settings_json={"max_urls": 10},
            stats_json={},
        )
        session.add(job)
        session.commit()

        job.stats_json["total_pages"] = 1
        session.commit()
        session.refresh(job)
        assert job.stats_json == {"total_pages": 1}

        first_page = Page(
            crawl_job_id=job.id,
            url="https://example.com/a",
            normalized_url="https://example.com/a",
            final_url="https://example.com/a",
            status_code=200,
            title="A",
            meta_description=None,
            h1=None,
            is_internal=True,
            depth=0,
            fetched_at=None,
            error_message=None,
        )
        session.add(first_page)
        session.commit()

        duplicate_page = Page(
            crawl_job_id=job.id,
            url="https://example.com/a?dup=1",
            normalized_url="https://example.com/a",
            final_url="https://example.com/a",
            status_code=200,
            title=None,
            meta_description=None,
            h1=None,
            is_internal=True,
            depth=0,
            fetched_at=None,
            error_message=None,
        )
        session.add(duplicate_page)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    engine.dispose()


def test_postgres_crawl_job_end_to_end_smoke(postgres_database_url: str) -> None:
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DATABASE_URL"] = postgres_database_url

    engine = create_engine(postgres_database_url)
    truncate_application_tables(engine)

    with run_local_site() as base_url:
        crawl = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.cli.run_crawl",
                f"{base_url}/",
                "--max-urls",
                "20",
                "--max-depth",
                "3",
                "--delay",
                "0",
            ],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert crawl.returncode == 0, crawl.stderr or crawl.stdout

    with engine.connect() as connection:
        crawl_job_row = connection.execute(
            text("SELECT id, status, stats_json FROM crawl_jobs ORDER BY id DESC LIMIT 1")
        ).first()
        assert crawl_job_row is not None
        crawl_job_id = int(crawl_job_row.id)
        assert crawl_job_row.status == "finished"
        assert crawl_job_row.stats_json == {
            "total_pages": 4,
            "total_internal_links": 6,
            "total_external_links": 2,
            "total_errors": 1,
        }

        external_links = connection.execute(
            text("SELECT COUNT(*) FROM links WHERE crawl_job_id = :job_id AND is_internal = false"),
            {"job_id": crawl_job_id},
        ).scalar_one()
        assert external_links == 2

        external_pages = connection.execute(
            text(
                "SELECT COUNT(*) FROM pages WHERE crawl_job_id = :job_id "
                "AND normalized_url LIKE 'https://external.example/%'"
            ),
            {"job_id": crawl_job_id},
        ).scalar_one()
        assert external_pages == 0

        redirect_row = connection.execute(
            text(
                "SELECT final_url, depth FROM pages "
                "WHERE crawl_job_id = :job_id AND normalized_url = :normalized_url"
            ),
            {"job_id": crawl_job_id, "normalized_url": f"{base_url}/go"},
        ).first()
        assert redirect_row is not None
        assert redirect_row.final_url == f"{base_url}/final"
        assert int(redirect_row.depth) == 1

        root_seo_row = connection.execute(
            text(
                "SELECT canonical_url, robots_meta, content_type, response_time_ms "
                "FROM pages WHERE crawl_job_id = :job_id AND normalized_url = :normalized_url"
            ),
            {"job_id": crawl_job_id, "normalized_url": f"{base_url}/"},
        ).first()
        assert root_seo_row is not None
        assert root_seo_row.canonical_url == f"{base_url}/"
        assert root_seo_row.robots_meta == "noindex, follow"
        assert root_seo_row.content_type == "text/html; charset=utf-8"
        assert root_seo_row.response_time_ms is not None

    engine.dispose()
