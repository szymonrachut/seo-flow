from __future__ import annotations

from typing import Any

from app.core.text_processing import collapse_whitespace


def build_fetch_diagnostics_payload(
    *,
    was_rendered: bool = False,
    render_attempted: bool = False,
    fetch_mode_used: str | None = None,
    js_heavy_like: bool = False,
    render_reason: str | None = None,
    render_error_message: str | None = None,
    robots_meta: str | None = None,
    x_robots_tag: str | None = None,
    schema_count: int | None = None,
    schema_types: list[str] | None = None,
    visible_text_truncated: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "was_rendered": bool(was_rendered),
        "render_attempted": bool(render_attempted),
        "js_heavy_like": bool(js_heavy_like),
    }
    if fetch_mode_used:
        payload["fetch_mode_used"] = str(fetch_mode_used)[:32]
    if render_reason:
        payload["render_reason"] = str(render_reason)
    if render_error_message:
        payload["render_error_message"] = str(render_error_message)
    if robots_meta:
        payload["robots_meta"] = str(robots_meta)
    if x_robots_tag:
        payload["x_robots_tag"] = str(x_robots_tag)
    normalized_schema_types = [
        str(value).strip()
        for value in (schema_types or [])
        if str(value).strip()
    ]
    if schema_count is not None:
        payload["schema_count"] = max(0, int(schema_count))
    elif normalized_schema_types:
        payload["schema_count"] = len(normalized_schema_types)
    if normalized_schema_types:
        payload["schema_types"] = normalized_schema_types
    if visible_text_truncated is not None:
        payload["visible_text_truncated"] = bool(visible_text_truncated)
    return payload


def get_fetch_diagnostics(page: Any) -> dict[str, Any]:
    payload = getattr(page, "fetch_diagnostics_json", None)
    return dict(payload) if isinstance(payload, dict) else {}


def get_page_robots_meta(page: Any) -> str | None:
    diagnostics = get_fetch_diagnostics(page)
    value = diagnostics.get("robots_meta") if diagnostics else getattr(page, "robots_meta", None)
    return str(value) if isinstance(value, str) and value.strip() else None


def get_page_x_robots_tag(page: Any) -> str | None:
    diagnostics = get_fetch_diagnostics(page)
    value = diagnostics.get("x_robots_tag") if diagnostics else getattr(page, "x_robots_tag", None)
    return str(value) if isinstance(value, str) and value.strip() else None


def get_page_schema_types(page: Any) -> list[str]:
    diagnostics = get_fetch_diagnostics(page)
    raw_value = diagnostics.get("schema_types") if diagnostics else getattr(page, "schema_types_json", None)
    if not isinstance(raw_value, list):
        return []
    return [str(value).strip() for value in raw_value if str(value).strip()]


def get_page_schema_count(page: Any) -> int:
    diagnostics = get_fetch_diagnostics(page)
    raw_value = diagnostics.get("schema_count") if diagnostics else getattr(page, "schema_count", None)
    try:
        if raw_value is not None:
            return max(0, int(raw_value))
    except (TypeError, ValueError):
        pass
    return len(get_page_schema_types(page))


def get_page_schema_present(page: Any) -> bool:
    return get_page_schema_count(page) > 0 or bool(get_page_schema_types(page))


def get_page_visible_text_chars(page: Any) -> int:
    return len(collapse_whitespace(getattr(page, "visible_text", None)))


def get_page_word_count(page: Any) -> int:
    visible_text = collapse_whitespace(getattr(page, "visible_text", None))
    if not visible_text:
        raw_word_count = getattr(page, "word_count", None)
        try:
            return max(0, int(raw_word_count))
        except (TypeError, ValueError):
            return 0
    return len(visible_text.split())


def get_page_visible_text_truncated(page: Any) -> bool:
    diagnostics = get_fetch_diagnostics(page)
    value = (
        diagnostics.get("visible_text_truncated")
        if diagnostics
        else getattr(page, "visible_text_truncated", None)
    )
    return bool(value) if isinstance(value, bool) else False
