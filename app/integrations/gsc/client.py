from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.integrations.gsc.auth import GscAuthError, GscTokenStore


class GscApiError(RuntimeError):
    pass


class SearchConsoleApiClient:
    def __init__(self, token_store: GscTokenStore | None = None) -> None:
        self.token_store = token_store or GscTokenStore()

    def list_sites(self) -> list[dict[str, Any]]:
        service = self._build_service()
        try:
            response = service.sites().list().execute()
        except HttpError as exc:
            raise GscApiError(f"Search Console sites.list failed: {exc}") from exc
        return list(response.get("siteEntry", []))

    def query_search_analytics(self, property_uri: str, request: dict[str, Any]) -> list[dict[str, Any]]:
        service = self._build_service()
        try:
            response = service.searchanalytics().query(siteUrl=property_uri, body=request).execute()
        except HttpError as exc:
            raise GscApiError(f"Search Console searchanalytics.query failed for '{property_uri}': {exc}") from exc
        return list(response.get("rows", []))

    def _build_service(self):
        try:
            credentials = self.token_store.load_credentials()
        except GscAuthError:
            raise
        return build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
