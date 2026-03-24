from __future__ import annotations


def abort_playwright_request(request) -> bool:  # type: ignore[no-untyped-def]
    resource_type = getattr(request, "resource_type", "")
    return resource_type in {"font", "image", "media", "stylesheet"}
