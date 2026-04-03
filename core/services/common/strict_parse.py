from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Optional

from core.infrastructure.errors import ValidationError


def is_blank_input(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _raise_blank_required(field: str) -> None:
    raise ValidationError(f"“{field}”不能为空", field=field)


def _ensure_min_float(value: float, *, field: str, min_value: Optional[float], min_inclusive: bool = True) -> float:
    if min_value is not None:
        is_valid = value >= float(min_value) if bool(min_inclusive) else value > float(min_value)
        if not is_valid:
            raise ValidationError(f"“{field}”必须{'大于等于' if bool(min_inclusive) else '大于'} {min_value}", field=field)
    return float(value)


def _ensure_min_int(value: int, *, field: str, min_value: Optional[int]) -> int:
    if min_value is not None and value < int(min_value):
        raise ValidationError(f"“{field}”必须大于等于 {min_value}", field=field)
    return int(value)


def _parse_finite_float(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"“{field}”必须是数字", field=field)
    try:
        parsed = float(value)
    except Exception as exc:
        raise ValidationError(f"“{field}”必须是数字", field=field) from exc
    if not math.isfinite(parsed):
        raise ValidationError(f"“{field}”必须是有限数字", field=field)
    return float(parsed)


def _parse_finite_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"“{field}”必须是整数", field=field)
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


def parse_required_float(
    value: Any, *, field: str, min_value: Optional[float] = None, min_inclusive: bool = True
) -> float:
    if is_blank_input(value):
        _raise_blank_required(field)
    return _ensure_min_float(_parse_finite_float(value, field=field), field=field, min_value=min_value, min_inclusive=min_inclusive)


def parse_optional_float(value: Any, *, field: str, min_value: Optional[float] = None, min_inclusive: bool = True) -> Optional[float]:
    if is_blank_input(value):
        return None
    return parse_required_float(value, field=field, min_value=min_value, min_inclusive=min_inclusive)


def parse_required_int(value: Any, *, field: str, min_value: Optional[int] = None) -> int:
    if is_blank_input(value):
        _raise_blank_required(field)
    return _ensure_min_int(_parse_finite_int(value, field=field), field=field, min_value=min_value)


def parse_optional_int(value: Any, *, field: str, min_value: Optional[int] = None) -> Optional[int]:
    if is_blank_input(value):
        return None
    return parse_required_int(value, field=field, min_value=min_value)


def parse_required_date(value: Any, *, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if is_blank_input(value):
        _raise_blank_required(field)
    text = str(value).strip().replace("/", "-")
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except Exception as exc:
        raise ValidationError(f"“{field}”格式不合法（期望：YYYY-MM-DD）", field=field) from exc


def parse_optional_date(value: Any, *, field: str) -> Optional[date]:
    if is_blank_input(value):
        return None
    return parse_required_date(value, field=field)
