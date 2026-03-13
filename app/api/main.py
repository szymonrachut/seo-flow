from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.routes import audit, crawl_jobs, exports, links, pages

settings = get_settings()

app = FastAPI(
    title="SEO Crawler API",
    version="0.2.0",
    description="Local API for SEO crawler jobs, data and ETAP 2 audit reports.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_dev_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crawl_jobs.router)
app.include_router(pages.router)
app.include_router(links.router)
app.include_router(audit.router)
app.include_router(exports.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
