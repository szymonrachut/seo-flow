from __future__ import annotations

from collections.abc import Sequence
from time import sleep
from typing import Any

import httpx

from app.core.config import get_settings


SEMSTORM_COMPETITORS_PATH = "/explorer/explorer-competitors/get-data.json"
SEMSTORM_KEYWORDS_PATH = "/explorer/explorer-keywords/get-data.json"
SEMSTORM_KEYWORDS_BASIC_STATS_PATH = "/explorer/explorer-keywords/basic-stats.json"
SEMSTORM_PAGE_SIZE_OPTIONS = (10, 25, 50)
SEMSTORM_MAX_DOMAINS_PER_REQUEST = 5


class SemstormIntegrationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        status_code: int = 502,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class SemstormConfigurationError(SemstormIntegrationError):
    pass


class SemstormApiClient:
    provider_name = "semstorm"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        services_token: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = str(base_url or settings.semstorm_base_url).strip().rstrip("/")
        self.services_token = str(services_token or settings.semstorm_services_token or "").strip()
        self.timeout_seconds = float(timeout_seconds or settings.semstorm_timeout_seconds)
        self.max_retries = max(0, int(max_retries if max_retries is not None else settings.semstorm_max_retries))
        self.retry_backoff_seconds = max(
            0.0,
            float(
                retry_backoff_seconds
                if retry_backoff_seconds is not None
                else settings.semstorm_retry_backoff_seconds
            ),
        )

    def is_available(self) -> bool:
        settings = get_settings()
        return bool(settings.semstorm_enabled and self.services_token and self.base_url)

    def get_competitors(
        self,
        *,
        domains: Sequence[str],
        result_type: str = "organic",
        competitors_type: str = "all",
        max_items: int = 10,
    ) -> list[dict[str, Any]]:
        prepared_domains = _prepare_domains(domains)
        payload: dict[str, Any] = {
            "domains": prepared_domains,
            "result_type": result_type,
            "pager": _build_pager(max_items),
        }
        if competitors_type == "all":
            payload["competitors_type"] = "all"
        raw = self._post(SEMSTORM_COMPETITORS_PATH, payload)
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        raise SemstormIntegrationError(
            "Semstorm competitors response has an unexpected shape.",
            code="invalid_response",
            status_code=502,
        )

    def get_keywords(
        self,
        *,
        domains: Sequence[str],
        result_type: str = "organic",
        max_items: int = 10,
        sorting: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        prepared_domains = _prepare_domains(domains)
        payload: dict[str, Any] = {
            "domains": prepared_domains,
            "result_type": result_type,
            "pager": _build_pager(max_items),
        }
        if sorting:
            payload["sorting"] = sorting
        raw = self._post(SEMSTORM_KEYWORDS_PATH, payload)
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        raise SemstormIntegrationError(
            "Semstorm keywords response has an unexpected shape.",
            code="invalid_response",
            status_code=502,
        )

    def get_keywords_basic_stats(
        self,
        *,
        domains: Sequence[str],
        result_type: str = "organic",
    ) -> dict[str, Any]:
        prepared_domains = _prepare_domains(domains)
        payload: dict[str, Any] = {
            "domains": prepared_domains,
            "result_type": result_type,
        }
        raw = self._post(SEMSTORM_KEYWORDS_BASIC_STATS_PATH, payload)
        if isinstance(raw, dict):
            return raw
        raise SemstormIntegrationError(
            "Semstorm basic stats response has an unexpected shape.",
            code="invalid_response",
            status_code=502,
        )

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        self._validate_configuration()
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        # Semstorm API v3 uses the services_token query parameter for auth.
        params = {"services_token": self.services_token}
        attempt = 0
        max_attempts = 1 + self.max_retries

        while attempt < max_attempts:
            attempt += 1
            try:
                with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False) as client:
                    response = client.post(url, params=params, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                raise SemstormIntegrationError(
                    "Semstorm request timed out.",
                    code="timeout",
                    status_code=504,
                ) from exc
            except httpx.RequestError as exc:
                raise SemstormIntegrationError(
                    "Semstorm connection failed.",
                    code="connection_error",
                    status_code=503,
                ) from exc

            if response.status_code == 503 and attempt < max_attempts:
                delay_seconds = self.retry_backoff_seconds * attempt
                if delay_seconds > 0:
                    sleep(delay_seconds)
                continue

            if response.is_error:
                raise _error_from_response(response)
            return _unwrap_payload(response)

        raise SemstormIntegrationError(
            "Semstorm request failed after retry attempts.",
            code="unavailable",
            status_code=503,
        )

    def _validate_configuration(self) -> None:
        if not self.base_url:
            raise SemstormConfigurationError(
                "SEMSTORM_BASE_URL is not configured.",
                code="missing_base_url",
                status_code=503,
            )
        if not self.services_token:
            raise SemstormConfigurationError(
                "SEMSTORM_SERVICES_TOKEN is not configured.",
                code="missing_services_token",
                status_code=503,
            )


def _prepare_domains(domains: Sequence[str]) -> list[str]:
    normalized = [str(domain).strip() for domain in domains if str(domain).strip()]
    if not normalized:
        raise SemstormIntegrationError(
            "Semstorm request requires at least one domain.",
            code="invalid_domains",
            status_code=400,
        )
    if len(normalized) > SEMSTORM_MAX_DOMAINS_PER_REQUEST:
        raise SemstormIntegrationError(
            f"Semstorm request supports up to {SEMSTORM_MAX_DOMAINS_PER_REQUEST} domains.",
            code="too_many_domains",
            status_code=400,
        )
    return normalized


def _build_pager(max_items: int) -> dict[str, int]:
    requested = max(1, int(max_items or 1))
    page_size = next((value for value in SEMSTORM_PAGE_SIZE_OPTIONS if requested <= value), SEMSTORM_PAGE_SIZE_OPTIONS[-1])
    return {"items_per_page": page_size, "page": 0}


def _unwrap_payload(response: httpx.Response) -> Any:
    try:
        payload = response.json()
    except ValueError as exc:
        raise SemstormIntegrationError(
            "Semstorm returned a non-JSON response.",
            code="invalid_response",
            status_code=502,
        ) from exc

    if isinstance(payload, dict):
        error_payload = payload.get("error")
        if error_payload:
            raise SemstormIntegrationError(
                _error_message_from_payload(error_payload) or "Semstorm returned an error payload.",
                code="provider_error",
                status_code=502,
            )
        if "results" in payload:
            return payload.get("results")
        if "result" in payload:
            return payload.get("result")
    return payload


def _error_from_response(response: httpx.Response) -> SemstormIntegrationError:
    message = "Semstorm request failed."
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if payload is not None:
        error_payload = payload.get("error", payload) if isinstance(payload, dict) else payload
        parsed_message = _error_message_from_payload(error_payload)
        if parsed_message:
            message = parsed_message

    if response.status_code == 400:
        return SemstormIntegrationError(message, code="upstream_bad_request", status_code=502)
    if response.status_code == 403:
        return SemstormIntegrationError(message, code="upstream_access_denied", status_code=502)
    if response.status_code == 404:
        return SemstormIntegrationError(message, code="upstream_not_found", status_code=502)
    if response.status_code == 409:
        return SemstormIntegrationError(message, code="upstream_conflict", status_code=503)
    if response.status_code == 503:
        return SemstormIntegrationError(message, code="unavailable", status_code=503)
    return SemstormIntegrationError(message, code="provider_error", status_code=502)


def _error_message_from_payload(payload: Any) -> str | None:
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    if isinstance(payload, list):
        for item in payload:
            parsed = _error_message_from_payload(item)
            if parsed:
                return parsed
        return None
    if not isinstance(payload, dict):
        return None

    for key in ("message", "error", "detail", "description"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
