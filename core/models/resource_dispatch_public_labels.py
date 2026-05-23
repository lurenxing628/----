from __future__ import annotations

from typing import Any

_SOURCE_LABELS = {
    "internal": "自制",
    "external": "外协",
}

_LOCK_STATUS_LABELS = {
    "locked": "已锁定",
    "unlocked": "未锁定",
}


def _normalized_text(value: Any) -> str:
    return str(value or "").strip().lower()


def source_public_label(value: Any) -> str:
    text = _normalized_text(value)
    if not text:
        return "来源未维护"
    return _SOURCE_LABELS.get(text, "来源未识别")


def lock_status_public_label(value: Any) -> str:
    text = _normalized_text(value)
    if not text:
        return "未锁定"
    return _LOCK_STATUS_LABELS.get(text, "锁定状态未识别")


__all__ = ["source_public_label", "lock_status_public_label"]
