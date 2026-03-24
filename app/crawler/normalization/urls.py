from __future__ import annotations

from collections.abc import Iterable
from posixpath import normpath
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import tldextract

# Use the bundled snapshot without touching the shared site-packages cache.
# This avoids flaky file-lock contention during local/API tests.
_DOMAIN_EXTRACTOR = tldextract.TLDExtract(cache_dir=None, suffix_list_urls=None)
_SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:")


def extract_host(url: str) -> str | None:
    parsed = urlsplit(url.strip())
    if not parsed.scheme or parsed.scheme.lower() not in {"http", "https"}:
        return None
    if not parsed.hostname:
        return None
    return parsed.hostname.lower().strip(".")


def extract_registered_domain(url_or_host: str) -> str | None:
    if "://" in url_or_host:
        host = extract_host(url_or_host)
        if not host:
            return None
    else:
        host = url_or_host.lower().strip(".")

    extracted = _DOMAIN_EXTRACTOR(host)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}".lower()
    return host


def normalize_url(url: str) -> str | None:
    if not url:
        return None

    raw = url.strip()
    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        return None
    if not parsed.hostname:
        return None

    hostname = parsed.hostname.lower().strip(".")
    port = parsed.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    userinfo = ""
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo = f"{userinfo}:{parsed.password}"
        userinfo = f"{userinfo}@"

    host_for_netloc = hostname
    if ":" in hostname and not hostname.startswith("["):
        host_for_netloc = f"[{hostname}]"

    netloc = f"{userinfo}{host_for_netloc}"
    if port:
        netloc = f"{netloc}:{port}"

    path = _normalize_path(parsed.path)
    query = _normalize_query(parsed.query)
    return urlunsplit((scheme, netloc, path, query, ""))


def resolve_url(base_url: str, candidate: str) -> str:
    return urljoin(base_url, candidate)


def is_internal_url(url: str, site_registered_domain: str) -> bool:
    target_domain = extract_registered_domain(url)
    if not target_domain:
        return False
    return target_domain == site_registered_domain.lower()


def should_skip_href(href: str | None) -> bool:
    if href is None:
        return True
    trimmed = href.strip()
    if not trimmed:
        return True
    if trimmed.startswith("#"):
        return True
    lowered = trimmed.lower()
    return lowered.startswith(_SKIP_SCHEMES)


def is_http_url(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def is_crawlable_document_url(url: str, blocked_extensions: Iterable[str]) -> bool:
    path = urlsplit(url).path.lower()
    if not path:
        return True

    for extension in blocked_extensions:
        ext = extension.lower()
        if path.endswith(ext):
            return False
    return True


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    normalized = normpath(path)
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if normalized == "/.":
        normalized = "/"
    if normalized != "/" and normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    return normalized


def _normalize_query(query: str) -> str:
    params = [
        (key, value)
        for key, value in parse_qsl(query, keep_blank_values=False)
        if key and value != ""
    ]
    params.sort(key=lambda pair: (pair[0], pair[1]))
    return urlencode(params, doseq=True)
