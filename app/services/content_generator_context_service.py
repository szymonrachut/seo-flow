from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.services import content_generator_source_service


class ContentGeneratorContextServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "content_generator_context_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ContentGeneratorPromptContext:
    site_id: int
    site_domain: str
    site_root_url: str
    basis_crawl_job_id: int
    source_urls: list[str]
    source_pages_hash: str
    prompt_payload: dict[str, Any]


def build_content_generator_prompt_context(
    session: Session,
    *,
    site_id: int,
    active_crawl_id: int | None = None,
) -> ContentGeneratorPromptContext:
    try:
        selection = content_generator_source_service.select_site_content_generator_sources(
            session,
            site_id=site_id,
            active_crawl_id=active_crawl_id,
        )
    except content_generator_source_service.ContentGeneratorSourceServiceError as exc:
        raise ContentGeneratorContextServiceError(str(exc), code=exc.code) from exc

    prompt_payload = {
        "site": {
            "site_id": selection.site_id,
            "domain": selection.site_domain,
            "root_url": selection.site_root_url,
            "basis_crawl_job_id": selection.basis_crawl_job_id,
        },
        "source_selection": {
            "source_count": len(selection.source_pages),
            "source_urls": list(selection.source_urls),
        },
        "source_pages": [
            {
                "page_id": page.page_id,
                "url": page.url,
                "title": page.title,
                "h1": page.h1,
                "meta_description": page.meta_description,
                "page_type": page.page_type,
                "page_bucket": page.page_bucket,
                "page_type_confidence": round(float(page.page_type_confidence), 4),
                "priority_score": page.priority_score,
                "status_code": page.status_code,
                "content_type": page.content_type,
                "depth": page.depth,
                "word_count": page.word_count,
                "clicks_28d": page.clicks_28d,
                "impressions_28d": page.impressions_28d,
                "top_queries": list(page.top_queries),
                "selection_reason": page.selection_reason,
                "selection_score": round(float(page.selection_score), 2),
            }
            for page in selection.source_pages
        ],
    }
    source_pages_hash = _build_source_pages_hash(prompt_payload)

    return ContentGeneratorPromptContext(
        site_id=selection.site_id,
        site_domain=selection.site_domain,
        site_root_url=selection.site_root_url,
        basis_crawl_job_id=selection.basis_crawl_job_id,
        source_urls=list(selection.source_urls),
        source_pages_hash=source_pages_hash,
        prompt_payload=prompt_payload,
    )


def _build_source_pages_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
