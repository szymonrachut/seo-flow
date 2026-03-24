from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CrawlJob, Page

PAGE_TAXONOMY_VERSION = "11.1-v1"
UNCLASSIFIED_PAGE_TYPE_VERSION = "unclassified"

PAGE_TYPES: tuple[str, ...] = (
    "home",
    "category",
    "product",
    "service",
    "blog_article",
    "blog_index",
    "contact",
    "about",
    "faq",
    "location",
    "legal",
    "utility",
    "other",
)

PAGE_BUCKETS: tuple[str, ...] = ("commercial", "informational", "utility", "trust", "other")

PAGE_TYPE_PRIORITY: tuple[str, ...] = (
    "home",
    "utility",
    "legal",
    "contact",
    "faq",
    "about",
    "location",
    "product",
    "category",
    "service",
    "blog_article",
    "blog_index",
    "other",
)

PAGE_BUCKET_BY_TYPE: dict[str, str] = {
    "home": "commercial",
    "category": "commercial",
    "product": "commercial",
    "service": "commercial",
    "blog_article": "informational",
    "blog_index": "informational",
    "contact": "trust",
    "about": "trust",
    "faq": "informational",
    "location": "commercial",
    "legal": "trust",
    "utility": "utility",
    "other": "other",
}

MIN_CLASSIFICATION_SCORE = 3.0
MIN_CLEAR_GAP = 1.0
SITE_PATTERN_MIN_OCCURRENCES = 2

CONTENT_FIRST_SEGMENTS = {"blog", "blogi", "aktualnosci", "news", "poradnik", "poradniki", "artykuly", "knowledge-base", "baza-wiedzy"}
UTILITY_FIRST_SEGMENTS = {"search", "szukaj", "login", "logowanie", "account", "konto", "my-account", "cart", "koszyk", "checkout", "tag", "tags", "author", "feed", "admin", "panel", "wp-admin", "wp-json"}
LEGAL_TOKENS = {"privacy", "privacy-policy", "polityka-prywatnosci", "polityka-prywatnosci", "terms", "terms-and-conditions", "regulamin", "cookies", "cookie-policy", "rodo", "gdpr", "disclaimer", "accessibility", "dostepnosc"}

SCHEMA_SIGNAL_WEIGHTS: dict[str, dict[str, float]] = {
    "category": {
        "collectionpage": 5.5,
        "itemlist": 4.0,
        "offercatalog": 5.0,
    },
    "product": {
        "product": 7.5,
        "offer": 2.5,
    },
    "service": {
        "service": 7.0,
    },
    "blog_article": {
        "article": 7.0,
        "blogposting": 7.0,
        "newsarticle": 7.0,
        "reportagearticle": 7.0,
        "techarticle": 7.0,
    },
    "blog_index": {
        "blog": 4.5,
    },
    "contact": {
        "contactpage": 7.0,
    },
    "about": {
        "aboutpage": 7.0,
        "organization": 1.5,
        "person": 1.0,
    },
    "faq": {
        "faqpage": 7.0,
        "question": 3.0,
    },
    "location": {
        "localbusiness": 7.0,
        "place": 5.0,
        "store": 5.0,
        "postaladdress": 3.0,
    },
    "utility": {
        "searchresultspage": 7.0,
    },
}

PATH_TOKEN_SIGNAL_WEIGHTS: dict[str, dict[str, float]] = {
    "category": {
        "category": 4.5,
        "categories": 4.5,
        "kategoria": 4.5,
        "kategorie": 4.5,
        "collection": 4.0,
        "collections": 4.0,
        "catalog": 3.5,
        "katalog": 3.5,
        "shop": 2.0,
        "sklep": 2.0,
    },
    "product": {
        "product": 4.5,
        "products": 3.5,
        "produkt": 4.5,
        "produkty": 3.5,
        "sku": 4.0,
        "item": 3.0,
    },
    "service": {
        "service": 4.5,
        "services": 4.5,
        "usluga": 4.5,
        "uslugi": 4.5,
        "offer": 4.0,
        "oferta": 4.0,
        "solutions": 3.5,
        "rozwiazania": 3.5,
    },
    "contact": {
        "contact": 5.0,
        "kontakt": 5.0,
        "contact-us": 5.0,
        "get-in-touch": 4.5,
        "skontaktuj-sie": 4.5,
    },
    "about": {
        "about": 4.5,
        "about-us": 4.5,
        "o-nas": 4.5,
        "o-firmie": 4.5,
        "company": 3.0,
        "team": 3.0,
        "kim-jestesmy": 4.5,
    },
    "faq": {
        "faq": 5.0,
        "faqs": 5.0,
        "pytania": 4.5,
        "najczesciej-zadawane-pytania": 5.0,
        "questions": 4.0,
    },
    "location": {
        "location": 4.0,
        "locations": 4.5,
        "lokalizacja": 4.0,
        "lokalizacje": 4.5,
        "oddzial": 4.5,
        "oddzialy": 4.5,
        "showroom": 4.0,
        "salon": 4.0,
        "biuro": 4.0,
    },
    "legal": {
        "privacy": 5.0,
        "privacy-policy": 5.5,
        "polityka-prywatnosci": 5.5,
        "terms": 5.0,
        "terms-and-conditions": 5.5,
        "regulamin": 5.5,
        "cookies": 5.0,
        "cookie-policy": 5.5,
        "rodo": 5.5,
        "gdpr": 5.5,
        "accessibility": 4.5,
        "dostepnosc": 4.5,
    },
    "utility": {
        "search": 5.5,
        "szukaj": 5.5,
        "login": 5.5,
        "logowanie": 5.5,
        "account": 5.5,
        "konto": 5.5,
        "my-account": 5.5,
        "cart": 5.5,
        "koszyk": 5.5,
        "checkout": 5.5,
        "tag": 4.5,
        "tags": 4.5,
        "author": 4.0,
        "feed": 5.0,
        "admin": 5.5,
        "panel": 5.0,
        "sitemap": 5.0,
    },
}

TEXT_SIGNAL_WEIGHTS: dict[str, dict[str, float]] = {
    "category": {
        "category": 2.5,
        "kategoria": 2.5,
        "collection": 2.0,
        "catalog": 2.0,
        "katalog": 2.0,
    },
    "product": {
        "product": 2.5,
        "produkt": 2.5,
        "buy": 1.5,
        "price": 1.0,
        "cena": 1.0,
    },
    "service": {
        "service": 2.0,
        "services": 2.5,
        "usluga": 2.0,
        "uslugi": 2.5,
        "offer": 2.0,
        "oferta": 2.0,
        "solutions": 2.0,
    },
    "blog_article": {
        "guide": 1.5,
        "how to": 1.5,
        "tutorial": 1.5,
        "case study": 1.5,
        "poradnik": 1.5,
    },
    "blog_index": {
        "blog": 2.5,
        "news": 2.0,
        "aktualnosci": 2.5,
        "articles": 2.0,
        "poradniki": 2.0,
    },
    "contact": {
        "contact": 2.5,
        "kontakt": 2.5,
        "contact us": 2.5,
        "get in touch": 2.5,
    },
    "about": {
        "about": 2.0,
        "about us": 2.5,
        "o nas": 2.5,
        "our company": 2.0,
        "kim jestesmy": 2.5,
    },
    "faq": {
        "faq": 2.5,
        "frequently asked": 2.5,
        "pytania": 2.0,
    },
    "location": {
        "locations": 2.5,
        "lokalizacje": 2.5,
        "oddzial": 2.5,
        "showroom": 2.5,
        "biuro": 1.5,
    },
    "legal": {
        "privacy policy": 3.5,
        "polityka prywatnosci": 3.5,
        "regulamin": 3.5,
        "terms": 3.0,
        "cookies": 3.0,
        "cookie policy": 3.0,
        "rodo": 3.5,
    },
    "utility": {
        "search": 2.5,
        "szukaj": 2.5,
        "login": 2.5,
        "logowanie": 2.5,
        "checkout": 2.5,
        "koszyk": 2.5,
    },
}

SITE_PATTERN_SEGMENT_TO_TYPE: dict[str, str] = {
    "blog": "blog_article",
    "blogi": "blog_article",
    "aktualnosci": "blog_article",
    "news": "blog_article",
    "poradnik": "blog_article",
    "poradniki": "blog_article",
    "artykuly": "blog_article",
    "category": "category",
    "categories": "category",
    "kategoria": "category",
    "kategorie": "category",
    "collection": "category",
    "collections": "category",
    "product": "product",
    "products": "product",
    "produkt": "product",
    "produkty": "product",
    "service": "service",
    "services": "service",
    "uslugi": "service",
    "oferta": "service",
    "kontakt": "contact",
    "contact": "contact",
    "faq": "faq",
    "locations": "location",
    "lokalizacje": "location",
}

PAGE_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
PAGINATION_PATTERN = re.compile(r"/(?:page|strona)/\d+/?$")
UTILITY_FILENAME_PATTERN = re.compile(r"(?:^|/)(?:sitemap|sitemap_index)\.xml$")


@dataclass(frozen=True)
class PageTaxonomyClassification:
    page_type: str
    page_bucket: str
    page_type_confidence: float
    page_type_version: str
    page_type_rationale: str | None = None


@dataclass(frozen=True)
class JobPatternContext:
    segment_counts: dict[str, int]


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", ascii_only.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_slug(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    lowered = ascii_only.lower()
    cleaned = re.sub(r"[^a-z0-9/-]+", "-", lowered)
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned.strip("-/")


def _path_segments(url: str | None) -> list[str]:
    if not url:
        return []
    parsed = urlsplit(url)
    path = unquote(parsed.path or "/")
    normalized = _normalize_slug(path)
    if not normalized:
        return []
    return [segment for segment in normalized.split("/") if segment]


def _path_tokens(segments: list[str]) -> set[str]:
    tokens: set[str] = set()
    for segment in segments:
        tokens.update(PAGE_TOKEN_PATTERN.findall(segment))
    return tokens


def _normalize_schema_type(value: Any) -> str:
    if value is None:
        return ""
    raw = str(value).strip().lower()
    if not raw:
        return ""
    for separator in ("#", "/"):
        if separator in raw:
            raw = raw.rsplit(separator, 1)[-1]
    return raw


def _normalized_schema_types(schema_types: list[str] | None) -> set[str]:
    return {normalized for item in schema_types or [] if (normalized := _normalize_schema_type(item))}


def _pattern_context_for_pages(pages: list[Page]) -> JobPatternContext:
    counts: Counter[str] = Counter()
    for page in pages:
        segments = _path_segments(page.normalized_url or page.url)
        if not segments:
            continue
        first_segment = segments[0]
        if first_segment in SITE_PATTERN_SEGMENT_TO_TYPE:
            counts[first_segment] += 1
    return JobPatternContext(segment_counts=dict(counts))


def _add_signal(
    scores: dict[str, float],
    rationales: dict[str, list[tuple[float, str]]],
    page_type: str,
    signal: str,
    weight: float,
) -> None:
    scores[page_type] += weight
    rationales[page_type].append((weight, signal))


def _apply_keyword_signals(
    scores: dict[str, float],
    rationales: dict[str, list[tuple[float, str]]],
    *,
    candidates: set[str],
    weights_by_type: dict[str, dict[str, float]],
    signal_prefix: str,
) -> None:
    for page_type, token_weights in weights_by_type.items():
        for token, weight in token_weights.items():
            if token in candidates:
                _add_signal(scores, rationales, page_type, f"{signal_prefix}:{token}(+{weight:.1f})", weight)


def _apply_phrase_signals(
    scores: dict[str, float],
    rationales: dict[str, list[tuple[float, str]]],
    *,
    normalized_text: str,
    weights_by_type: dict[str, dict[str, float]],
    signal_prefix: str,
) -> None:
    if not normalized_text:
        return
    for page_type, phrase_weights in weights_by_type.items():
        for phrase, weight in phrase_weights.items():
            if phrase in normalized_text:
                _add_signal(scores, rationales, page_type, f"{signal_prefix}:{phrase}(+{weight:.1f})", weight)


def _resolve_best_type(scores: dict[str, float]) -> tuple[str, float, float]:
    ranking = sorted(
        PAGE_TYPES,
        key=lambda page_type: (
            -scores.get(page_type, 0.0),
            PAGE_TYPE_PRIORITY.index(page_type),
        ),
    )
    best_type = ranking[0]
    best_score = float(scores.get(best_type, 0.0))
    second_score = float(scores.get(ranking[1], 0.0)) if len(ranking) > 1 else 0.0
    return best_type, best_score, second_score


def _resolve_confidence(page_type: str, best_score: float, second_score: float) -> float:
    if page_type == "other":
        if best_score <= 0:
            return 0.1
        return round(min(0.39, 0.12 + (best_score / 12)), 2)

    base = 0.45 + min(best_score, 8.0) * 0.05
    gap_bonus = min(0.14, max(0.0, best_score - second_score) * 0.04)
    exact_bonus = 0.05 if best_score >= 7.0 else 0.0
    return round(min(0.98, base + gap_bonus + exact_bonus), 2)


def classify_page(
    *,
    url: str,
    normalized_url: str | None = None,
    title: str | None = None,
    h1: str | None = None,
    schema_types: list[str] | None = None,
    pattern_context: JobPatternContext | None = None,
) -> PageTaxonomyClassification:
    effective_url = normalized_url or url
    segments = _path_segments(effective_url)
    tokens = _path_tokens(segments)
    first_segment = segments[0] if segments else ""
    normalized_text = " ".join(part for part in [_normalize_text(title), _normalize_text(h1)] if part)
    normalized_schema_types = _normalized_schema_types(schema_types)
    parsed = urlsplit(effective_url)
    normalized_path = "/" + "/".join(segments) if segments else "/"

    scores = {page_type: 0.0 for page_type in PAGE_TYPES}
    rationales: dict[str, list[tuple[float, str]]] = defaultdict(list)

    if normalized_path == "/" and not parsed.query:
        _add_signal(scores, rationales, "home", "path:root(+9.0)", 9.0)

    if first_segment in CONTENT_FIRST_SEGMENTS:
        if len(segments) <= 1:
            _add_signal(scores, rationales, "blog_index", f"path:first_segment:{first_segment}(+5.5)", 5.5)
        else:
            _add_signal(scores, rationales, "blog_article", f"path:first_segment:{first_segment}(+5.5)", 5.5)

    if first_segment in UTILITY_FIRST_SEGMENTS:
        _add_signal(scores, rationales, "utility", f"path:first_segment:{first_segment}(+6.0)", 6.0)

    if tokens & LEGAL_TOKENS:
        matched = sorted(tokens & LEGAL_TOKENS)[0]
        _add_signal(scores, rationales, "legal", f"path:legal_token:{matched}(+5.5)", 5.5)

    if PAGINATION_PATTERN.search(parsed.path or ""):
        _add_signal(scores, rationales, "utility", "path:pagination(+4.5)", 4.5)

    if UTILITY_FILENAME_PATTERN.search((parsed.path or "").lower()):
        _add_signal(scores, rationales, "utility", "path:utility_file(+5.0)", 5.0)

    _apply_keyword_signals(
        scores,
        rationales,
        candidates=tokens | ({first_segment} if first_segment else set()),
        weights_by_type=PATH_TOKEN_SIGNAL_WEIGHTS,
        signal_prefix="path",
    )
    _apply_phrase_signals(
        scores,
        rationales,
        normalized_text=normalized_text,
        weights_by_type=TEXT_SIGNAL_WEIGHTS,
        signal_prefix="text",
    )

    for page_type, schema_weights in SCHEMA_SIGNAL_WEIGHTS.items():
        for schema_type, weight in schema_weights.items():
            if schema_type in normalized_schema_types:
                _add_signal(scores, rationales, page_type, f"schema:{schema_type}(+{weight:.1f})", weight)

    if "collectionpage" in normalized_schema_types and first_segment in CONTENT_FIRST_SEGMENTS:
        _add_signal(scores, rationales, "blog_index", "schema+path:collection_blog(+2.0)", 2.0)

    if "organization" in normalized_schema_types and normalized_path == "/":
        _add_signal(scores, rationales, "home", "schema:path_root_org(+1.5)", 1.5)

    if pattern_context and first_segment:
        occurrence_count = pattern_context.segment_counts.get(first_segment, 0)
        inferred_type = SITE_PATTERN_SEGMENT_TO_TYPE.get(first_segment)
        if inferred_type and occurrence_count >= SITE_PATTERN_MIN_OCCURRENCES:
            boost = min(2.5, 1.0 + (occurrence_count - SITE_PATTERN_MIN_OCCURRENCES) * 0.25)
            _add_signal(
                scores,
                rationales,
                inferred_type,
                f"site_pattern:{first_segment}({occurrence_count})(+{boost:.1f})",
                boost,
            )

    best_type, best_score, second_score = _resolve_best_type(scores)
    weak_signal = best_score < MIN_CLASSIFICATION_SCORE
    ambiguous_signal = best_score < (MIN_CLASSIFICATION_SCORE + 0.5) and (best_score - second_score) < MIN_CLEAR_GAP

    resolved_type = "other" if weak_signal or ambiguous_signal else best_type
    rationale_items = sorted(rationales.get(resolved_type, []), key=lambda item: (-item[0], item[1]))
    if resolved_type == "other":
        if best_score > 0:
            rationale = f"fallback:{best_type}({best_score:.1f}) gap={best_score - second_score:.1f}"
        else:
            rationale = "fallback:no_strong_signals"
    else:
        rationale = " | ".join(signal for _, signal in rationale_items[:4]) or None

    return PageTaxonomyClassification(
        page_type=resolved_type,
        page_bucket=PAGE_BUCKET_BY_TYPE[resolved_type],
        page_type_confidence=_resolve_confidence(resolved_type, best_score, second_score),
        page_type_version=PAGE_TAXONOMY_VERSION,
        page_type_rationale=rationale,
    )


def _page_needs_classification(page: Page) -> bool:
    return (
        page.page_type_version != PAGE_TAXONOMY_VERSION
        or page.page_type is None
        or page.page_bucket is None
        or page.page_type_confidence is None
    )


def ensure_page_taxonomy_for_job(session: Session, crawl_job_id: int) -> int:
    pages = session.scalars(select(Page).where(Page.crawl_job_id == crawl_job_id).order_by(Page.id.asc())).all()
    if not pages:
        return 0

    pattern_context = _pattern_context_for_pages(pages)
    updated = 0
    for page in pages:
        if not _page_needs_classification(page):
            continue
        classification = classify_page(
            url=page.url,
            normalized_url=page.normalized_url,
            title=page.title,
            h1=page.h1,
            schema_types=page.schema_types_json,
            pattern_context=pattern_context,
        )
        page.page_type = classification.page_type
        page.page_bucket = classification.page_bucket
        page.page_type_confidence = classification.page_type_confidence
        page.page_type_version = classification.page_type_version
        page.page_type_rationale = classification.page_type_rationale
        updated += 1

    if updated:
        session.flush()
        session.commit()
    return updated


def build_page_taxonomy_summary(session: Session, crawl_job_id: int) -> dict[str, Any]:
    crawl_job = session.get(CrawlJob, crawl_job_id)
    if crawl_job is None:
        raise ValueError(f"Crawl job {crawl_job_id} not found.")

    ensure_page_taxonomy_for_job(session, crawl_job_id)
    pages = session.scalars(select(Page).where(Page.crawl_job_id == crawl_job_id).order_by(Page.id.asc())).all()

    counts_by_page_type = {page_type: 0 for page_type in PAGE_TYPES}
    counts_by_page_bucket = {page_bucket: 0 for page_bucket in PAGE_BUCKETS}
    classified_pages = 0

    for page in pages:
        page_type = page.page_type or "other"
        page_bucket = page.page_bucket or PAGE_BUCKET_BY_TYPE.get(page_type, "other")
        if page.page_type_version == PAGE_TAXONOMY_VERSION:
            classified_pages += 1
        counts_by_page_type[page_type] = counts_by_page_type.get(page_type, 0) + 1
        counts_by_page_bucket[page_bucket] = counts_by_page_bucket.get(page_bucket, 0) + 1

    return {
        "crawl_job_id": crawl_job_id,
        "page_type_version": PAGE_TAXONOMY_VERSION,
        "total_pages": len(pages),
        "classified_pages": classified_pages,
        "counts_by_page_type": counts_by_page_type,
        "counts_by_page_bucket": counts_by_page_bucket,
    }
