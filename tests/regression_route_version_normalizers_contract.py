from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.version_resolution import resolve_version_or_latest
from web.routes.normalizers import parse_optional_version_int


@pytest.mark.parametrize(
    ("raw", "latest_version", "expected", "source"),
    [
        (None, 7, 7, "default"),
        ("", 7, 7, "default"),
        ("latest", 7, 7, "latest"),
        ("LATEST", 7, 7, "latest"),
        ("9", 7, 9, "explicit"),
    ],
)
def test_core_version_resolution_contract(raw, latest_version: int, expected: int, source: str) -> None:
    resolution = resolve_version_or_latest(raw, latest_version=latest_version, version_exists=lambda version: True)

    assert resolution.has_history is True
    assert resolution.selected_version == expected
    assert resolution.status == "ok"
    assert resolution.source == source


@pytest.mark.parametrize("raw", ["abc", "0", "-1"])
def test_core_version_resolution_rejects_invalid_explicit_values(raw: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        resolve_version_or_latest(raw, latest_version=7)

    assert exc_info.value.field == "version"
    assert exc_info.value.message == "版本号不对。请填写大于 0 的数字版本号；如果想看最新版本，可以不填版本。"


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


def test_resolve_version_or_latest_no_history_does_not_synthesize_v1() -> None:
    for raw in (None, "", "latest"):
        resolution = resolve_version_or_latest(raw, latest_version=0)
        assert resolution.has_history is False
        assert resolution.selected_version is None
        assert resolution.requested_version is None
        assert resolution.status == "no_history"


def test_resolve_version_or_latest_missing_explicit_version_is_not_selected() -> None:
    resolution = resolve_version_or_latest("7", latest_version=0, version_exists=lambda _version: False)

    assert resolution.has_history is False
    assert resolution.selected_version is None
    assert resolution.requested_version == 7
    assert resolution.status == "missing_history"
