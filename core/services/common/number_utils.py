from __future__ import annotations

import math
from typing import Any, Literal, Optional, overload

from core.infrastructure.errors import ValidationError


@overload
def parse_finite_float(value: Any, *, field: str, allow_none: Literal[False] = False) -> float:
    ...


@overload
def parse_finite_float(value: Any, *, field: str, allow_none: Literal[True]) -> Optional[float]:
    ...


def parse_finite_float(value: Any, *, field: str, allow_none: bool = True) -> Optional[float]:
    """
    Parse a float and reject non-finite values (NaN/Inf).

    Returns None only when allow_none=True and input is empty.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None if allow_none else 0.0
    try:
        parsed = float(value)
    except Exception as exc:
        raise ValidationError(f"“{field}”必须是数字", field=field) from exc
    if not math.isfinite(parsed):
        raise ValidationError(f"“{field}”必须是有限数字", field=field)
    return float(parsed)


@overload
def parse_finite_int(value: Any, *, field: str, allow_none: Literal[False] = False) -> int:
    ...


@overload
def parse_finite_int(value: Any, *, field: str, allow_none: Literal[True]) -> Optional[int]:
    ...


def parse_finite_int(value: Any, *, field: str, allow_none: bool = False) -> Optional[int]:
    """
    Parse an integer and reject non-finite values (NaN/Inf).

    Accepts numeric strings like "12" and "12.0", but rejects non-integers
    like "12.5".
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None if allow_none else 0

    try:
        parsed = float(value)
    except Exception as exc:
        raise ValidationError(f"“{field}”必须是整数", field=field) from exc

    if not math.isfinite(parsed):
        raise ValidationError(f"“{field}”必须是有限整数", field=field)

    integer_value = int(parsed)
    if abs(parsed - float(integer_value)) > 1e-9:
        raise ValidationError(f"“{field}”必须是整数", field=field)
    return int(integer_value)
