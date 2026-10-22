from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, MutableSequence, Optional


def normalize_text(value: Any) -> Optional[str]:
    """
    将任意输入标准化为“去首尾空白的文本”。

    约定：
    - None -> None
    - str -> strip；空串 -> None
    - 其他类型 -> str(value).strip；空串 -> None
    """
    if isinstance(value, str):
        return value.strip() or None
    if value is None:
        return None
    # Excel 中的浮点和 Decimal NaN 视为空值。
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, Decimal) and value.is_nan():
        return None
    v = str(value).strip()
    return v if v != "" else None


def to_str_or_blank(value: Any) -> str:
    """
    将任意输入标准化为“去首尾空白的文本”；空值返回空串。

    说明：
    - 与 `normalize_text()` 不同，此函数不会返回 None
    - 对数字 0 返回 "0"，避免 `value or ""` 把 0 误判为空
    """
    normalized = normalize_text(value)
    return "" if normalized is None else normalized


def append_unique_text_messages(buffer: Optional[MutableSequence[str]], messages: Any) -> None:
    """向消息缓冲区按原顺序追加非空且不重复的文本。"""
    if buffer is None:
        return
    items = messages if isinstance(messages, (list, tuple, set)) else [messages]
    for item in items:
        text = str(item or "").strip()
        if not text or text in buffer:
            continue
        buffer.append(text)

