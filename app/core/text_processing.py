from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import unicodedata


VISIBLE_TEXT_CHAR_LIMIT = 12_000
TOPIC_WORD_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@dataclass(frozen=True, slots=True)
class PreparedVisibleText:
    full_text: str
    stored_text: str | None
    stored_chars: int
    truncated: bool
    content_hash: str | None
    word_count: int


def normalize_ascii(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.translate(
        str.maketrans(
            {
                "ł": "l",
                "Ł": "L",
            }
        )
    )
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    return ascii_only


def collapse_whitespace(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip()


def collapse_whitespace_ascii(value: str | None) -> str:
    normalized = normalize_ascii(value)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_text_for_hash(value: str | None) -> str:
    return collapse_whitespace_ascii(value).lower()


def hash_content_text(value: str | None) -> str | None:
    simplified = normalize_text_for_hash(value)
    if not simplified:
        return None
    return hashlib.sha256(simplified.encode("utf-8")).hexdigest()


def prepare_visible_text(value: str | None, *, limit: int = VISIBLE_TEXT_CHAR_LIMIT) -> PreparedVisibleText:
    full_text = collapse_whitespace(value)
    content_hash = hash_content_text(full_text)
    if not full_text:
        return PreparedVisibleText(
            full_text="",
            stored_text=None,
            stored_chars=0,
            truncated=False,
            content_hash=None,
            word_count=0,
        )

    stored_text = full_text[:limit]
    return PreparedVisibleText(
        full_text=full_text,
        stored_text=stored_text,
        stored_chars=len(stored_text),
        truncated=len(full_text) > limit,
        content_hash=content_hash,
        word_count=len(full_text.split()),
    )


def tokenize_topic_text(value: str | None, *, min_length: int = 3) -> list[str]:
    normalized = normalize_text_for_hash(value)
    if not normalized:
        return []
    tokens: list[str] = []
    for token in TOPIC_WORD_RE.findall(normalized):
        cleaned = token.strip("-")
        if len(cleaned) < min_length or cleaned.isdigit():
            continue
        tokens.append(cleaned)
    return tokens


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
