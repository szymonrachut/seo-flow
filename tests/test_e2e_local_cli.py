from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class LocalSiteHandler(BaseHTTPRequestHandler):
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
        <a href="tel:+48123456789"> Phone </a>
        <a href="javascript:void(0)"> JS </a>
        <a href="#hash-only"> Hash </a>
      </body>
    </html>
    """

    ABOUT_HTML = """
    <html>
      <head>
        <title>About</title>
        <meta name="description" content=" About page desc " />
      </head>
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
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalSiteHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_cli_end_to_end_local_sample(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "e2e.sqlite3"
    database_url = f"sqlite+pysqlite:///{db_path.as_posix()}"

    env = os.environ.copy()
    env["DATABASE_URL"] = database_url

    with run_local_site() as base_url:
        migrate = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert migrate.returncode == 0, migrate.stderr or migrate.stdout

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

    with sqlite3.connect(db_path) as conn:
        crawl_job_row = conn.execute(
            "SELECT id, status, stats_json FROM crawl_jobs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert crawl_job_row is not None
        crawl_job_id = int(crawl_job_row[0])
        status = str(crawl_job_row[1])
        raw_stats = crawl_job_row[2]

        if isinstance(raw_stats, str):
            stats = json.loads(raw_stats)
        else:
            stats = raw_stats

        assert status == "finished"
        assert stats == {
            "total_pages": 4,
            "total_internal_links": 6,
            "total_external_links": 2,
            "total_errors": 1,
        }

        external_links = conn.execute(
            "SELECT COUNT(*) FROM links WHERE crawl_job_id = ? AND is_internal = 0",
            (crawl_job_id,),
        ).fetchone()[0]
        assert external_links == 2

        external_pages = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE crawl_job_id = ? AND normalized_url LIKE ?",
            (crawl_job_id, "https://external.example/%"),
        ).fetchone()[0]
        assert external_pages == 0

        about_count = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE crawl_job_id = ? AND normalized_url = ?",
            (crawl_job_id, f"{base_url}/about"),
        ).fetchone()[0]
        assert about_count == 1

        pdf_count = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE crawl_job_id = ? AND normalized_url = ?",
            (crawl_job_id, f"{base_url}/file.pdf"),
        ).fetchone()[0]
        assert pdf_count == 0

        redirect_row = conn.execute(
            "SELECT final_url, depth FROM pages WHERE crawl_job_id = ? AND normalized_url = ?",
            (crawl_job_id, f"{base_url}/go"),
        ).fetchone()
        assert redirect_row is not None
        assert redirect_row[0] == f"{base_url}/final"
        assert int(redirect_row[1]) == 1

        external_anchor = conn.execute(
            "SELECT anchor_text FROM links WHERE crawl_job_id = ? AND target_url = ?",
            (crawl_job_id, "https://external.example/out"),
        ).fetchone()
        assert external_anchor is not None
        assert external_anchor[0] == "External"

        root_seo_row = conn.execute(
            "SELECT canonical_url, robots_meta, content_type, response_time_ms "
            "FROM pages WHERE crawl_job_id = ? AND normalized_url = ?",
            (crawl_job_id, f"{base_url}/"),
        ).fetchone()
        assert root_seo_row is not None
        assert root_seo_row[0] == f"{base_url}/"
        assert root_seo_row[1] == "noindex, follow"
        assert root_seo_row[2] == "text/html; charset=utf-8"
        assert root_seo_row[3] is not None
