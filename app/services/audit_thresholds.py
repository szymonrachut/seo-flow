from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class AuditThresholds:
    title_too_short: int
    title_too_long: int
    meta_description_too_short: int
    meta_description_too_long: int
    thin_content_word_count: int
    oversized_page_bytes: int


def get_audit_thresholds() -> AuditThresholds:
    settings = get_settings()
    return AuditThresholds(
        title_too_short=settings.audit_title_too_short,
        title_too_long=settings.audit_title_too_long,
        meta_description_too_short=settings.audit_meta_description_too_short,
        meta_description_too_long=settings.audit_meta_description_too_long,
        thin_content_word_count=settings.audit_thin_content_word_count,
        oversized_page_bytes=settings.audit_oversized_page_bytes,
    )
