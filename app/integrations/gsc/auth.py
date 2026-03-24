from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.core.config import get_settings

GSC_SCOPES = ("https://www.googleapis.com/auth/webmasters.readonly",)
STATE_TTL_MINUTES = 15
logger = logging.getLogger(__name__)


class GscAuthError(RuntimeError):
    pass


@dataclass(slots=True)
class OAuthStatePayload:
    state: str
    redirect_url: str
    created_at: str
    code_verifier: str | None = None


class GscTokenStore:
    def __init__(self, path: str | None = None) -> None:
        settings = get_settings()
        self.path = Path(path or settings.gsc_token_path)

    def has_token(self) -> bool:
        return self.path.exists()

    def load_credentials(self) -> Credentials:
        if not self.path.exists():
            raise GscAuthError(
                f"Google Search Console token file is missing at '{self.path}'. Start OAuth first."
            )

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive local file guard
            raise GscAuthError(f"Could not parse GSC token file '{self.path}'.") from exc

        credentials = Credentials.from_authorized_user_info(payload, scopes=list(GSC_SCOPES))
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self.save_credentials(credentials)

        if not credentials.valid:
            raise GscAuthError("Stored Google credentials are invalid. Re-run the OAuth flow.")

        return credentials

    def save_credentials(self, credentials: Credentials) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(credentials.to_json(), encoding="utf-8")


class GscOAuthStateStore:
    def __init__(self, path: str | None = None) -> None:
        settings = get_settings()
        self.path = Path(path or settings.gsc_oauth_state_path)

    def save(self, payload: OAuthStatePayload) -> None:
        state_map = self._load_map()
        state_map[payload.state] = asdict(payload)
        self._save_map(state_map)

    def pop(self, state: str) -> OAuthStatePayload:
        state_map = self._load_map()
        payload = state_map.pop(state, None)
        self._save_map(state_map)
        if payload is None:
            raise GscAuthError("OAuth state is missing or expired. Start the GSC connection flow again.")

        created_at = datetime.fromisoformat(payload["created_at"])
        if datetime.now(timezone.utc) - created_at > timedelta(minutes=STATE_TTL_MINUTES):
            raise GscAuthError("OAuth state expired. Start the GSC connection flow again.")

        return OAuthStatePayload(**payload)

    def _load_map(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:  # pragma: no cover - defensive local file guard
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_map(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def ensure_client_secrets_file() -> Path:
    settings = get_settings()
    client_secrets_path = Path(settings.gsc_client_secrets_path)
    if not client_secrets_path.exists():
        raise GscAuthError(
            f"Google OAuth client secrets file is missing at '{client_secrets_path}'. "
            "Add credentials.json before starting the GSC flow."
        )
    return client_secrets_path


def build_authorization_url(
    *,
    redirect_url: str,
    state_store: GscOAuthStateStore | None = None,
) -> str:
    settings = get_settings()
    flow = Flow.from_client_secrets_file(
        str(ensure_client_secrets_file()),
        scopes=list(GSC_SCOPES),
    )
    flow.redirect_uri = settings.gsc_oauth_redirect_uri
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    resolved_state_store = state_store or GscOAuthStateStore()
    resolved_state_store.save(
        OAuthStatePayload(
            state=state,
            redirect_url=redirect_url,
            created_at=datetime.now(timezone.utc).isoformat(),
            code_verifier=flow.code_verifier,
        )
    )
    return authorization_url


def exchange_code_for_credentials(
    *,
    state: str,
    code: str,
    state_store: GscOAuthStateStore | None = None,
    token_store: GscTokenStore | None = None,
) -> OAuthStatePayload:
    settings = get_settings()
    resolved_state_store = state_store or GscOAuthStateStore()
    resolved_token_store = token_store or GscTokenStore()
    state_payload = resolved_state_store.pop(state)
    if not state_payload.code_verifier:
        raise GscAuthError("OAuth state is missing the PKCE code verifier. Restart the GSC connection flow.")

    flow = Flow.from_client_secrets_file(
        str(ensure_client_secrets_file()),
        scopes=list(GSC_SCOPES),
        state=state,
        code_verifier=state_payload.code_verifier,
        autogenerate_code_verifier=False,
    )
    flow.redirect_uri = settings.gsc_oauth_redirect_uri
    try:
        flow.fetch_token(code=code)
    except Exception as exc:  # pragma: no cover - library-specific failures vary by environment
        logger.exception("Google OAuth token exchange failed for redirect URI '%s'.", settings.gsc_oauth_redirect_uri)
        error_detail = _describe_google_oauth_exception(exc)
        raise GscAuthError(
            f"Google OAuth token exchange failed: {error_detail}"
        ) from exc

    try:
        resolved_token_store.save_credentials(flow.credentials)
    except OSError as exc:  # pragma: no cover - local filesystem guard
        logger.exception("Could not persist Google OAuth token at '%s'.", resolved_token_store.path)
        raise GscAuthError(
            f"Google OAuth succeeded, but the token could not be saved to '{resolved_token_store.path}'."
        ) from exc

    return state_payload


def _describe_google_oauth_exception(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            payload = response.json()
        except Exception:  # pragma: no cover - defensive parsing fallback
            payload = None

        if isinstance(payload, dict):
            error = str(payload.get("error") or "").strip()
            error_description = str(payload.get("error_description") or "").strip()
            combined = ": ".join(part for part in [error, error_description] if part)
            if combined:
                if error == "invalid_grant":
                    return (
                        f"{combined}. Common causes: reused or expired authorization code, system clock skew, "
                        "or redirect URI mismatch."
                    )
                return combined

        response_text = str(getattr(response, "text", "") or "").strip()
        if response_text:
            return response_text

    description = str(getattr(exc, "description", "") or "").strip()
    if description:
        error_code = str(getattr(exc, "error", "") or "").strip()
        return ": ".join(part for part in [error_code, description] if part)

    message = str(exc).strip()
    if message:
        return message

    return (
        "Check the configured redirect URI, OAuth client type, system clock, "
        "and restart the GSC connection flow."
    )
