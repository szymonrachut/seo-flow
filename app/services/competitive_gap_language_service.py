from __future__ import annotations

from typing import Any


DEFAULT_COMPETITIVE_GAP_LANGUAGE = "en"
SUPPORTED_COMPETITIVE_GAP_LANGUAGES = {"en", "pl"}
LANGUAGE_LABELS = {
    "en": "English",
    "pl": "Polish",
}


def normalize_output_language(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("pl"):
        return "pl"
    return DEFAULT_COMPETITIVE_GAP_LANGUAGE


def resolve_output_language(*values: Any) -> str:
    for value in values:
        normalized = normalize_output_language(value)
        if normalized in SUPPORTED_COMPETITIVE_GAP_LANGUAGES:
            return normalized
    return DEFAULT_COMPETITIVE_GAP_LANGUAGE


def output_language_name(value: Any) -> str:
    normalized = normalize_output_language(value)
    return LANGUAGE_LABELS.get(normalized, LANGUAGE_LABELS[DEFAULT_COMPETITIVE_GAP_LANGUAGE])


def output_language_instruction(value: Any) -> str:
    normalized = normalize_output_language(value)
    language_name = output_language_name(normalized)
    diacritics_instruction = ""
    if normalized == "pl":
        diacritics_instruction = " Use correct Polish diacritics in every free-text field."
    return (
        f"Write all free-text output fields in {language_name}. "
        f"Keep enum-like labels and JSON keys unchanged.{diacritics_instruction}"
    )
