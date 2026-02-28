from __future__ import annotations

from core.services.common.normalize import normalize_text


def test_normalize_text_none_and_blank() -> None:
    assert normalize_text(None) is None
    assert normalize_text("") is None
    assert normalize_text("   ") is None


def test_normalize_text_str_and_non_str() -> None:
    assert normalize_text(" a ") == "a"
    assert normalize_text("0") == "0"
    assert normalize_text(0) == "0"
    assert normalize_text(123) == "123"

