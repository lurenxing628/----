from __future__ import annotations

from typing import Any


def _safe_int(value: Any, *, default: int = 0) -> int:
    """
    严格版整数解析（用于甘特依赖/关键链的 seq 等字段）：
    - None/bool -> default
    - "5"/"5.0"/5/5.0 -> 5
    - "5.5"/5.5/"5e0" -> default（拒绝非整数浮点与科学计数法）
    """
    if value is None or isinstance(value, bool):
        return default
    try:
        if isinstance(value, str):
            s = value.strip()
            if "e" in s.lower():
                return default
            f = float(s)
        else:
            f = float(value)
        i = int(f)
        if f != i:
            return default
        return i
    except Exception:
        return default

