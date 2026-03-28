from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.routes import (
    audit,
    cannibalization,
    crawl_jobs,
    exports,
    gsc,
    internal_linking,
    links,
    opportunities,
    pages,
    site_ai_review_editor,
    site_competitive_gap,
    site_content_generator_assets,
    site_content_recommendations,
    site_compare,
    sites,
    trends,
)

settings = get_settings()

app = FastAPI(
    title="SEO Crawler API",
    version="0.2.0",
    description="Local API for SEO crawler jobs, data and ETAP 2 audit reports.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_dev_origins),
    allow_origin_regex=settings.frontend_dev_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crawl_jobs.router)
app.include_router(sites.router)
app.include_router(site_ai_review_editor.router)
app.include_router(site_competitive_gap.router)
app.include_router(site_content_generator_assets.router)
app.include_router(site_content_recommendations.router)
app.include_router(site_compare.router)
app.include_router(pages.router)
app.include_router(links.router)
app.include_router(audit.router)
app.include_router(exports.router)
app.include_router(gsc.router)
app.include_router(opportunities.router)
app.include_router(trends.router)
app.include_router(internal_linking.router)
app.include_router(cannibalization.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
