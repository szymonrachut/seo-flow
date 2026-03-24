from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit

from app.core.text_processing import normalize_text_for_hash
from app.services.competitive_gap_page_diagnostics import (
    get_page_robots_meta,
    get_page_visible_text_chars,
    get_page_word_count,
    get_page_x_robots_tag,
)
from app.services.competitive_gap_topic_quality_service import analyze_topic_quality
from app.services.seo_analysis import has_noindex_directive


SEMANTIC_EXCLUSION_REASONS: tuple[str, ...] = (
    "error_like",
    "non_indexable",
    "privacy_policy",
    "terms",
    "contact",
    "cart",
    "checkout",
    "account",
    "login",
    "register",
    "search",
    "tag",
    "archive",
    "utility_page",
    "weak_about",
    "weak_location",
    "weak_certificate",
    "weak_gallery",
    "weak_partner_brand",
    "weak_support",
    "weak_low_strength",
    "thin",
    "low_value",
)

_PRIVACY_TOKENS = {
    "cookie",
    "cookies",
    "cookie-policy",
    "cookies-policy",
    "gdpr",
    "polityka-prywatnosci",
    "privacy",
    "privacy-policy",
    "prywatnosc",
    "rodo",
}
_TERMS_TOKENS = {
    "accessibility",
    "conditions",
    "disclaimer",
    "dostepnosc",
    "regulamin",
    "terms",
    "terms-and-conditions",
    "warunki",
}
_CONTACT_TOKENS = {"contact", "contact-us", "kontakt", "skontaktuj-sie"}
_CART_TOKENS = {"cart", "koszyk"}
_CHECKOUT_TOKENS = {"checkout", "kasa", "zamowienie", "zamow"}
_ACCOUNT_TOKENS = {"account", "konto", "my-account"}
_LOGIN_TOKENS = {"log-in", "login", "logowanie", "sign-in", "signin"}
_REGISTER_TOKENS = {"join", "register", "registration", "rejestracja", "sign-up", "signup"}
_SEARCH_TOKENS = {"q", "query", "search", "search-results", "searchresultspage", "szukaj", "wyniki"}
_TAG_TOKENS = {"tag", "tags"}
_ARCHIVE_TOKENS = {"archive", "archives", "archiwum"}


@dataclass(frozen=True, slots=True)
class SemanticEligibilityResult:
    eligible: bool
    exclusion_reason: str | None


def resolve_semantic_eligibility(
    page: Any,
    *,
    match_terms: Iterable[str] | None = None,
) -> SemanticEligibilityResult:
    exclusion_reason = resolve_semantic_exclusion_reason(page, match_terms=match_terms)
    return SemanticEligibilityResult(
        eligible=exclusion_reason is None,
        exclusion_reason=exclusion_reason,
    )


def resolve_semantic_exclusion_reason(
    page: Any,
    *,
    match_terms: Iterable[str] | None = None,
) -> str | None:
    status_code = _int_or_none(_value(page, "status_code"))
    if status_code is None or not (200 <= status_code <= 299):
        return "error_like"

    if has_noindex_directive(_robots_meta(page), _x_robots_tag(page)):
        return "non_indexable"

    text_corpus = _text_corpus(page)
    page_type = _normalized_string(_value(page, "page_type"))

    if page_type == "legal" and _matches_any(text_corpus, _PRIVACY_TOKENS):
        return "privacy_policy"
    if _matches_any(text_corpus, _PRIVACY_TOKENS):
        return "privacy_policy"

    if page_type == "legal" or _matches_any(text_corpus, _TERMS_TOKENS):
        return "terms"
    if page_type == "contact" or _matches_any(text_corpus, _CONTACT_TOKENS):
        return "contact"
    if _matches_any(text_corpus, _CART_TOKENS):
        return "cart"
    if _matches_any(text_corpus, _CHECKOUT_TOKENS):
        return "checkout"
    if _matches_any(text_corpus, _ACCOUNT_TOKENS):
        return "account"
    if _matches_any(text_corpus, _LOGIN_TOKENS):
        return "login"
    if _matches_any(text_corpus, _REGISTER_TOKENS):
        return "register"
    if _matches_any(text_corpus, _SEARCH_TOKENS):
        return "search"
    if _matches_any(text_corpus, _TAG_TOKENS):
        return "tag"
    if _matches_any(text_corpus, _ARCHIVE_TOKENS):
        return "archive"
    if page_type == "utility":
        return "utility_page"

    quality_signals = analyze_topic_quality(page)
    word_count = _word_count(page)
    visible_text_chars = _visible_text_chars(page)
    if (
        word_count < 80
        and visible_text_chars < 400
        and float(quality_signals.dominant_topic_strength or 0.0) < 0.55
    ):
        return "thin"
    if not list(match_terms or ()):
        return "low_value"
    if quality_signals.weak_evidence_reason == "weak_contact":
        return "contact"
    if quality_signals.weak_evidence_reason in {
        "weak_about",
        "weak_location",
        "weak_certificate",
        "weak_gallery",
        "weak_partner_brand",
        "weak_support",
        "weak_low_strength",
    }:
        return quality_signals.weak_evidence_reason

    return None


def _text_corpus(page: Any) -> set[str]:
    values = [
        _normalized_string(_value(page, "page_type")),
        _normalized_string(_value(page, "normalized_url")),
        _normalized_string(_value(page, "final_url")),
        _normalized_string(_value(page, "title")),
        _normalized_string(_value(page, "h1")),
    ]
    tokens: set[str] = set()
    for value in values:
        if not value:
            continue
        normalized_value = (
            value.replace("/", " ")
            .replace(".", " ")
            .replace("-", " ")
            .replace("_", " ")
        )
        tokens.update(part for part in normalized_value.split() if part)
        parsed = urlsplit(value if value.startswith("http") else f"https://semantic.local/{value}")
        path = unquote(parsed.path or "/")
        normalized_path = (
            path.replace("/", " ")
            .replace(".", " ")
            .replace("-", " ")
            .replace("_", " ")
        )
        tokens.update(part for part in normalized_path.split() if part)
    return tokens


def _matches_any(values: set[str], patterns: set[str]) -> bool:
    return any(pattern in values for pattern in patterns)


def _normalized_string(value: Any) -> str:
    return normalize_text_for_hash(str(value or "")).replace("_", "-")


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _value(page: Any, field_name: str) -> Any:
    if isinstance(page, dict):
        return page.get(field_name)
    return getattr(page, field_name, None)


def _robots_meta(page: Any) -> str | None:
    if isinstance(page, dict):
        return _value(page, "robots_meta")
    return get_page_robots_meta(page)


def _x_robots_tag(page: Any) -> str | None:
    if isinstance(page, dict):
        return _value(page, "x_robots_tag")
    return get_page_x_robots_tag(page)


def _word_count(page: Any) -> int:
    if isinstance(page, dict):
        return _int_or_none(_value(page, "word_count")) or 0
    return get_page_word_count(page)


def _visible_text_chars(page: Any) -> int:
    if isinstance(page, dict):
        return _int_or_none(_value(page, "visible_text_chars")) or 0
    return get_page_visible_text_chars(page)
