from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/seo_crawler"
    log_level: str = "INFO"
    frontend_app_url: str = "http://127.0.0.1:5173"
    frontend_dev_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    frontend_dev_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    scrapy_user_agent: str = "seo-crawler/0.1 (+local)"
    scrapy_concurrent_requests: int = 8
    scrapy_download_timeout: int = 20

    crawl_default_max_urls: int = 500
    crawl_default_max_depth: int = 10
    crawl_default_request_delay: float = 0.25
    crawl_default_render_mode: str = "auto"
    crawl_default_render_timeout_ms: int = 8_000
    crawl_default_max_rendered_pages_per_job: int = 25

    gsc_client_secrets_path: str = ".local/worktree/gsc/credentials.json"
    gsc_token_path: str = ".local/worktree/gsc/token.json"
    gsc_oauth_state_path: str = ".local/worktree/gsc/oauth_state.json"
    gsc_oauth_redirect_uri: str = "http://127.0.0.1:8000/gsc/oauth/callback"
    gsc_default_top_queries_limit: int = 20
    gsc_metrics_row_limit: int = 25_000

    semstorm_enabled: bool = False
    semstorm_base_url: str = "https://api.semstorm.com/api-v3"
    semstorm_services_token: str | None = None
    semstorm_timeout_seconds: float = 20.0
    semstorm_max_retries: int = 2
    semstorm_retry_backoff_seconds: float = 1.0
    semstorm_brief_llm_enabled: bool = False
    semstorm_brief_llm_model: str = "gpt-5-mini"
    semstorm_brief_llm_timeout_seconds: float = 20.0
    semstorm_brief_engine_mode: Literal["auto", "mock", "llm"] = "auto"

    openai_api_key: str | None = None
    openai_llm_enabled: bool = False
    openai_model_competitor_extraction: str = "gpt-5-mini"
    openai_model_competitor_merge: str = "gpt-5.4-mini"
    openai_model_competitor_explanation: str = "gpt-5-mini"
    openai_model_content_generator: str = "gpt-5.4-mini"
    openai_model_editor_review: str = "gpt-5.4"
    openai_model_editor_rewrite: str = "gpt-5-mini"
    editor_review_engine_mode: Literal["auto", "mock", "llm"] = "auto"
    content_gap_read_model_mode: Literal["legacy", "hybrid", "reviewed_preferred"] = "legacy"
    openai_timeout_seconds: float = 20.0
    openai_max_retries: int = 2

    audit_title_too_short: int = 30
    audit_title_too_long: int = 60
    audit_meta_description_too_short: int = 70
    audit_meta_description_too_long: int = 160
    audit_thin_content_word_count: int = 150
    audit_oversized_page_bytes: int = 512_000

    # Extensions that should never be crawled as HTML pages.
    skip_extensions: tuple[str, ...] = (
        ".7z",
        ".avi",
        ".bmp",
        ".css",
        ".csv",
        ".doc",
        ".docx",
        ".gif",
        ".gz",
        ".ico",
        ".jpeg",
        ".jpg",
        ".js",
        ".json",
        ".m4a",
        ".m4v",
        ".mov",
        ".mp3",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".pdf",
        ".png",
        ".ppt",
        ".pptx",
        ".rar",
        ".svg",
        ".tar",
        ".tgz",
        ".txt",
        ".wav",
        ".webm",
        ".webp",
        ".woff",
        ".woff2",
        ".xls",
        ".xlsx",
        ".xml",
        ".zip",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
