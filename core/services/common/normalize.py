from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Optional, Tuple

from core.errors import ValidationError


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


def validate_enum(value: Optional[str], allowed: Tuple[str, ...], field: str) -> Optional[str]:
    if value is None:
        return None
    if value not in allowed:
        allow_text = "普通 / 急件 / 特急" if field == "优先级" else " / ".join(allowed)
        raise ValidationError(f"“{field}”不正确，请选择：{allow_text}。", field=field)
    return value
