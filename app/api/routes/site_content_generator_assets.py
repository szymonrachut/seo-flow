from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.content_generator import (
    SiteContentGeneratorAssetResponse,
    SiteContentGeneratorGenerateRequest,
    SiteContentGeneratorGenerateResponse,
)
from app.services import content_generator_service


router = APIRouter(prefix="/sites", tags=["site-content-generator-assets"])


def _raise_http_for_content_generator_error(exc: content_generator_service.ContentGeneratorServiceError) -> None:
    detail = str(exc)
    status_code = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/{site_id}/content-generator-assets", response_model=SiteContentGeneratorAssetResponse)
def get_site_content_generator_assets(
    site_id: int,
    active_crawl_id: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_db),
) -> SiteContentGeneratorAssetResponse:
    try:
        payload = content_generator_service.build_site_content_generator_asset_view(
            session,
            site_id,
            active_crawl_id=active_crawl_id,
        )
    except content_generator_service.ContentGeneratorServiceError as exc:
        _raise_http_for_content_generator_error(exc)
    return SiteContentGeneratorAssetResponse.model_validate(payload)


@router.post(
    "/{site_id}/content-generator-assets/generate",
    response_model=SiteContentGeneratorGenerateResponse,
)
def generate_site_content_generator_assets(
    site_id: int,
    input_data: SiteContentGeneratorGenerateRequest,
    session: Session = Depends(get_db),
) -> SiteContentGeneratorGenerateResponse:
    try:
        payload = content_generator_service.generate_site_content_assets_action(
            session,
            site_id=site_id,
            output_language=input_data.output_language,
        )
    except content_generator_service.ContentGeneratorServiceError as exc:
        _raise_http_for_content_generator_error(exc)
    return SiteContentGeneratorGenerateResponse.model_validate(payload)
