from __future__ import annotations

from typing import Any

_YES = "yes"
_NO = "no"
_YES_NO_TRUE_WIDE = ("y", _YES, "true", "1", "on")
_YES_NO_FALSE_WIDE = ("n", _NO, "false", "0", "off", "")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_default_yes_no(value: Any) -> str:
    text = _text(value).lower()
    return _YES if text in _YES_NO_TRUE_WIDE else _NO


def normalize_yes_no_wide(
    value: Any,
    *,
    default: str = _NO,
) -> str:
    # 这是 core 低层宽口径；不要改指 services.common.normalization_matrix，反向导入会把 core/services 绕成环。
    if value is None:
        return _normalize_default_yes_no(default)
    text = _text(value)
    lowered = text.lower()
    if text == "是" or lowered in _YES_NO_TRUE_WIDE:
        return _YES
    if text == "否" or lowered in _YES_NO_FALSE_WIDE:
        return _NO
    return _normalize_default_yes_no(default)
