from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any, Optional


def normalize_text(value: Any) -> Optional[str]:
    """
    将任意输入标准化为“去首尾空白的文本”。

    约定：
    - None -> None
    - str -> strip；空串 -> None
    - 其他类型 -> str(value).strip；空串 -> None
    """
    if value is None:
        return None
    # pandas/numpy 兼容：NaN/NaT 视为空值
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, Decimal):
        try:
            if value.is_nan():
                return None
        except (InvalidOperation, ValueError, TypeError):
            # Decimal NaN 标记检查在个别实现下可能抛异常，按空值处理更安全
            return None
    try:
        # NaN 的自反性检测：NaN != NaN
        if value != value:
            return None
    except (TypeError, ValueError):
        # 个别对象的比较实现可能抛错；此处仅跳过 NaN 自反性检测
        ...
    if isinstance(value, str):
        v = value.strip()
        return v if v != "" else None
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


def is_blank_value(value: Any) -> bool:
    """判断 Excel/表单值是否为空，不把数字 0 视为空。"""
    return normalize_text(value) is None

