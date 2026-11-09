from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Optional


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
