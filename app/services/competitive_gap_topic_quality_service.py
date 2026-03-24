from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit

from app.core.text_processing import collapse_whitespace, dedupe_preserve_order, normalize_text_for_hash, tokenize_topic_text


TOPIC_GENERIC_TOKENS = {
    "a",
    "an",
    "about",
    "article",
    "and",
    "at",
    "blog",
    "business",
    "category",
    "company",
    "content",
    "for",
    "faq",
    "guide",
    "home",
    "index",
    "in",
    "is",
    "of",
    "on",
    "or",
    "page",
    "pages",
    "post",
    "posts",
    "service",
    "services",
    "support",
    "team",
    "the",
    "to",
    "with",
}
TITLE_WEIGHT = 5.0
H1_WEIGHT = 6.0
META_WEIGHT = 3.0
URL_WEIGHT = 2.0
BODY_WEIGHT = 0.8
MAX_BODY_TOKENS = 220
PRIMARY_TOKEN_LIMIT = 4
SECONDARY_TOKEN_LIMIT = 8

_CERTIFICATE_TOKENS = {
    "certificate",
    "certificates",
    "certified",
    "certyfikat",
    "certyfikaty",
}
_GALLERY_TOKENS = {"gallery", "galeria", "portfolio"}
_CONTACT_TOKENS = {"contact", "contact-us", "kontakt", "skontaktuj", "telefon", "email"}
_LOCATION_TOKENS = {
    "consultation",
    "consultations",
    "consulting-point",
    "konsultacyjne",
    "konsultacyjny",
    "location",
    "locations",
    "lokalizacja",
    "lokalizacje",
    "office",
    "offices",
    "point",
    "points",
    "punkt",
    "punkty",
}
_ABOUT_TOKENS = {"about", "about-us", "company", "firma", "o-nas", "team", "zespol"}
_PARTNER_TOKENS = {"dostawca", "dostawcy", "partner", "partnerzy", "partners", "vendor", "vendors"}
_BRAND_PAGE_TOKENS = {"brand", "brands", "marka", "marki"}
_SUPPORT_TOKENS = {"customer-service", "help", "knowledge-base", "pomoc", "support", "support-center"}
_UTILITY_PAGE_TYPES = {"about", "contact", "legal", "location", "utility"}


@dataclass(frozen=True, slots=True)
class TopicQualitySignals:
    dominant_topic_label: str | None
    dominant_topic_key: str | None
    primary_tokens: list[str]
    secondary_tokens: list[str]
    normalized_terms: list[str]
    page_role_hint: str
    title_h1_alignment_score: float
    meta_support_score: float
    body_conflict_score: float
    boilerplate_contamination_score: float
    dominant_topic_strength: float
    weak_evidence_flag: bool
    weak_evidence_reason: str | None

    def as_debug_payload(self) -> dict[str, Any]:
        return {
            "dominant_topic_label": self.dominant_topic_label,
            "dominant_topic_key": self.dominant_topic_key,
            "normalized_terms": list(self.normalized_terms),
            "page_role_hint": self.page_role_hint,
            "title_h1_alignment_score": round(self.title_h1_alignment_score, 2),
            "meta_support_score": round(self.meta_support_score, 2),
            "body_conflict_score": round(self.body_conflict_score, 2),
            "boilerplate_contamination_score": round(self.boilerplate_contamination_score, 2),
            "dominant_topic_strength": round(self.dominant_topic_strength, 2),
            "weak_evidence_flag": self.weak_evidence_flag,
            "weak_evidence_reason": self.weak_evidence_reason,
        }


def analyze_topic_quality(page: Any) -> TopicQualitySignals:
    title_tokens = _tokenize_value(_value(page, "title"))
    h1_tokens = _tokenize_value(_value(page, "h1"))
    meta_tokens = _tokenize_value(_value(page, "meta_description"))
    url_tokens = _tokenize_url(_value(page, "final_url") or _value(page, "normalized_url") or _value(page, "url"))
    body_counter = _body_token_counter(_value(page, "visible_text"))
    body_focus_tokens = [token for token, _count in body_counter.most_common(8)]

    title_h1_alignment_score = _overlap_ratio(set(title_tokens), set(h1_tokens))
    meta_anchor_tokens = set(title_tokens) | set(h1_tokens) | set(url_tokens)
    meta_support_score = _overlap_ratio(set(meta_tokens), meta_anchor_tokens) if meta_tokens else 0.0
    body_conflict_score = _body_conflict_score(body_focus_tokens, anchor_tokens=meta_anchor_tokens | set(meta_tokens))
    boilerplate_contamination_score = _boilerplate_contamination_score(
        body_counter,
        anchor_tokens=meta_anchor_tokens | set(meta_tokens),
    )

    anchor_weights: Counter[str] = Counter()
    support_weights: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    order = 0
    for token in title_tokens:
        anchor_weights[token] += TITLE_WEIGHT
        if token not in first_seen:
            first_seen[token] = order
            order += 1
    for token in h1_tokens:
        anchor_weights[token] += H1_WEIGHT
        if token not in first_seen:
            first_seen[token] = order
            order += 1
    for token in url_tokens:
        anchor_weights[token] += URL_WEIGHT
        if token not in first_seen:
            first_seen[token] = order
            order += 1
    for token in meta_tokens:
        support_weights[token] += META_WEIGHT
        if token not in first_seen:
            first_seen[token] = order
            order += 1
    for token in body_focus_tokens:
        if token in meta_anchor_tokens or token in meta_tokens:
            support_weights[token] += BODY_WEIGHT
            if token not in first_seen:
                first_seen[token] = order
                order += 1

    weights = Counter(anchor_weights)
    weights.update(support_weights)

    ranked_tokens = [
        token
        for token, _score in sorted(
            anchor_weights.items() or weights.items(),
            key=lambda item: (-item[1], first_seen.get(item[0], 999), len(item[0]), item[0]),
        )
    ]
    if not ranked_tokens:
        ranked_tokens = [
            token
            for token, _score in sorted(
                weights.items(),
                key=lambda item: (-item[1], len(item[0]), item[0]),
            )
        ]
    primary_tokens = _select_distinct_topic_tokens(ranked_tokens, limit=PRIMARY_TOKEN_LIMIT)
    secondary_tokens = _select_distinct_topic_tokens(
        [
            token
            for token, _score in sorted(
                weights.items(),
                key=lambda item: (-item[1], first_seen.get(item[0], 999), len(item[0]), item[0]),
            )
            if token not in primary_tokens
        ],
        limit=SECONDARY_TOKEN_LIMIT,
        existing_tokens=primary_tokens,
    )
    normalized_terms = dedupe_preserve_order(primary_tokens + secondary_tokens)

    dominant_topic_label = _build_dominant_topic_label(
        page,
        title_tokens=title_tokens,
        h1_tokens=h1_tokens,
        meta_tokens=meta_tokens,
        ranked_tokens=ranked_tokens,
        title_h1_alignment_score=title_h1_alignment_score,
    )
    dominant_topic_key = "-".join(primary_tokens[:PRIMARY_TOKEN_LIMIT]) if primary_tokens else None
    page_role_hint = _infer_page_role_hint(page, title_tokens=title_tokens, h1_tokens=h1_tokens, url_tokens=url_tokens)

    anchor_presence = min(1.0, len(set(title_tokens) | set(h1_tokens) | set(meta_tokens)) / 3.0)
    dominant_topic_strength = max(
        0.0,
        min(
            1.0,
            (
                0.32 * title_h1_alignment_score
                + 0.22 * meta_support_score
                + 0.18 * anchor_presence
                + 0.10 * min(1.0, len(primary_tokens) / 3.0)
                + 0.10 * (1.0 - body_conflict_score)
                + 0.08 * (1.0 - boilerplate_contamination_score)
            ),
        ),
    )
    weak_evidence_reason = _resolve_weak_evidence_reason(
        page,
        page_role_hint=page_role_hint,
        title_tokens=title_tokens,
        h1_tokens=h1_tokens,
        meta_tokens=meta_tokens,
        url_tokens=url_tokens,
        body_counter=body_counter,
        dominant_topic_strength=dominant_topic_strength,
        body_conflict_score=body_conflict_score,
    )
    weak_evidence_flag = weak_evidence_reason is not None

    return TopicQualitySignals(
        dominant_topic_label=dominant_topic_label,
        dominant_topic_key=dominant_topic_key,
        primary_tokens=list(primary_tokens),
        secondary_tokens=list(secondary_tokens),
        normalized_terms=list(normalized_terms),
        page_role_hint=page_role_hint,
        title_h1_alignment_score=title_h1_alignment_score,
        meta_support_score=meta_support_score,
        body_conflict_score=body_conflict_score,
        boilerplate_contamination_score=boilerplate_contamination_score,
        dominant_topic_strength=dominant_topic_strength,
        weak_evidence_flag=weak_evidence_flag,
        weak_evidence_reason=weak_evidence_reason,
    )


def update_page_topic_quality_debug(page: Any) -> TopicQualitySignals:
    signals = analyze_topic_quality(page)
    diagnostics = dict(getattr(page, "fetch_diagnostics_json", None) or {})
    diagnostics.update(signals.as_debug_payload())
    setattr(page, "fetch_diagnostics_json", diagnostics)
    return signals


def build_topic_quality_payload(page: Any) -> dict[str, Any]:
    return analyze_topic_quality(page).as_debug_payload()


def _build_dominant_topic_label(
    page: Any,
    *,
    title_tokens: list[str],
    h1_tokens: list[str],
    meta_tokens: list[str],
    ranked_tokens: list[str],
    title_h1_alignment_score: float,
) -> str | None:
    h1 = collapse_whitespace(_value(page, "h1"))
    if h1 and len(h1.split()) <= 8 and title_h1_alignment_score >= 0.24:
        return h1

    title = collapse_whitespace(_value(page, "title"))
    if title and len(title.split()) <= 10:
        return title

    meta_description = collapse_whitespace(_value(page, "meta_description"))
    if meta_description and meta_tokens:
        return " ".join(word.capitalize() for word in meta_tokens[:4])

    if ranked_tokens:
        return " ".join(token.replace("-", " ").capitalize() for token in ranked_tokens[:3])
    return None


def _resolve_weak_evidence_reason(
    page: Any,
    *,
    page_role_hint: str,
    title_tokens: list[str],
    h1_tokens: list[str],
    meta_tokens: list[str],
    url_tokens: list[str],
    body_counter: Counter[str],
    dominant_topic_strength: float,
    body_conflict_score: float,
) -> str | None:
    token_set = set(title_tokens) | set(h1_tokens) | set(meta_tokens) | set(url_tokens)
    page_type = _normalized(_value(page, "page_type"))

    if page_type == "contact" or token_set & _CONTACT_TOKENS:
        return "weak_contact"
    if page_type == "about" or token_set & _ABOUT_TOKENS:
        return "weak_about"
    if page_type == "location" or token_set & _LOCATION_TOKENS:
        return "weak_location"
    if token_set & _CERTIFICATE_TOKENS:
        return "weak_certificate"
    if token_set & _GALLERY_TOKENS:
        return "weak_gallery"
    title_like_token_set = set(title_tokens) | set(h1_tokens) | set(url_tokens)
    if token_set & _PARTNER_TOKENS:
        return "weak_partner_brand"
    if title_like_token_set & _BRAND_PAGE_TOKENS and page_role_hint != "money_page":
        return "weak_partner_brand"
    if page_type in _UTILITY_PAGE_TYPES or page_role_hint in {"trust_page", "utility_page"} or token_set & _SUPPORT_TOKENS:
        return "weak_support"
    if not token_set:
        return "weak_low_strength"
    if _has_actionable_url_topic(
        page_type=page_type,
        page_role_hint=page_role_hint,
        url_tokens=url_tokens,
        body_counter=body_counter,
    ):
        return None
    if dominant_topic_strength < 0.42:
        return "weak_low_strength"
    if dominant_topic_strength < 0.55 and body_conflict_score >= 0.62:
        return "weak_low_strength"
    return None


def _has_actionable_url_topic(
    *,
    page_type: str,
    page_role_hint: str,
    url_tokens: list[str],
    body_counter: Counter[str],
) -> bool:
    if page_type in _UTILITY_PAGE_TYPES or page_role_hint in {"trust_page", "utility_page", "location_page"}:
        return False

    expanded_url_tokens = dedupe_preserve_order(
        part
        for token in url_tokens
        for part in [token, *[piece for piece in token.split("-") if piece]]
    )
    cleaned_url_tokens = [
        token
        for token in expanded_url_tokens
        if token
        and len(token) >= 4
        and token not in TOPIC_GENERIC_TOKENS
        and token not in _CONTACT_TOKENS
        and token not in _ABOUT_TOKENS
        and token not in _LOCATION_TOKENS
        and token not in _CERTIFICATE_TOKENS
        and token not in _GALLERY_TOKENS
        and token not in _PARTNER_TOKENS
        and token not in _SUPPORT_TOKENS
    ]
    if len(cleaned_url_tokens) < 2:
        return False

    body_tokens = set(body_counter)
    supported_tokens = [token for token in cleaned_url_tokens if token in body_tokens]
    return len(supported_tokens) >= 1


def _infer_page_role_hint(
    page: Any,
    *,
    title_tokens: list[str],
    h1_tokens: list[str],
    url_tokens: list[str],
) -> str:
    page_type = _normalized(_value(page, "page_type"))
    token_set = set(title_tokens) | set(h1_tokens) | set(url_tokens)
    if page_type in {"service", "product", "category", "home"}:
        return "money_page"
    if page_type in {"faq", "blog_article", "blog_index"}:
        return "supporting_page"
    if page_type == "location":
        return "location_page"
    if page_type in {"about", "contact"}:
        return "trust_page"
    if page_type == "utility":
        return "utility_page"
    if token_set & _CONTACT_TOKENS:
        return "trust_page"
    if token_set & _LOCATION_TOKENS:
        return "location_page"
    if token_set & (_SUPPORT_TOKENS | _PARTNER_TOKENS):
        return "utility_page"
    return "other"


def _body_token_counter(value: Any) -> Counter[str]:
    body_tokens = _tokenize_value(value)
    return Counter(body_tokens[:MAX_BODY_TOKENS])


def _body_conflict_score(body_focus_tokens: list[str], *, anchor_tokens: set[str]) -> float:
    if not body_focus_tokens:
        return 0.0
    conflicting = [token for token in body_focus_tokens if token not in anchor_tokens]
    return min(1.0, len(conflicting) / max(1, len(body_focus_tokens)))


def _boilerplate_contamination_score(
    body_counter: Counter[str],
    *,
    anchor_tokens: set[str],
) -> float:
    if not body_counter:
        return 0.0
    repeated_non_anchor = sum(
        count
        for token, count in body_counter.items()
        if token not in anchor_tokens and count >= 3
    )
    total = sum(body_counter.values())
    return min(1.0, repeated_non_anchor / max(1, total))


def _tokenize_url(value: Any) -> list[str]:
    parsed = urlsplit(str(value or ""))
    path = unquote(parsed.path or "/")
    return _clean_tokens(tokenize_topic_text(path.replace("/", " ")))


def _tokenize_value(value: Any) -> list[str]:
    return _clean_tokens(tokenize_topic_text(str(value or "")))


def _clean_tokens(tokens: list[str]) -> list[str]:
    return [
        token
        for token in dedupe_preserve_order(tokens)
        if token and token not in TOPIC_GENERIC_TOKENS
    ]


def _select_distinct_topic_tokens(
    tokens: list[str],
    *,
    limit: int,
    existing_tokens: list[str] | None = None,
) -> list[str]:
    selected = list(existing_tokens or [])
    for token in tokens:
        if token in selected:
            continue
        parts = [part for part in token.split("-") if part]
        if len(parts) > 1 and all(part in selected for part in parts):
            continue
        if token in TOPIC_GENERIC_TOKENS:
            continue
        selected.append(token)
        if len(selected) >= limit + len(existing_tokens or []):
            break
    if existing_tokens:
        return selected[len(existing_tokens):]
    return selected[:limit]


def _overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return min(1.0, len(left & right) / max(1, len(left | right)))


def _normalized(value: Any) -> str:
    return normalize_text_for_hash(str(value or "")).replace("_", "-")


def _value(page: Any, field_name: str) -> Any:
    if isinstance(page, dict):
        return page.get(field_name)
    return getattr(page, field_name, None)
