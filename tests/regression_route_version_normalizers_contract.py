from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from web.routes.normalizers import normalize_version_or_latest_fallback, parse_optional_version_int


@pytest.mark.parametrize(
    ("raw", "latest_version", "expected"),
    [
        (None, 7, 7),
        ("", 7, 7),
        ("abc", 7, 7),
        ("0", 7, 7),
        ("-1", 7, 7),
        ("9", 7, 9),
    ],
)
def test_normalize_version_or_latest_fallback_contract(raw, latest_version: int, expected: int) -> None:
    assert normalize_version_or_latest_fallback(raw, latest_version=latest_version) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("0", 0),
        ("-1", -1),
        ("9", 9),
    ],
)
def test_parse_optional_version_int_contract(raw, expected) -> None:
    assert parse_optional_version_int(raw, field="version") == expected


def test_parse_optional_version_int_rejects_non_integer_text() -> None:
    with pytest.raises(ValidationError) as exc_info:
        parse_optional_version_int("abc", field="version")

    assert exc_info.value.field == "version"
    assert "期望整数" in exc_info.value.message