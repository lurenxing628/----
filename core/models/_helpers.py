from __future__ import annotations

import math
import sqlite3
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Union

RowLike = Union[sqlite3.Row, Dict[str, Any]]


def parse_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """
    折中安全的 int 解析：
    - 支持 '1'/'1.0'/1/1.0
    - 只有当值是“整数”时才接受（例如 '1.5' -> default）
    - 非法值（如 'N/A'）回落 default/None，不抛异常
    """
    if value is None:
        return default
    # bool 是 int 子类，避免 True/False 被当成 1/0
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value.is_integer() else default
    try:
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8", errors="ignore")
        s = str(value).strip()
        if s == "":
            return default
        try:
            return int(s)
        except ValueError:
            pass
        try:
            d = Decimal(s)
            if not d.is_finite():
                return default
            if d == d.to_integral_value():
                return int(d)
        except (InvalidOperation, ValueError):
            return default
        return default
    except (UnicodeDecodeError, TypeError, ValueError, ArithmeticError):
        return default


def parse_float(value: Any) -> Optional[float]:
    """
    折中安全的 float 解析：
    - 支持 '1'/'1.5'/1/1.5
    - 非法值（如 'N/A'）返回 None，不抛异常
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8", errors="ignore")
        if isinstance(value, str):
            s = value.strip()
            if s == "":
                return None
            f = float(s)
        else:
            f = float(value)
        if not math.isfinite(f):
            return None
        return f
    except (UnicodeDecodeError, TypeError, ValueError, OverflowError):
        return None


def parse_float_or_default(value: Any, default: float, *, field: str) -> float:
    if value is None or (isinstance(value, str) and not value.strip()):
        return float(default)
    parsed = parse_float(value)
    if parsed is None:
        raise ValueError(f"{field} 必须是数字，当前值无法读取：{value!r}")
    return parsed
