from app.core.text_processing import collapse_whitespace, normalize_text_for_hash


def test_collapse_whitespace_preserves_polish_diacritics() -> None:
    assert collapse_whitespace("  Zażółć   gęślą   jaźń  ") == "Zażółć gęślą jaźń"


def test_normalize_text_for_hash_remains_ascii_insensitive() -> None:
    assert normalize_text_for_hash("Zażółć gęślą jaźń") == "zazolc gesla jazn"
