from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from web.routes.normalizers import (
    default_version_to_latest,
    normalize_version_or_latest_fallback,
    parse_explicit_version_or_latest,
    parse_optional_version_int,
    resolve_route_version_or_latest,
)


@pytest.mark.parametrize(
    ("latest_version", "expected"),
    [
        (0, 0),
        (7, 7),
    ],
)
def test_default_version_to_latest_contract(latest_version: int, expected: int) -> None:
    assert default_version_to_latest(latest_version=latest_version) == expected


@pytest.mark.parametrize(
    ("raw", "latest_version", "expected"),
    [
        ("latest", 7, 7),
        ("LATEST", 7, 7),
        ("9", 7, 9),
    ],
)
def test_parse_explicit_version_or_latest_contract(raw, latest_version: int, expected: int) -> None:
    assert parse_explicit_version_or_latest(raw, latest_version=latest_version, field="version") == expected


@pytest.mark.parametrize("raw", ["", " ", "abc", "0", "-1"])
def test_parse_explicit_version_or_latest_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        parse_explicit_version_or_latest(raw, latest_version=7, field="version")

    assert exc_info.value.field == "version"
    assert exc_info.value.message == "版本参数不合法，请填写正整数版本号，或使用 latest 表示最新版本。"


@pytest.mark.parametrize(
    ("raw", "latest_version", "expected"),
    [
        (None, 7, 7),
        ("", 7, 7),
        ("latest", 7, 7),
        ("9", 7, 9),
    ],
)
def test_normalize_version_or_latest_fallback_contract(raw, latest_version: int, expected: int) -> None:
    assert normalize_version_or_latest_fallback(raw, latest_version=latest_version) == expected


@pytest.mark.parametrize("raw", ["abc", "0", "-1"])
def test_normalize_version_or_latest_fallback_rejects_invalid_explicit_values(raw: str) -> None:
    with pytest.raises(ValidationError):
        normalize_version_or_latest_fallback(raw, latest_version=7)


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


def test_resolve_route_version_or_latest_no_history_does_not_synthesize_v1() -> None:
    for raw in (None, "", "latest"):
        resolution = resolve_route_version_or_latest(raw, latest_version=0)
        assert resolution.has_history is False
        assert resolution.selected_version is None
        assert resolution.requested_version is None
        assert resolution.status == "no_history"


def test_resolve_route_version_or_latest_missing_explicit_version_is_not_selected() -> None:
    resolution = resolve_route_version_or_latest("7", latest_version=0, version_exists=lambda _version: False)

    assert resolution.has_history is False
    assert resolution.selected_version is None
    assert resolution.requested_version == 7
    assert resolution.status == "missing_history"
