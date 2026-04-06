from __future__ import annotations

import math
import sqlite3
from decimal import Decimal
from typing import Any, Dict, Optional, Union

RowLike = Union[sqlite3.Row, Dict[str, Any]]


def as_dict(row: Optional[RowLike]) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    return {k: row[k] for k in row.keys()}


def get(row: Optional[RowLike], key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        return default


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
        try:
            if math.isfinite(value) and value.is_integer():
                return int(value)
        except Exception:
            return default
        return default
    try:
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8", errors="ignore")
        s = str(value).strip()
        if s == "":
            return default
        try:
            return int(s)
        except Exception:
            pass
        try:
            d = Decimal(s)
            if not d.is_finite():
                return default
            if d == d.to_integral_value():
                return int(d)
        except Exception:
            return default
        return default
    except Exception:
        return default


def parse_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    折中安全的 float 解析：
    - 支持 '1'/'1.5'/1/1.5
    - 非法值（如 'N/A'）回落 default/None，不抛异常
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    try:
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8", errors="ignore")
        if isinstance(value, str):
            s = value.strip()
            if s == "":
                return default
            f = float(s)
        else:
            f = float(value)
        if not math.isfinite(f):
            return default
        return f
    except Exception:
        return default

