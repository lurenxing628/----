"""回归测试：版本号归一化契约——resolve_version_or_latest 把 None/空当 default、latest/LATEST 当 latest、数字当 explicit，对 abc/0/-1 抛 ValidationError(field=version) 中文文案，且无历史(latest_version=0)时不臆造 v1 而返回 no_history/missing_history；parse_optional_version_int 保留 0/-1 原值并对非整数文本报「期望整数」。"""

from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.version_resolution import VERSION_ERROR_MESSAGE, resolve_version_or_latest
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


# --- 并入自 test_version_resolution_contract.py（P5.1 单挂靠，逐字保留唯一边界）---
# 已去重：原 test_version_resolution_reports_no_history_without_fallback_version
# 是 test_resolve_version_or_latest_no_history_does_not_synthesize_v1（遍历 None/""/"latest"，
# latest_version=0 → has_history False/selected None/status no_history）的逐字子集，故不重复并入。


def test_version_resolution_defaults_to_latest() -> None:
    result = resolve_version_or_latest(None, latest_version=7)

    assert result.has_history is True
    assert result.selected_version == 7
    assert result.requested_version is None
    assert result.status == "ok"
    assert result.source == "default"


def test_version_resolution_accepts_latest_keyword() -> None:
    result = resolve_version_or_latest("latest", latest_version=9)

    assert result.selected_version == 9
    assert result.status == "ok"
    assert result.source == "latest"


def test_version_resolution_reports_missing_explicit_history() -> None:
    # 🔴关键边界：latest_version=9（有历史）+ 请求显式版本不存在 →
    # has_history True / status missing_history / requested_version==5。
    # 与 test_resolve_version_or_latest_missing_explicit_version_is_not_selected
    # 的 latest_version=0（无历史，has_history False）取值相反，绝不可折叠。
    result = resolve_version_or_latest(
        "5",
        latest_version=9,
        version_exists=lambda version: False,
    )

    assert result.has_history is True
    assert result.selected_version is None
    assert result.requested_version == 5
    assert result.status == "missing_history"


def test_version_resolution_rejects_invalid_explicit_value() -> None:
    with pytest.raises(ValidationError, match="版本号不对") as exc_info:
        resolve_version_or_latest("bad", latest_version=9)
    assert exc_info.value.message == VERSION_ERROR_MESSAGE
    assert exc_info.value.field == "version"

    with pytest.raises(ValidationError, match="版本号不对") as exc_info:
        resolve_version_or_latest("0", latest_version=9)
    assert exc_info.value.message == VERSION_ERROR_MESSAGE
    assert exc_info.value.field == "version"
