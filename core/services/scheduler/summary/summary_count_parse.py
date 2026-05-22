from __future__ import annotations

import math
from typing import Any, Optional, Tuple


def parse_summary_count(value: Any, *, field: str) -> Tuple[int, Optional[str]]:
    if value is None or value == "":
        return 0, None
    if isinstance(value, bool):
        return 0, f"{field} 不能是布尔值：{value!r}"
    try:
        if isinstance(value, float):
            if not math.isfinite(value) or not value.is_integer():
                return 0, f"{field} 必须是非负整数：{value!r}"
            number = int(value)
        else:
            text = str(value).strip()
            if not text:
                return 0, None
            if "." in text:
                fv = float(text)
                if not math.isfinite(fv) or not fv.is_integer():
                    return 0, f"{field} 必须是非负整数：{value!r}"
                number = int(fv)
            else:
                number = int(text)
    except Exception:
        return 0, f"{field} 必须是非负整数：{value!r}"
    if number < 0:
        return 0, f"{field} 不能为负数：{value!r}"
    return number, None
