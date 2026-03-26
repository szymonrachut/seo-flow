from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ContentGeneratorAssetStatus = Literal["pending", "running", "ready", "failed"]


class SiteContentGeneratorAssetResponse(BaseModel):
    site_id: int
    has_assets: bool
    can_regenerate: bool
    active_crawl_id: int | None = None
    active_crawl_status: str | None = None
    status: ContentGeneratorAssetStatus | None = None
    basis_crawl_job_id: int | None = None
    surfer_custom_instructions: str | None = None
    seowriting_details_to_include: str | None = None
    introductory_hook_brief: str | None = None
    source_urls: list[str] = Field(default_factory=list)
    source_pages_hash: str | None = None
    prompt_version: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    generated_at: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None


class SiteContentGeneratorGenerateRequest(BaseModel):
    output_language: str = Field(default="en", min_length=2, max_length=8)


class SiteContentGeneratorGenerateResponse(BaseModel):
    success: bool
    generation_triggered: bool
    asset: SiteContentGeneratorAssetResponse
    error_code: str | None = None
    error_message: str | None = None
