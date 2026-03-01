from __future__ import annotations

import math
from typing import Any, Optional

from core.infrastructure.errors import ValidationError
from core.services.common.enum_normalizers import normalize_yes_no_wide


def parse_finite_float(value: Any, *, field: str, allow_none: bool = True) -> Optional[float]:
    """
    Parse a float and reject non-finite values (NaN/Inf).

    Returns None only when allow_none=True and input is empty.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None if allow_none else 0.0
    try:
        v = float(value)
    except Exception as e:
        raise ValidationError(f"“{field}”必须是数字", field=field) from e
    if not math.isfinite(v):
        raise ValidationError(f"“{field}”必须是有限数字", field=field)
    return float(v)


def parse_finite_int(value: Any, *, field: str, allow_none: bool = False) -> Optional[int]:
    """
    Parse an integer and reject non-finite values (NaN/Inf).

    Accepts numeric strings like "12" and "12.0", but rejects non-integers
    like "12.5".
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None if allow_none else 0

    try:
        v = float(value)
    except Exception as e:
        raise ValidationError(f"“{field}”必须是整数", field=field) from e

    if not math.isfinite(v):
        raise ValidationError(f"“{field}”必须是有限整数", field=field)

    i = int(v)
    if abs(v - float(i)) > 1e-9:
        raise ValidationError(f"“{field}”必须是整数", field=field)
    return int(i)


def to_yes_no(value: Any, *, default: str = "no") -> str:
    """
    归一化 yes/no 开关值，返回严格的 "yes" 或 "no"。

    - 会先对输入做 str().strip().lower()
    - 视为真值：yes/y/true/1/on
    - value 为 None 时使用 default（默认 "no"）
    """
    return normalize_yes_no_wide(value, default=default, unknown_policy="no")
